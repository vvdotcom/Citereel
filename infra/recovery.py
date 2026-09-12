"""Event-driven recovery after a task dies or exhausts queue deliveries."""
import hashlib
import json
import os
import time
import boto3

ACTIVE = {"queued", "inspecting", "researching", "planning", "capturing", "narrating", "rendering", "quality_check"}


def recover(table, job_id, attempt, reason):
    key = {"pk": f"JOB#{job_id}", "sk": "JOB"}
    for _ in range(5):
        item = table.get_item(Key=key, ConsistentRead=True).get("Item")
        if not item or int(item["attempt"]) != attempt or item["state"] not in ACTIVE:
            return
        job = json.loads(item["payload"])
        previous = job["version"]
        job.update(state="blocked", error=reason, version=previous+1, updated_at=time.time())
        job.setdefault("trace", []).append({"component": "recovery", "event": "worker_stopped", "detail": reason, "at": time.time()})
        job.setdefault("policy_receipts", []).append({"action": "worker_recovery", "phase": "after", "outcome": "blocked", "detail": reason, "at": time.time(), "attempt": attempt, "policy_version": "2026-09-09"})
        try:
            table.update_item(Key=key, UpdateExpression="SET #s=:s, #p=:p, #v=:v, lease=:zero", ConditionExpression="#v=:old AND #a=:a",
                ExpressionAttributeNames={"#s": "state", "#p": "payload", "#v": "version", "#a": "attempt"},
                ExpressionAttributeValues={":s": "blocked", ":p": json.dumps(job), ":v": previous+1, ":old": previous, ":a": attempt, ":zero": 0})
            print(json.dumps({"job_id": job_id, "event": "recovery_available", "attempt": attempt}))
            return
        except table.meta.client.exceptions.ConditionalCheckFailedException:
            continue
    raise RuntimeError("Job changed during recovery; retry the event.")


def handler(event, _context):
    table = boto3.resource("dynamodb").Table(os.environ["LAUNCHPAD_DYNAMODB_TABLE"])
    if event.get("source") == "aws.ecs":
        detail = event["detail"]
        identity = detail.get("startedBy", "")
        if not identity.startswith("lp_") or "-a" not in identity:
            return
        job_id, attempt_text = identity.rsplit("-a", 1)
        attempt = int(attempt_text)
        recover(table, job_id, attempt, "The cloud worker stopped before completion. Saved storyboard and S3 recordings are preserved. Retry to resume (maximum three retries).")
        token = hashlib.sha256(f"{job_id}:{attempt}".encode()).hexdigest()
        for slot in range(int(os.getenv("WORKER_CONCURRENCY", "2"))):
            try:
                table.delete_item(Key={"pk": f"WORKER_SLOT#{slot}", "sk": "SLOT"}, ConditionExpression="#t=:t", ExpressionAttributeNames={"#t": "token"}, ExpressionAttributeValues={":t": token})
            except table.meta.client.exceptions.ConditionalCheckFailedException:
                pass
    else:
        for record in event.get("Records", []):
            message = json.loads(record["body"])
            recover(table, message["job_id"], message["attempt"], "The cloud queue exhausted its delivery attempts. Retry after checking worker availability; saved work is preserved.")
