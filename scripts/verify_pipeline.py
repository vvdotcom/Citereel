"""Generate a real MP4 using the owned fixture. Bedrock can be selected explicitly."""

import argparse
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for area in ("api", "agent", "worker"):
    sys.path.insert(0, str(ROOT / "services" / area / "src"))
from launchpad_agent.contracts import GenerationRequest
from launchpad_api.store import store
from launchpad_worker.runner import process

parser = argparse.ArgumentParser()
parser.add_argument("--bedrock", action="store_true")
parser.add_argument(
    "--format", choices=["presentation", "product", "spotlight", "short"], default="presentation"
)
parser.add_argument("--portrait", action="store_true")
args = parser.parse_args()
request = GenerationRequest(
    title="Northstar — product research, with context",
    website_url="fixture://northstar",
    authorization_confirmed=True,
    brief="Introduce Northstar to a product team. Show the workspace, review the evidence library, and finish with the decision review. Only use the included evidence.",
    duration_seconds=30,
    format=args.format,
    orientation="portrait" if args.portrait else "landscape",
    idempotency_key=uuid.uuid4().hex,
)
job = store.create(
    request,
    "local-creator",
    planner_mode="bedrock" if args.bedrock else "fixture",
    claim_immediately=True,
)
print("Generating", job["id"], flush=True)
process(job, fixture=not args.bedrock)
result = store.get(job["id"])
print(
    json.dumps(
        {
            "id": job["id"],
            "state": result["state"],
            "error": result["error"],
            "artifacts": result["artifacts"],
        },
        indent=2,
    ),
    flush=True,
)
sys.exit(0 if result["state"] == "ready_for_review" else 1)
