"""Exercise the deployed app over HTTPS. Never print authentication material."""
import argparse
import json
import secrets
import tempfile
import uuid
import time
from pathlib import Path

import httpx

BASE = "https://dqhy3yyc3g60j.cloudfront.net"
SESSION = Path(tempfile.gettempdir()) / "launchpad-cloud-verification-session.json"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["start", "status", "watch", "approve", "retry", "rerender", "rewrite", "receipt", "cancel"])
    parser.add_argument("--job")
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument("--wikipedia", action="store_true")
    parser.add_argument("--duration", type=int, choices=[30, 45, 60, 90, 120, 180], default=30)
    args = parser.parse_args()
    with httpx.Client(base_url=BASE, timeout=90, follow_redirects=True) as client:
        saved = json.loads(SESSION.read_text()) if SESSION.exists() else {}
        if saved.get("cookie"):
            client.cookies.set("launchpad_session", saved["cookie"])
        else:
            response = client.post("/v1/session/register", json={"email": f"cloud-check-{uuid.uuid4().hex[:12]}@example.invalid", "password": secrets.token_urlsafe(32)})
            response.raise_for_status()
            saved["cookie"] = client.cookies.get("launchpad_session")
            SESSION.write_text(json.dumps(saved))
        job_id = args.job or saved.get("job_id")
        if args.action == "watch":
            previous = None
            for _ in range(90):
                response = client.get(f"/v1/jobs/{job_id}")
                response.raise_for_status()
                job = response.json()
                state = job["state"]
                if state != previous:
                    print(json.dumps({"job_id":job_id,"state":state,"error":job.get("error")}), flush=True)
                    previous = state
                if state not in {"queued","inspecting","researching","planning","capturing","narrating","rendering","quality_check"}:
                    break
                time.sleep(10)
            else:
                raise SystemExit("Watch timed out. Inspect the queue and worker logs.")
            args.action = "status"
        if args.action == "start":
            website = (
                "fixture://northstar"
                if args.fixture
                else "https://www.wikipedia.org/"
                if args.wikipedia
                else "https://docs.aws.amazon.com/bedrock/latest/userguide/what-is-bedrock.html"
            )
            brand = "Northstar" if args.fixture else "Wikipedia" if args.wikipedia else "Amazon Bedrock"
            request = {
                "title": f"{brand} cloud verification", "website_url": website,
                "authorization_confirmed": True, "brief": "Create a concise guided overview using only the inspected source evidence. Show what visitors can discover and how they can begin exploring. Do not invent statistics, performance claims, endorsements or benefits.",
                "duration_seconds": args.duration, "format": "presentation", "review_plan": True,
                "brand": {"name": brand, "primary_color": "#3366cc" if args.wikipedia else "#ff9900"}, "idempotency_key": uuid.uuid4().hex,
            }
            response = client.post("/v1/jobs", json={"request": request, "planner_mode": "bedrock"})
        else:
            response = client.get(f"/v1/jobs/{job_id}")
            response.raise_for_status()
            job = response.json()
            if args.action in {"approve", "retry", "cancel"}:
                action = "approve_plan" if args.action == "approve" else args.action
                response = client.post(f"/v1/jobs/{job_id}/decision", json={"action": action, "claims_reviewed": True, "version": job["version"]})
            elif args.action in {"rerender", "rewrite"}:
                response = client.post(f"/v1/jobs/{job_id}/revision", json={"change": "founder_cut" if args.action == "rewrite" else "rerender", "version": job["version"]})
            elif args.action == "receipt":
                response = client.get(f"/v1/jobs/{job_id}/receipt")
        if response.is_error:
            print(json.dumps({"http_status": response.status_code, "detail": response.text[:1400]}))
            raise SystemExit(1)
        job = response.json()
        if isinstance(job, dict) and job.get("id"):
            saved["job_id"] = job["id"]
            SESSION.write_text(json.dumps(saved))
        print(json.dumps({k: job.get(k) for k in ["id", "state", "attempt", "error", "planner", "agent_runtime", "capture_reuse", "observability"]}, indent=2))
        if job.get("artifacts"):
            print(json.dumps({"exports":[{"attempt":a["attempt"],"seconds":a["qa"]["duration_seconds"],"sha256":a["qa"]["sha256"]} for a in job["artifacts"]]}))
        if args.action in {"status", "receipt"} and job_id:
            target = Path("artifacts/cloud-verification")
            target.mkdir(parents=True, exist_ok=True)
            job.pop("owner", None)
            (target / f"{job_id}-{args.action}.json").write_text(json.dumps(job, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
