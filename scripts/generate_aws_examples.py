"""Create/review/render/stage owned demos through Launchpad, with live AWS receipts.

Planning and narration are billable. Each phase is explicit; inspect plans before
approve. No old public example is replaced until every output passes checks.
"""

import argparse
import hashlib
import json
import shutil
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
MODES = ("presentation", "product", "spotlight", "short")
RUN = ROOT / "artifacts" / "verification" / "aws-four-modes"
STATE = RUN / "jobs.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("create", "plans", "approve", "stage"))
    args = parser.parse_args()
    RUN.mkdir(parents=True, exist_ok=True)
    with httpx.Client(
        base_url="http://127.0.0.1:3011/api/backend/",
        timeout=60,
        headers={"Origin": "http://127.0.0.1:3011"},
    ) as client:

        def call(path, method="GET", body=None):
            response = client.request(method, path, json=body)
            response.raise_for_status()
            return response.json()

        def wait(job_id, target):
            deadline = time.monotonic() + 900
            previous = None
            while time.monotonic() < deadline:
                job = call(f"jobs/{job_id}")
                if job["state"] != previous:
                    print(job_id, job["state"], flush=True)
                    previous = job["state"]
                if job["state"] == target:
                    return job
                if job["state"] in ("failed", "blocked", "cancelled"):
                    raise RuntimeError(str(job.get("error") or job["state"]))
                time.sleep(2)
            raise TimeoutError(job_id)

        call("session/local", "POST")
        assert call("settings")["voice"] == "polly", "Restart worker with LAUNCHPAD_VOICE=polly"
        jobs = json.loads(STATE.read_text()) if STATE.exists() else {}
        if args.phase == "create":
            for mode in MODES:
                if mode in jobs:
                    continue
                request = {
                    "title": f"Northstar - {mode} AWS benchmark",
                    "website_url": "fixture://northstar",
                    "authorization_confirmed": True,
                    "brief": "Create a grounded Northstar product demo. Introduce the research workspace, show the evidence library, and explain decision review. Use only inspected source claims; do not invent results, prices or time savings. "
                    + (
                        "Use exactly five short scenes, with about 12 spoken words per scene. "
                        if mode == "presentation"
                        else "Use three scenes with about 20 spoken words each. "
                    )
                    + (
                        "Focus on source links staying attached to research findings."
                        if mode == "spotlight"
                        else "End with an invitation to explore Northstar."
                    ),
                    "duration_seconds": 30,
                    "format": mode,
                    "orientation": "portrait" if mode == "short" else "landscape",
                    "review_plan": True,
                    "captions": True,
                    "zoom": True,
                    "brand": {"name": "Northstar", "primary_color": "#ff9900"},
                    "idempotency_key": f"aws-four-modes-v1-{mode}",
                }
                deadline = time.monotonic() + 900
                while True:
                    try:
                        job = call("jobs", "POST", {"request": request, "planner_mode": "bedrock"})
                        break
                    except httpx.HTTPStatusError as error:
                        if error.response.status_code != 409 or time.monotonic() > deadline:
                            raise
                        # Respect the application's two-active-production limit.
                        time.sleep(2)
                jobs[mode] = job["id"]
                STATE.write_text(json.dumps(jobs, indent=2))
                print(mode, job["id"], flush=True)
        elif args.phase == "plans":
            for mode in MODES:
                job = wait(jobs[mode], "awaiting_plan_approval")
                assert job["planner"] == "bedrock" and job["model_usage"]["totalTokens"] > 0
                assert any(t["component"] == "strands" for t in job.get("trace", []))
                (RUN / f"{mode}-review.json").write_text(
                    json.dumps(
                        {
                            "plan": job["plan"],
                            "evidence": job["evidence"],
                            "claim_ledger": job["claim_ledger"],
                            "version": job["version"],
                        },
                        indent=2,
                    )
                )
                print(mode, json.dumps(job["plan"]), flush=True)
        elif args.phase == "approve":
            for mode in MODES:
                reviewed = json.loads((RUN / f"{mode}-review.json").read_text())
                job = call(f"jobs/{jobs[mode]}")
                assert job["plan"] == reviewed["plan"], "Plan changed after review"
                if job["state"] == "awaiting_plan_approval":
                    call(
                        f"jobs/{jobs[mode]}/decision",
                        "POST",
                        {
                            "action": "approve_plan",
                            "version": reviewed["version"],
                            "claims_reviewed": True,
                        },
                    )
                print("Approved reviewed plan", mode, flush=True)
                # Keep the queue within its normal concurrency limit.
                wait(jobs[mode], "ready_for_review")
        else:
            manifest = {}
            for mode in MODES:
                job = wait(jobs[mode], "ready_for_review")
                assert job["request"]["website_url"] == "fixture://northstar"
                assert job["planner"] == "bedrock" and job["model_usage"]["totalTokens"] > 0
                assert any(t["component"] == "strands" for t in job["trace"])
                artifact = job["artifacts"][-1]
                qa = artifact["qa"]
                assert qa["voices"] and all(v["provider"] == "Amazon Polly" for v in qa["voices"])
                assert 29 <= qa["duration_seconds"] <= 31
                assert (qa["width"], qa["height"]) == (
                    (1080, 1920) if mode == "short" else (2560, 1440)
                )
                for filename, suffix in (("export.mp4", "mp4"), ("poster.png", "png")):
                    response = client.get(
                        f"jobs/{job['id']}/artifacts/{artifact['attempt']}/{filename}"
                    )
                    response.raise_for_status()
                    if suffix == "mp4":
                        assert hashlib.sha256(response.content).hexdigest() == qa["sha256"]
                        assert len(response.content) == qa["bytes"]
                    (RUN / f"{mode}.{suffix}").write_bytes(response.content)
                manifest[mode] = {
                    "job_id": job["id"],
                    "planner": job["planner"],
                    "model": job["model"],
                    "model_usage": job["model_usage"],
                    "orchestrator": "Strands Agents",
                    "qa": qa,
                }
                (RUN / f"{mode}-receipt.json").write_text(
                    json.dumps(
                        {
                            **manifest[mode],
                            "trace": job["trace"],
                            "tool_receipts": job["tool_receipts"],
                            "capture_events": job.get("capture_events"),
                        },
                        indent=2,
                    )
                )
                print("Verified", mode, qa["bytes"], "bytes; all scenes Polly", flush=True)
            public = ROOT / "public" / "examples"
            backup = RUN / f"previous-public-{time.time_ns()}"
            shutil.copytree(public, backup)
            for mode in MODES:
                for extension in ("mp4", "png"):
                    shutil.copyfile(RUN / f"{mode}.{extension}", public / f"{mode}.{extension}")
            (public / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            print("Staged all four verified AWS examples. Backup:", backup, flush=True)


if __name__ == "__main__":
    main()
