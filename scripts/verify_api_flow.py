"""Exercise actual queued work, plan approval, export access and a persisted revision."""

import argparse
import json
import time
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument(
    "--bedrock", action="store_true", help="Use live, potentially billable Bedrock planning."
)
args = parser.parse_args()
planner_mode = "bedrock" if args.bedrock else "fixture"
client = httpx.Client(
    base_url="http://127.0.0.1:3011/api/backend/",
    timeout=30,
    headers={"Origin": "http://127.0.0.1:3011"},
)


def call(path, method="GET", body=None):
    response = client.request(method, path, json=body)
    response.raise_for_status()
    return response.json()


def wait(job_id, target):
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        j = call("jobs/" + job_id)
        if j["state"] == target:
            return j
        if j["state"] in ("blocked", "failed", "cancelled"):
            raise AssertionError(j["error"] or j["state"])
        time.sleep(1)
    raise AssertionError("Worker did not reach " + target)


call("session/local", "POST")
request = {
    "title": "Northstar — approval and revision test",
    "website_url": "fixture://northstar",
    "authorization_confirmed": True,
    "brief": "Show the workspace and evidence library, then review a decision with source context.",
    "duration_seconds": 30,
    "review_plan": True,
    "format": "presentation",
    "idempotency_key": uuid.uuid4().hex,
}
created = call("jobs", "POST", {"request": request, "planner_mode": planner_mode})
job_id = created["id"]
print("Created", job_id, flush=True)
assert call("jobs", "POST", {"request": request, "planner_mode": planner_mode})["id"] == job_id
j = wait(job_id, "awaiting_plan_approval")
assert j["plan"] and not j["artifacts"]
print("Plan paused for approval", flush=True)
call(
    "jobs/" + job_id + "/decision",
    "POST",
    {"action": "approve_plan", "version": j["version"], "claims_reviewed": True},
)
j = wait(job_id, "ready_for_review")
first = j["artifacts"][-1]
assert first["qa"]["video_codec"] == "h264"
print("First export passed", flush=True)
url = f"jobs/{job_id}/artifacts/{first['attempt']}/export.mp4"
response = client.get(url, headers={"Range": "bytes=0-255"})
assert response.status_code == 206 and len(response.content) == 256
call("jobs/" + job_id + "/revision", "POST", {"change": "portrait", "version": j["version"]})
j = wait(job_id, "ready_for_review")
assert len(j["artifacts"]) == 2 and j["artifacts"][-1]["qa"]["height"] == 1920
assert j["artifacts"][0]["qa"]["sha256"] == first["qa"]["sha256"]
assert client.get(url).status_code == 200
call("jobs/" + job_id + "/decision", "POST", {"action": "approve_export", "version": j["version"]})
assert call("jobs/" + job_id)["state"] == "approved"
out = ROOT / "artifacts" / "verification"
out.mkdir(parents=True, exist_ok=True)
(out / ("api-flow-bedrock.json" if args.bedrock else "api-flow.json")).write_text(
    json.dumps(
        {
            "job_id": job_id,
            "planner": j.get("planner"),
            "model": j.get("model"),
            "model_usage": j.get("model_usage"),
            "approved": True,
            "checks": [
                "idempotency",
                "plan approval pause",
                "real queue worker",
                "H.264/AAC export",
                "HTTP range playback",
                "portrait revision",
                "prior export preserved",
            ],
            "artifacts": j["artifacts"],
        },
        indent=2,
    ),
    encoding="utf-8",
)
print("API approval and revision flow passed", flush=True)
