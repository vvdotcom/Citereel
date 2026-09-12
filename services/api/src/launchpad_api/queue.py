"""Queue handoff used in cloud mode; local mode keeps the existing worker loop."""

import json
import os

import boto3
from .audit import emit


def enqueue(job):
    url = os.getenv("LAUNCHPAD_QUEUE_URL")
    if not url:
        return
    boto3.client("sqs", region_name=os.getenv("AWS_REGION")).send_message(
        QueueUrl=url,
        MessageBody=json.dumps({"job_id": job["id"], "attempt": job["attempt"]}),
    )
    emit(job["id"], "queue_sent", attempt=job["attempt"])
