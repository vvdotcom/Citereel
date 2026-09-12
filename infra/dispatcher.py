"""SQS-to-Fargate bridge. A successful launch is intentionally idempotent.

The worker claims the durable DynamoDB job before it does work, so duplicate
SQS deliveries cannot create duplicate renders.
"""

import json
import os
import time
import hashlib

import boto3


def handler(event, _context):
    ecs = boto3.client("ecs")
    table = boto3.resource("dynamodb").Table(os.environ["LAUNCHPAD_DYNAMODB_TABLE"])
    failures = []
    for record in event["Records"]:
        message = json.loads(record["body"])
        try:
            item = table.get_item(Key={"pk": f"JOB#{message['job_id']}", "sk": "JOB"}, ConsistentRead=True).get("Item")
            if not item or item["state"] != "queued" or int(item["attempt"]) != message["attempt"]:
                continue
            token = hashlib.sha256(f"{message['job_id']}:{message['attempt']}".encode()).hexdigest()
            slot_key = None
            for slot in range(int(os.getenv("WORKER_CONCURRENCY", "2"))):
                candidate = {"pk": f"WORKER_SLOT#{slot}", "sk": "SLOT"}
                previous = table.get_item(Key=candidate, ConsistentRead=True).get("Item", {})
                if previous.get("token") == token:
                    slot_key = candidate
                    break
                try:
                    table.put_item(Item={**candidate, "token": token, "expires": int(time.time()) + 2100},
                        ConditionExpression="attribute_not_exists(pk) OR expires < :now",
                        ExpressionAttributeValues={":now": int(time.time())})
                    slot_key = candidate
                    break
                except table.meta.client.exceptions.ConditionalCheckFailedException:
                    pass
            if slot_key is None:
                raise RuntimeError("All render slots are occupied; leave this message for retry.")
            response = ecs.run_task(
                clientToken=token,
                startedBy=f"{message['job_id']}-a{message['attempt']}",
                cluster=os.environ["ECS_CLUSTER_ARN"],
                taskDefinition=os.environ["WORKER_TASK_DEFINITION_ARN"],
                launchType="FARGATE",
                count=1,
                networkConfiguration={
                    "awsvpcConfiguration": {
                        "subnets": os.environ["WORKER_SUBNET_IDS"].split(","),
                        "securityGroups": [os.environ["WORKER_SECURITY_GROUP_ID"]],
                        "assignPublicIp": "ENABLED",
                    }
                },
                overrides={
                    "containerOverrides": [
                        {
                            "name": "worker",
                            "command": ["python", "-m", "launchpad_worker.task", message["job_id"], str(message["attempt"])],
                        }
                    ]
                },
            )
            if response.get("failures"):
                raise RuntimeError(response["failures"])
            print(json.dumps({"job_id": message["job_id"], "event": "task_dispatched", "attempt": message["attempt"], "task_arn": response["tasks"][0]["taskArn"]}))
        except Exception as exc:
            print(json.dumps({"job_id": message["job_id"], "event": "dispatch_deferred", "error_type": type(exc).__name__}))
            failures.append({"itemIdentifier": record["messageId"]})
    return {"batchItemFailures": failures}
