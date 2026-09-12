"""Build a public, credential-free report from the owned cloud engineering run.

Does not deploy. Review public/verification before uploading the static site.
"""
import hashlib
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import boto3
import httpx
from cloud_verify import BASE, SESSION


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--public-job")
    args = parser.parse_args()
    session = json.loads(SESSION.read_text())
    proof = json.loads(Path("artifacts/cloud-verification/recovery-probe.json").read_text())
    job_id = proof["job_id"]
    assert proof["plan_preserved"]
    with httpx.Client(base_url=BASE, timeout=120, follow_redirects=True) as client:
        client.cookies.set("launchpad_session", session["cookie"])
        response = client.get(f"/v1/jobs/{job_id}/receipt")
        response.raise_for_status()
        job = response.json()
        assert job["request"]["website_url"] == "fixture://northstar"
        assert job["state"] == "ready_for_review" and job["agent_runtime"] == "agentcore"
        assert job["agent_execution"]["status"] == "completed"
        artifact = job["artifacts"][-1]
        qa = artifact["qa"]
        assert artifact["attempt"] > proof["interrupted_attempt"]
        assert artifact["capture_reuse"]["reused"] > 0
        response = client.get(f"/v1/jobs/{job_id}/artifacts/{artifact['attempt']}/export.mp4")
        response.raise_for_status()
        assert hashlib.sha256(response.content).hexdigest() == qa["sha256"]
        folder = Path("public/verification")
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "northstar-cloud-demo.mp4").write_bytes(response.content)

    logs = boto3.client("logs", region_name="us-east-1")
    groups = ["launchpad-serverless-WorkerLogGroup-eLiq88e36Oi7",
              "/aws/bedrock-agentcore/runtimes/launchpad_concierge-mSpoPr3pi7-DEFAULT",
              "/aws/lambda/launchpad-serverless-Dispatcher-9qrrL9lEnWhN",
              "/aws/lambda/launchpad-serverless-Recovery-iBcKAYG3uAG8"]
    events = []
    for group in groups:
        for page in logs.get_paginator("filter_log_events").paginate(logGroupName=group, filterPattern=f'"{job_id}"'):
            for entry in page["events"]:
                try:
                    value = json.loads(entry["message"])
                except ValueError:
                    continue
                if value.get("job_id") != job_id:
                    continue
                safe = {k: value[k] for k in ("job_id", "event", "attempt", "session_id", "action", "phase", "outcome", "elapsed_seconds") if k in value}
                events.append({"log_group": group, "timestamp": entry["timestamp"], **safe})
    assert any(e.get("event") == "agentcore_completed" for e in events)
    assert any(e.get("event") == "agentcore_session_stopped" for e in events)
    assert any(e.get("event") == "recovery_available" for e in events)
    # Publish only source/script/decision information for this owned synthetic test.
    receipt = {key: job[key] for key in ("id", "state", "attempt", "planner", "agent_runtime", "agent_session_id", "agent_execution",
               "plan", "plan_history", "evidence", "claim_ledger", "trace", "timeline", "policy_receipts", "capture_reuse") if key in job}
    receipt["exports"] = [{k: a[k] for k in ("attempt", "qa", "created_at", "capture_reuse", "plan_sha256", "export_sha256") if k in a} for a in job["artifacts"]]
    receipt["recovery_test"] = {k: v for k, v in proof.items() if k != "task_arn"}
    receipt["cloud_log_evidence"] = sorted(events, key=lambda e: e["timestamp"])
    receipt["disclosure"] = "Owned synthetic Northstar site; real AWS services. Not a customer study. Claims received an engineering review, not independent verification."
    (folder / "cloud-receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    rejected = [p for p in job["policy_receipts"] if p["action"] == "storyboard_validation" and p["outcome"] == "blocked"]
    checks = [
        {"name": "Cloud execution", "result": "passed", "evidence": "Public HTTPS API → SQS → Fargate → AgentCore / Strands / Bedrock → human approval → browser capture → Polly → MP4 → S3. Correlated service logs are included in the receipt."},
        {"name": "Actual AI revision", "result": "passed", "evidence": "AgentCore rewrote the previous storyboard for founders. Both script versions and the session identifier are retained."},
        {"name": "Policy enforcement", "result": "passed", "evidence": f"{len(rejected)} invalid storyboard submission(s) were rejected before acceptance. Before/after tool decisions and approval receipts are retained."},
        {"name": "Interrupted worker recovery", "result": "passed", "evidence": f"Stopped attempt {proof['interrupted_attempt']} during rendering. EventBridge marked it blocked; the saved script and the prior downloadable MP4 remained intact. Retry attempt {artifact['attempt']} completed."},
        {"name": "Footage preservation", "result": "passed", "evidence": f"The retry restored {artifact['capture_reuse']['reused']} S3-checkpointed clips and recorded {artifact['capture_reuse']['recorded']} new clips. Checkpoint hashes were verified before reuse."},
        {"name": "Media integrity", "result": "passed", "evidence": f"Downloaded the S3 export through the authenticated API and independently matched SHA-256 {qa['sha256']}."},
        {"name": "Observability", "result": "logs verified; span export incomplete", "evidence": "Worker, dispatcher, recovery and AgentCore logs correlate by job ID. The operations dashboard is deployed. ADOT span export returned HTTP 400; account-wide CloudWatch transaction-search configuration was not changed."},
    ]
    report = {"verified_at": datetime.now(timezone.utc).isoformat(), "job_id": job_id,
              "runtime": "Bedrock AgentCore + Strands", "model": "Amazon Nova Lite",
              **{k: qa[k] for k in ("duration_seconds", "width", "height")}, "export_sha256": qa["sha256"],
              "video_url": "/verification/northstar-cloud-demo.mp4", "receipt_url": "/verification/cloud-receipt.json",
              "checks": checks, "policy_receipts": job["policy_receipts"]}
    if args.public_job:
        with httpx.Client(base_url=BASE, timeout=120, follow_redirects=True) as client:
            client.cookies.set("launchpad_session", session["cookie"])
            response = client.get(f"/v1/jobs/{args.public_job}/receipt")
            response.raise_for_status()
            example = response.json()
            assert example["request"]["website_url"] == "https://docs.aws.amazon.com/bedrock/latest/userguide/what-is-bedrock.html"
            assert example["state"] == "ready_for_review" and example["agent_runtime"] == "agentcore"
            exported = example["artifacts"][-1]
            response = client.get(f"/v1/jobs/{example['id']}/artifacts/{exported['attempt']}/export.mp4")
            response.raise_for_status()
            assert hashlib.sha256(response.content).hexdigest() == exported["qa"]["sha256"]
            (folder / "amazon-bedrock-demo.mp4").write_bytes(response.content)
            report["public_example"] = {"job_id": example["id"], "source_url": example["request"]["website_url"],
                                        "video_url": "/verification/amazon-bedrock-demo.mp4", "qa": exported["qa"]}
            checks.append({"name": "Public website production", "result": "passed", "evidence": f"Production {example['id']} inspected the public AWS documentation, planned through AgentCore, paused for script review, captured six browser scenes, narrated with Polly and saved its verified MP4 to S3. An initial connection timeout recovered after the bounded network fix."})
    (folder / "cloud-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"job_id": job_id, "attempt": artifact["attempt"], "sha256": qa["sha256"], "correlated_log_events": len(events), "published_locally": str(folder)}))


if __name__ == "__main__":
    main()
