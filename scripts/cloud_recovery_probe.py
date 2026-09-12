"""Controlled failure of exactly the signed-in engineering test's active task.

Run only after reviewing and approving its storyboard. Never targets other jobs.
"""
import hashlib
import json
import time
from pathlib import Path
import boto3
import httpx
from cloud_verify import BASE, SESSION


def main():
    session = json.loads(SESSION.read_text())
    job_id = session["job_id"]
    ecs = boto3.client("ecs", region_name="us-east-1")
    cluster = "launchpad-serverless-Cluster-fiOlukFa9GKc"
    target = Path("artifacts/cloud-verification/recovery-probe.json")
    with httpx.Client(base_url=BASE, timeout=90, follow_redirects=True) as client:
        client.cookies.set("launchpad_session", session["cookie"])
        def job():
            response = client.get(f"/v1/jobs/{job_id}")
            response.raise_for_status()
            return response.json()
        initial = job()
        if initial["request"]["website_url"] != "fixture://northstar" or not initial.get("artifacts"):
            raise SystemExit("Requires the owned synthetic test and an existing successful export.")
        attempt = initial["attempt"]
        prior = initial["artifacts"][-1]
        for _ in range(120):
            current = job()
            if current["attempt"] != attempt:
                raise SystemExit("Attempt changed; no task will be stopped.")
            if current["state"] == "rendering":
                break
            if current["state"] not in {"queued", "capturing", "narrating", "planning", "inspecting"}:
                raise SystemExit(f"Unexpected state: {current['state']}; no task stopped.")
            time.sleep(3)
        else:
            raise SystemExit("Render did not begin; no task stopped.")
        identity = f"{job_id}-a{attempt}"
        tasks = ecs.list_tasks(cluster=cluster, startedBy=identity)["taskArns"]
        matches = [t for t in ecs.describe_tasks(cluster=cluster, tasks=tasks)["tasks"]
                   if t.get("startedBy") == identity and t["lastStatus"] == "RUNNING"] if tasks else []
        if len(matches) != 1 or not current.get("recording_checkpoints"):
            # Older receipts call the checkpoint map recordings; inspect the actual job schema.
            if len(matches) != 1 or not current.get("recordings"):
                raise SystemExit("Cannot prove a unique task with saved recordings; no task stopped.")
        proof = {"job_id": job_id, "interrupted_attempt": attempt, "task_arn": matches[0]["taskArn"],
                 "state_before": current["state"], "prior_export_sha256": prior["qa"]["sha256"],
                 "plan_before": current["plan"], "stopped_at": time.time()}
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(proof, indent=2))
        ecs.stop_task(cluster=cluster, task=matches[0]["taskArn"], reason="Launchpad authorized engineering recovery verification")
        print(json.dumps({"stopped": identity}), flush=True)
        for _ in range(90):
            current = job()
            if current["state"] == "blocked":
                break
            time.sleep(3)
        else:
            raise SystemExit("Recovery event did not produce a blocked state in time.")
        response = client.get(f"/v1/jobs/{job_id}/artifacts/{prior['attempt']}/export.mp4")
        response.raise_for_status()
        proof.update(state_after=current["state"], recovery_error=current.get("error"),
                     prior_export_download_sha256=hashlib.sha256(response.content).hexdigest(),
                     plan_preserved=current["plan"] == proof["plan_before"],
                     recovery_receipts=[p for p in current.get("policy_receipts", []) if p["action"] == "worker_recovery"])
        assert proof["prior_export_download_sha256"] == proof["prior_export_sha256"]
        assert proof["plan_preserved"] and proof["recovery_receipts"]
        target.write_text(json.dumps(proof, indent=2))
        print(json.dumps({"state": current["state"], "plan_preserved": True, "prior_export_download_verified": True}), flush=True)


if __name__ == "__main__":
    main()
