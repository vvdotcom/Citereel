"""Policy decisions persisted with the job and emitted as structured cloud logs."""
import hashlib
import json
import os
import time
from contextlib import contextmanager
from urllib.parse import quote


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def emit(job_id, event, **fields):
    print(json.dumps({"service": "launchpad", "job_id": job_id, "event": event, "at": time.time(), **fields}), flush=True)


def append_policy(job, action, phase, outcome, detail):
    entry = {"action": action, "phase": phase, "outcome": outcome, "detail": detail[:700],
             "at": time.time(), "attempt": job["attempt"], "policy_version": "2026-09-09",
             "plan_sha256": digest(job["plan"]) if job.get("plan") else None}
    job.setdefault("policy_receipts", []).append(entry)
    return entry


def policy(db, job_id, action, phase, outcome="passed", detail="Policy satisfied"):
    db.mutate(job_id, lambda j: append_policy(j, action, phase, outcome, detail))
    emit(job_id, "policy", action=action, phase=phase, outcome=outcome)


@contextmanager
def checked_action(db, job_id, action, detail):
    db.check(job_id)
    policy(db, job_id, action, "before", detail=detail)
    started = time.monotonic()
    try:
        yield
        db.check(job_id)
    except Exception as exc:
        policy(db, job_id, action, "after", "blocked", type(exc).__name__)
        raise
    else:
        policy(db, job_id, action, "after", detail="Completed and persisted")
        emit(job_id, "action_completed", action=action, elapsed_seconds=round(time.monotonic()-started, 2))


def observability(job):
    region = os.getenv("AWS_REGION", "us-east-1")
    group = os.getenv("LAUNCHPAD_WORKER_LOG_GROUP")
    result = {"job_id": job["id"], "runtime": job.get("agent_runtime", "local"),
              "session_id": job.get("agent_session_id"), "aws_console_requires_operator_login": True}
    if group:
        encoded = quote(quote(group, safe=""), safe="").replace("%", "$")
        result["worker_logs"] = f"https://{region}.console.aws.amazon.com/cloudwatch/home?region={region}#logsV2:log-groups/log-group/{encoded}"
    dashboard = os.getenv("LAUNCHPAD_DASHBOARD")
    if dashboard:
        result["dashboard"] = f"https://{region}.console.aws.amazon.com/cloudwatch/home?region={region}#dashboards/dashboard/{quote(dashboard)}"
    if job.get("agent_runtime") == "agentcore":
        result["agent_console"] = f"https://{region}.console.aws.amazon.com/cloudwatch/home?region={region}#gen-ai-observability"
    return result
