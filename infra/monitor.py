"""EventBridge-driven, approval-gated website monitoring for cloud jobs."""
import json
import os
import time

import boto3
from boto3.dynamodb.conditions import Attr


READY = {"ready_for_review", "approved", "blocked"}


def handler(_event, _context):
    now = time.time()
    table = boto3.resource("dynamodb").Table(os.environ["LAUNCHPAD_DYNAMODB_TABLE"])
    queue = boto3.client("sqs", region_name=os.getenv("AWS_REGION"))
    checked = queued = 0
    scan = table.scan(FilterExpression=Attr("entity").eq("job"))
    while True:
        for item in scan.get("Items", []):
            checked += 1
            job = json.loads(item["payload"])
            monitor = job.get("monitor", {})
            if not monitor.get("enabled") or monitor.get("next_check_at", now + 1) > now:
                continue
            if job.get("state") not in READY or not job.get("plan") or not job.get("evidence"):
                continue
            interval = int(monitor.get("interval_hours", 24))
            old_version, old_attempt = job["version"], job["attempt"]
            job.update(
                resume_state=job["state"], operation="check_changes", state="queued",
                error=None, attempt=old_attempt + 1,
                monitor={"enabled": True, "interval_hours": interval, "next_check_at": now + interval * 3600},
                updated_at=now, version=old_version + 1,
            )
            job.setdefault("timeline", []).append({"stage": "queued", "detail": "Scheduled website check started. No rewrite or render is authorized.", "at": now})
            job.setdefault("trace", []).append({"component": "eventbridge", "event": "monitor_check_queued", "detail": f"Scheduled {interval}-hour source check.", "at": now})
            try:
                table.update_item(
                    Key={"pk": item["pk"], "sk": item["sk"]},
                    UpdateExpression="SET #payload=:payload, #state=:state, #version=:version, #attempt=:attempt",
                    ConditionExpression="#version=:old",
                    ExpressionAttributeNames={"#payload": "payload", "#state": "state", "#version": "version", "#attempt": "attempt"},
                    ExpressionAttributeValues={":payload": json.dumps(job), ":state": "queued", ":version": old_version + 1, ":attempt": old_attempt + 1, ":old": old_version},
                )
                queue.send_message(QueueUrl=os.environ["LAUNCHPAD_QUEUE_URL"], MessageBody=json.dumps({"job_id": job["id"], "attempt": old_attempt + 1}))
                queued += 1
            except table.meta.client.exceptions.ConditionalCheckFailedException:
                continue
        if "LastEvaluatedKey" not in scan:
            break
        scan = table.scan(FilterExpression=Attr("entity").eq("job"), ExclusiveStartKey=scan["LastEvaluatedKey"])
    print(json.dumps({"event": "monitor_tick", "checked": checked, "queued": queued}))
    return {"checked": checked, "queued": queued}
