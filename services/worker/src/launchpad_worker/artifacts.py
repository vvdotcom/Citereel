"""Persist completed render artifacts outside the ephemeral Fargate filesystem."""

import os
import hashlib
import json
from pathlib import Path

import boto3
from botocore.exceptions import ClientError


def checkpoint(clip, root, job_id, key, receipts):
    """Save each completed capture before moving on, so a stopped task can resume."""
    bucket = os.getenv("LAUNCHPAD_ARTIFACT_BUCKET")
    if not bucket:
        return None
    path = Path(clip)
    object_key = f"jobs/{job_id}/recordings/{key}/{path.name}"
    client = boto3.client("s3", region_name=os.getenv("AWS_REGION"))
    client.upload_file(str(path), bucket, object_key)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"key": object_key, "sha256": sha, "events": receipts}


def restore(recording, root, job_id):
    bucket = os.getenv("LAUNCHPAD_ARTIFACT_BUCKET")
    if not bucket or not recording:
        return None
    key = recording["key"]
    path = (root / key).resolve()
    if not key.startswith(f"jobs/{job_id}/recordings/") or not path.is_relative_to(root.resolve()):
        raise ValueError("Recording checkpoint is outside this production.")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        boto3.client("s3", region_name=os.getenv("AWS_REGION")).download_file(bucket, key, str(path))
    except ClientError as exc:
        if exc.response["Error"]["Code"] in {"404", "NoSuchKey"}:
            return None
        raise
    if hashlib.sha256(path.read_bytes()).hexdigest() != recording["sha256"]:
        raise ValueError("Recording checkpoint failed its integrity check.")
    path.with_suffix(".events.json").write_text(json.dumps(recording["events"]), encoding="utf-8")
    return str(path)


def publish(folder: Path, prefix: str):
    bucket = os.getenv("LAUNCHPAD_ARTIFACT_BUCKET")
    if not bucket:
        return
    client = boto3.client("s3", region_name=os.getenv("AWS_REGION"))
    for path in folder.rglob("*"):
        if path.is_file():
            client.upload_file(str(path), bucket, f"{prefix}/{path.relative_to(folder).as_posix()}")
