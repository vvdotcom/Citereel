"""Live selective-update integration test on an explicitly synthetic, owned fixture.
Prepare creates a baseline export and requests a Bedrock rewrite; finish approves the
reviewed plan and verifies recording reuse. Both commands can incur AWS charges.
"""

import argparse
import json
import uuid
from pathlib import Path

from launchpad_agent.concierge import fixture_plan
from launchpad_agent.contracts import GenerationRequest
from launchpad_api import main
from launchpad_api.store import Store
from launchpad_worker.fixture import FIXTURES
from launchpad_worker.runner import process

parser = argparse.ArgumentParser()
parser.add_argument("action", choices=["prepare", "propose", "finish"])
parser.add_argument("--job")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
db = Store(root / ".launchpad-data" / "selective-update-verification")
main.store = db
owner = "simulated-selective-update"
pages = FIXTURES["northstar"]["pages"]
changed_key = list(pages)[2]


def change_fixture():
    title, excerpt = pages[changed_key]
    pages[changed_key] = (title, excerpt + " Review decisions with a source checklist.")


if args.action == "prepare":
    request = GenerationRequest(
        website_url="fixture://northstar",
        authorization_confirmed=True,
        brief="Introduce the workspace using the retrieved product evidence.",
        title="Controlled website-update test — synthetic source",
        duration_seconds=45,
        idempotency_key=uuid.uuid4().hex,
        brand={"name": "Northstar test", "primary_color": "#ff9900"},
    )
    job = db.create(request, owner, planner_mode="fixture")
    fixture_plan(db, job["id"])
    process(db.claim(), db, fixture=True)
    job = db.get(job["id"])
    assert job["state"] == "ready_for_review", job["error"]
    print("Baseline export passed", job["id"], flush=True)
    change_fixture()
    main.check_changes(job["id"], main.Version(version=job["version"]), user=owner)
    process(db.claim(), db)
    job = db.get(job["id"])
    assert job["state"] == "awaiting_changes_approval", job["error"]
    assert job["change_proposal"]["affected_scenes"] == [3]
    main.decision(
        job["id"], main.Decision(action="approve_changes", version=job["version"]), user=owner
    )
    process(db.claim(), db)
    job = db.get(job["id"])
    assert job["state"] == "awaiting_plan_approval", job["error"]
    assert job["planner"] == "bedrock" and job["model_usage"]["totalTokens"] > 0
elif args.action == "propose":
    if not args.job:
        parser.error("--job required")
    change_fixture()
    job = db.get(args.job)
    main.decision(
        job["id"], main.Decision(action="approve_changes", version=job["version"]), user=owner
    )
    process(db.claim(), db)
    job = db.get(job["id"])
    assert job["state"] == "awaiting_plan_approval", job["error"]
else:
    if not args.job:
        parser.error("--job required")
    change_fixture()
    job = db.get(args.job)
    old = job["artifacts"][0]
    assert job["plan"]["scenes"][:2] == old["plan"]["scenes"][:2]
    main.decision(
        job["id"],
        main.Decision(action="approve_plan", version=job["version"], claims_reviewed=True),
        user=owner,
    )
    process(db.claim(), db)
    job = db.get(job["id"])
    assert job["state"] == "ready_for_review", job["error"]
    assert job["capture_reuse"] == {"reused": 2, "recorded": 1}
    assert job["artifacts"][0] == old
    assert job["artifacts"][-1]["qa"]["video_codec"] == "h264"
out = root / "artifacts" / "verification" / "selective-update-live.json"
out.parent.mkdir(parents=True, exist_ok=True)
receipt = {k: v for k, v in job.items() if k not in ("owner", "recordings", "clips")}
receipt["verification_disclosure"] = (
    "Controlled owned-fixture change, not a claim that AWS documentation changed. Baseline planner is deterministic; update planner is live Bedrock. Reviewer is an automated testing session."
)
out.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
print(
    json.dumps(
        {
            "id": job["id"],
            "state": job["state"],
            "plan": job["plan"],
            "reuse": job.get("capture_reuse"),
        },
        indent=2,
    ),
    flush=True,
)
