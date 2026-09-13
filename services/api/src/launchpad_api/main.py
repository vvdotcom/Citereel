import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
import uuid
from typing import Literal

import boto3
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from launchpad_agent.concierge import claim_ledger, validate_plan
from launchpad_agent.contracts import GenerationRequest, Storyboard
from launchpad_worker.fixture import is_fixture_url
from launchpad_worker.network import origin, validate_url
from pydantic import BaseModel, Field

from .settings import API_SECRET, configuration
from .queue import enqueue
from .store import ACTIVE, store
from .audit import append_policy, digest, emit, observability

app = FastAPI(title="Launchpad Concierge", version="1.0.0")
cors_origins = [
    value.strip()
    for value in os.getenv("LAUNCHPAD_WEB_ORIGINS", "http://127.0.0.1:3011,http://localhost:3011").split(
        ","
    )
    if value.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def trusted_proxy(request: Request, call_next):
    configured = os.getenv("LAUNCHPAD_REQUIRE_PROXY_SECRET")
    proxy_required = bool(API_SECRET) if configured is None else configured.lower() == "true"
    if proxy_required and request.url.path != "/health" and (
        not API_SECRET
        or not hmac.compare_digest(request.headers.get("x-launchpad-api-secret", ""), API_SECRET)
    ):
        return JSONResponse({"detail": "Use the Launchpad web application."}, status_code=403)
    return await call_next(request)


@app.exception_handler(KeyError)
async def missing(request, exc):
    return JSONResponse({"detail": "Job not found"}, status_code=404)


@app.exception_handler(ValueError)
async def invalid(request, exc):
    return JSONResponse({"detail": str(exc)[:1200]}, status_code=409)


def owner(request: Request):
    try:
        return store.owner(request.cookies.get("launchpad_session", ""))
    except PermissionError:
        raise HTTPException(401, "Sign in to your workspace.") from None


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=10, max_length=200)


def password_hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 300000).hex()


def set_session(response, owner_id):
    response.set_cookie(
        "launchpad_session",
        store.session(owner_id),
        httponly=True,
        samesite="lax",
        secure=os.getenv("LAUNCHPAD_SECURE_COOKIES") == "true",
        max_age=604800,
        path="/",
    )


@app.get("/health")
def health():
    return {"ok": True, "service": "launchpad-api"}


@app.get("/v1/session")
def session(user=Depends(owner)):
    return {"owner": user, "email": store.user_email(user)}


@app.post("/v1/session/local")
def local_session(response: Response):
    if os.getenv("LAUNCHPAD_LOCAL_MODE", "true") != "true":
        raise HTTPException(403, "Local workspace is disabled.")
    set_session(response, "local-creator")
    return {"owner": "local-creator"}


@app.post("/v1/session/register")
def register(body: Credentials, response: Response):
    if "@" not in body.email:
        raise ValueError("Enter a valid email address.")
    user = store.register_user(body.email.strip().lower(), body.password)
    set_session(response, user)
    return {"owner": user, "email": body.email.strip().lower()}


@app.post("/v1/session/login")
def login(body: Credentials, response: Response):
    try:
        user = store.authenticate(body.email.strip().lower(), body.password)
    except PermissionError:
        raise HTTPException(401, "Email or password is incorrect.")
    set_session(response, user)
    return {"owner": user, "email": body.email.strip().lower()}


@app.post("/v1/session/judge-demo")
def judge_demo(response: Response):
    """Sign reviewers into the shared, ordinary judge workspace.

    Credentials are configured only in the API environment. The endpoint is
    intentionally unavailable on deployments that do not provide both values.
    """
    email = os.getenv("LAUNCHPAD_JUDGE_DEMO_EMAIL", "").strip().lower()
    password = os.getenv("LAUNCHPAD_JUDGE_DEMO_PASSWORD", "")
    if not email or not password:
        raise HTTPException(404, "Judge demo access is not enabled for this deployment.")
    try:
        user = store.authenticate(email, password)
    except PermissionError:
        try:
            user = store.register_user(email, password)
        except ValueError:
            user = store.authenticate(email, password)
    set_session(response, user)
    return {"owner": user, "judge_demo": True}


@app.post("/v1/session/logout")
def logout(request: Request, response: Response):
    store.end_session(request.cookies.get("launchpad_session", ""))
    response.delete_cookie("launchpad_session", path="/")
    return {"ok": True}


@app.get("/v1/settings")
def settings(user=Depends(owner)):
    return configuration()


@app.get("/v1/jobs")
def jobs(user=Depends(owner)):
    return [job_view(j) for j in store.list(user)]


class Create(BaseModel):
    request: GenerationRequest
    planner_mode: Literal["bedrock", "fixture"] = "bedrock"


@app.post("/v1/jobs", status_code=201)
def create(body: Create, user=Depends(owner)):
    if not body.request.authorization_confirmed:
        raise ValueError("Confirm that you have permission to capture this website.")
    if not is_fixture_url(body.request.website_url):
        validate_url(body.request.website_url)
        allowed = configuration()["allowed_origins"]
        if allowed and origin(body.request.website_url) not in {origin(x) for x in allowed}:
            raise ValueError("This website is not in the operator's allowed origins.")
    if body.planner_mode == "fixture" and not is_fixture_url(body.request.website_url):
        raise ValueError("Local fixture mode only accepts an included demo site.")
    job = store.create(body.request, user, planner_mode=body.planner_mode)
    enqueue(job)
    return job


@app.get("/v1/jobs/{job_id}")
def get_job(job_id: str, user=Depends(owner)):
    return job_view(store.get(job_id, user))


def job_view(j):
    if j.get("plan"):
        j["claim_ledger"] = claim_ledger(j["plan"], j["evidence"])
    j["observability"] = observability(j)
    return j


class Decision(BaseModel):
    action: Literal[
        "cancel",
        "retry",
        "approve_plan",
        "approve_export",
        "reject_plan",
        "approve_changes",
        "dismiss_changes",
    ]
    claims_reviewed: bool = False
    version: int


@app.post("/v1/jobs/{job_id}/decision")
def decision(job_id: str, body: Decision, user=Depends(owner)):
    def change(j):
        if body.version != j["version"]:
            raise ValueError("This job changed. Refresh and try again.")
        if body.action == "cancel":
            if j["state"] not in ACTIVE | {
                "awaiting_plan_approval",
                "awaiting_changes_approval",
                "blocked",
            }:
                raise ValueError("This production cannot be cancelled.")
            j.update(cancel_requested=True, state="cancelled")
        elif body.action == "retry":
            if j["state"] not in {"blocked", "failed"}:
                raise ValueError("Only interrupted or failed jobs can be retried.")
            if j.get("retry_count", 0) >= 3:
                raise ValueError("Retry limit reached. Create a smaller production.")
            j.update(
                state="queued",
                attempt=j["attempt"] + 1,
                error=None,
                needs_decision=False,
                retry_count=j.get("retry_count", 0) + 1,
            )
        elif body.action == "approve_plan":
            if j["state"] != "awaiting_plan_approval":
                raise ValueError("There is no pending plan to approve.")
            ledger = claim_ledger(j["plan"], j["evidence"])
            if any(c["status"] == "needs_review" for c in ledger) and not body.claims_reviewed:
                raise ValueError(
                    "Review the cited evidence and acknowledge the claims before approving."
                )
            j.update(
                state="queued", plan_approved=True, claim_ledger=ledger, attempt=j["attempt"] + 1
            )
            j["approvals"].append(
                {"action": "claims_reviewed", "at": time.time(), "reviewer": user}
            )
        elif body.action == "reject_plan":
            if j["state"] != "awaiting_plan_approval":
                raise ValueError("There is no pending plan.")
            j.update(state="blocked", error="Plan rejected. Edit the storyboard and retry.")
        elif body.action in {"approve_changes", "dismiss_changes"}:
            if j["state"] != "awaiting_changes_approval":
                raise ValueError("There is no pending website change proposal.")
            proposal = j["change_proposal"]
            if body.action == "dismiss_changes":
                j.update(state=j.get("resume_state", "ready_for_review"))
                proposal["decision"] = "dismissed"
            elif not proposal["affected_scenes"]:
                j.update(state=j.get("resume_state", "ready_for_review"))
                proposal["decision"] = "no_scene_update_required"
            else:
                old = j["plan"]
                locked = {
                    str(i): scene
                    for i, scene in enumerate(old["scenes"])
                    if i + 1 not in proposal["affected_scenes"]
                }
                j["plan_history"] = j.get("plan_history", []) + [old]
                j.update(
                    evidence=proposal["evidence"],
                    plan=None,
                    claim_ledger=[],
                    plan_approved=False,
                    state="queued",
                    attempt=j["attempt"] + 1,
                    planner_mode="bedrock",
                    revision_context={
                        "instruction": "Update ONLY affected scenes to reflect the current sources. Keep every locked scene and scene count exactly unchanged.",
                        "previous_plan": old,
                        "locked_scenes": locked,
                        "affected_scenes": proposal["affected_scenes"],
                    },
                )
                j["request"]["review_plan"] = True
                proposal["decision"] = "accepted"
        elif body.action == "approve_export":
            if j["state"] != "ready_for_review" or not j["artifacts"]:
                raise ValueError("An export must pass QA before approval.")
            j["state"] = "approved"
        j["approvals"].append({"action": body.action, "at": time.time(), "attempt": j["attempt"]})
        append_policy(j, body.action, "after", "passed", "Owner, current version and allowed state verified; human decision persisted")
        j["timeline"].append(store.event(j["state"], body.action.replace("_", " ").capitalize()))

    result = store.mutate(job_id, change, user)
    emit(job_id, "human_decision", action=body.action, attempt=result["attempt"])
    if result["state"] == "queued":
        enqueue(result)
    return result


class Edit(BaseModel):
    plan: Storyboard
    version: int


@app.put("/v1/jobs/{job_id}/storyboard")
def storyboard(job_id: str, body: Edit, user=Depends(owner)):
    def change(j):
        if j["version"] != body.version:
            raise ValueError("This job changed. Refresh before saving.")
        if j["state"] not in {"awaiting_plan_approval", "ready_for_review", "approved", "blocked"}:
            raise ValueError("Wait for the current production stage to finish.")
        plan = validate_plan(body.plan, j["evidence"], j["request"])
        old = j["plan"]
        if not old or [(x["page_id"], x["scroll"]) for x in old["scenes"]] != [
            (x["page_id"], x["scroll"]) for x in plan["scenes"]
        ]:
            j["clips"] = None
        j["plan_history"] = j.get("plan_history", []) + [old]
        j.update(
            plan=plan,
            claim_ledger=claim_ledger(plan, j["evidence"]),
            plan_approved=False,
            state="awaiting_plan_approval",
        )

    result = store.mutate(job_id, change, user)
    if result["state"] == "queued":
        enqueue(result)
    return result


class Revision(BaseModel):
    change: Literal[
        "shorter",
        "founder_cut",
        "social_cut",
        "captions_on",
        "captions_off",
        "landscape",
        "portrait",
        "rerender",
        "presentation",
        "product",
        "spotlight",
        "short",
    ]
    version: int


@app.post("/v1/jobs/{job_id}/revision")
def revise(job_id: str, body: Revision, user=Depends(owner)):
    def change(j):
        if j["version"] != body.version or j["state"] not in {
            "ready_for_review",
            "approved",
            "blocked",
        }:
            raise ValueError("Refresh and finish the current job before revising.")
        if not j["plan"]:
            raise ValueError("A saved storyboard is required.")
        if body.change in {"shorter", "founder_cut"}:
            j["request"]["duration_seconds"] = max(
                [30] + [d for d in (30, 45, 60, 90, 120) if d < j["request"]["duration_seconds"]]
            )
        if body.change == "founder_cut":
            j["request"]["audience"] = "Founders and product leaders"
            j["request"]["tone"] = "Professional and confident"
        if body.change == "social_cut":
            j["request"].update(
                duration_seconds=30,
                orientation="portrait",
                format="short",
                audience="Social audiences",
                tone="Energetic and concise",
            )
        if body.change.startswith("captions_"):
            j["request"]["captions"] = body.change == "captions_on"
        if body.change in ("portrait", "landscape"):
            j["request"]["orientation"] = body.change
        if body.change in ("presentation", "product", "spotlight", "short"):
            j["request"]["format"] = body.change
        rewrite = body.change in {"shorter", "founder_cut", "social_cut"}
        if rewrite:
            previous = j["plan"]
            j["plan_history"] = j.get("plan_history", []) + [previous]
            j.update(
                plan=None,
                claim_ledger=[],
                planner_mode="bedrock",
                revision_context={
                    "instruction": f"Rewrite this storyboard for {body.change} using the updated audience, tone and duration. Do not merely truncate sentences. Preserve page choices where they support the revised story.",
                    "previous_plan": previous,
                },
            )
            j["request"]["review_plan"] = True
        else:
            j["claim_ledger"] = claim_ledger(j["plan"], j["evidence"])
        j.update(
            state="queued",
            attempt=j["attempt"] + 1,
            error=None,
            plan_approved=False if rewrite else j.get("plan_approved", False),
        )
        j["timeline"].append(
            store.event(
                "queued",
                "Revision: " + body.change + ". Reusing source evidence and eligible recordings.",
            )
        )

    result = store.mutate(job_id, change, user)
    if result["state"] == "queued":
        enqueue(result)
    return result


@app.get("/v1/jobs/{job_id}/artifacts/{attempt}/{filename}")
def artifact(job_id: str, attempt: int, filename: str, user=Depends(owner)):
    j = store.get(job_id, user)
    entry = next((a for a in j["artifacts"] if a["attempt"] == attempt), None)
    if not entry or filename not in {
        "export.mp4",
        "poster.png",
        "quality.json",
        "capture-events.json",
    }:
        raise HTTPException(404, "Artifact not found")
    bucket = os.getenv("LAUNCHPAD_ARTIFACT_BUCKET")
    if bucket:
        key = f"{entry['folder'].strip('/')}/{filename}"
        url = boto3.client("s3", region_name=os.getenv("AWS_REGION")).generate_presigned_url(
            "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=300
        )
        return RedirectResponse(url)
    # Entries are committed only after QA. A later failed/cancelled revision must
    # not revoke access to a previously completed export.
    path = (store.root / entry["folder"] / filename).resolve()
    if not path.is_relative_to(store.root) or not path.is_file():
        raise HTTPException(404, "Artifact not found")
    return FileResponse(path, media_type="video/mp4" if filename.endswith(".mp4") else None)


@app.get("/v1/jobs/{job_id}/receipt")
def receipt(job_id: str, user=Depends(owner)):
    j = store.get(job_id, user)
    exported = {k: v for k, v in job_view(j).items() if k not in ("owner", "clips", "recordings")}
    return Response(
        json.dumps(exported, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{job_id}-receipt.json"'},
    )


class Version(BaseModel):
    version: int


class MonitorSettings(BaseModel):
    enabled: bool
    interval_hours: Literal[6, 12, 24] = 24


@app.put("/v1/jobs/{job_id}/monitor")
def set_monitor(job_id: str, body: MonitorSettings, user=Depends(owner)):
    """Opt in to bounded background checks; changed content always awaits approval."""
    def change(j):
        if j["state"] not in {"ready_for_review", "approved", "blocked"}:
            raise ValueError("Finish the current production before changing monitoring.")
        if body.enabled and (not j.get("plan") or not j.get("evidence")):
            raise ValueError("A source-backed storyboard is required before monitoring.")
        j["monitor"] = {
            "enabled": body.enabled,
            "interval_hours": body.interval_hours,
            "next_check_at": time.time() + body.interval_hours * 3600 if body.enabled else None,
        }
        j.setdefault("trace", []).append({
            "component": "api", "event": "monitor_enabled" if body.enabled else "monitor_disabled",
            "detail": "Scheduled checks never rewrite, record, or publish without a fresh human approval.", "at": time.time(),
        })

    return store.mutate(job_id, change, user)


@app.post("/v1/jobs/{job_id}/changes")
def check_changes(job_id: str, body: Version, user=Depends(owner)):
    def change(j):
        if j["version"] != body.version or j["state"] not in {
            "ready_for_review",
            "approved",
            "blocked",
        }:
            raise ValueError("Finish the current job and refresh before checking the website.")
        if not j.get("plan") or not j["evidence"]:
            raise ValueError("A source-backed storyboard is required.")
        j.update(resume_state=j["state"], operation="check_changes", state="queued", error=None)
        j["attempt"] += 1
        j["timeline"].append(
            store.event(
                "queued",
                "Checking the previously inspected pages for text changes. No recording or AI rewrite is authorized yet.",
            )
        )

    result = store.mutate(job_id, change, user)
    enqueue(result)
    return result


class Trial(BaseModel):
    participant: Literal["Maya Chen", "Jordan Brooks", "Sam Patel", "Alex Rivera", "Taylor Morgan"]
    notes: str = Field(default="", max_length=1000)
    baseline_seconds: float | None = Field(default=None, gt=0, le=86400)
    version: int


@app.post("/v1/jobs/{job_id}/trial")
def trial(job_id: str, body: Trial, user=Depends(owner)):
    def change(j):
        if body.version != j["version"] or j["state"] not in {"ready_for_review", "approved"}:
            raise ValueError("Complete an export and refresh before saving a test session.")
        artifact = j["artifacts"][-1]
        elapsed = artifact["created_at"] - j["created_at"]
        j.setdefault("test_sessions", []).append(
            {
                "participant": body.participant,
                "simulated": True,
                "disclosure": "Fictional test persona, not a real founder or customer testimonial.",
                "recorded_at": time.time(),
                "production_elapsed_seconds": elapsed,
                "revision_requests": sum(
                    x["detail"].startswith("Revision:") for x in j["timeline"]
                ),
                "storyboard_edits": len(j.get("plan_history", [])),
                "manual_baseline_seconds": body.baseline_seconds,
                "baseline_provenance": "Tester-entered; not independently verified"
                if body.baseline_seconds
                else "Not measured",
                "would_use": None,
                "notes": body.notes,
            }
        )

    return store.mutate(job_id, change, user)
