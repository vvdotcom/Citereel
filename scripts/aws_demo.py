"""Explicit, local-only AWS demo actions. Create/revise/approve can incur AWS charges."""

import argparse
import json
import uuid
from pathlib import Path

import httpx

parser = argparse.ArgumentParser()
parser.add_argument(
    "action", choices=["create", "show", "approve", "retry", "revise", "check", "trial"]
)
parser.add_argument("--job")
parser.add_argument("--participant", default="Maya Chen")
parser.add_argument("--notes", default="")
parser.add_argument(
    "--website", default="https://docs.aws.amazon.com/bedrock/latest/userguide/what-is-bedrock.html"
)
parser.add_argument("--duration", type=int, choices=[30, 45, 60, 90, 120, 180], default=30)
parser.add_argument("--title", default="Amazon Bedrock — simulated founder walkthrough")
parser.add_argument("--brand", default="Amazon Bedrock")
parser.add_argument("--audience", default="Founders evaluating generative AI")
parser.add_argument("--cta")
parser.add_argument(
    "--brief",
    default="Explain Amazon Bedrock to founders evaluating generative AI. Use only inspected AWS documentation. Introduce foundation models, show model availability, then getting started. No invented performance or cost claims. This is an independent testing demo, not an Amazon endorsement.",
)
args = parser.parse_args()
client = httpx.Client(
    base_url="http://127.0.0.1:3011/api/backend/",
    timeout=30,
    headers={"Origin": "http://127.0.0.1:3011"},
)


def call(path, method="GET", body=None):
    result = client.request(method, path, json=body)
    if result.is_error:
        raise SystemExit(
            f"Launchpad API {result.status_code}: {result.json().get('detail', 'Request rejected')}"
        )
    result.raise_for_status()
    return result.json()


call("session/local", "POST")
if args.action == "create":
    job = call(
        "jobs",
        "POST",
        {
            "planner_mode": "bedrock",
            "request": {
                "title": args.title,
                "website_url": args.website,
                "brief": args.brief,
                "audience": args.audience,
                "duration_seconds": args.duration,
                "format": "presentation",
                "orientation": "landscape",
                "call_to_action": args.cta or f"Explore {args.brand}",
                "brand": {"name": args.brand, "primary_color": "#ff9900"},
                "review_plan": True,
                "authorization_confirmed": True,
                "idempotency_key": uuid.uuid4().hex,
            },
        },
    )
else:
    if not args.job:
        parser.error("--job is required")
    job = call("jobs/" + args.job)
    base = "jobs/" + args.job
    if args.action == "retry":
        job = call(base + "/decision", "POST", {"action": "retry", "version": job["version"]})
    elif args.action == "approve":
        job = call(
            base + "/decision",
            "POST",
            {"action": "approve_plan", "version": job["version"], "claims_reviewed": True},
        )
    elif args.action == "revise":
        job = call(base + "/revision", "POST", {"change": "founder_cut", "version": job["version"]})
    elif args.action == "check":
        job = call(base + "/changes", "POST", {"version": job["version"]})
    elif args.action == "trial":
        job = call(
            base + "/trial",
            "POST",
            {"version": job["version"], "participant": args.participant, "notes": args.notes},
        )
out = Path(__file__).resolve().parents[1] / "artifacts" / "verification"
out.mkdir(parents=True, exist_ok=True)
receipt = call("jobs/" + job["id"] + "/receipt")
(out / (job["id"] + "-aws-demo.json")).write_text(json.dumps(receipt, indent=2), encoding="utf-8")
print(
    json.dumps(
        {
            k: job.get(k)
            for k in (
                "id",
                "state",
                "error",
                "attempt",
                "plan",
                "model_usage",
                "capture_reuse",
                "change_proposal",
                "test_sessions",
            )
        },
        indent=2,
    )
)
