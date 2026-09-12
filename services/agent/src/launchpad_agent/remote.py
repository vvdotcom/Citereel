"""IAM-authenticated AgentCore invocation from the background worker."""
import json
import os
import uuid
import boto3
from botocore.config import Config
from launchpad_api.audit import emit


def remote_plan(db, job_id):
    job = db.get(job_id)
    session_id = str(uuid.uuid4())
    arn = os.environ["LAUNCHPAD_AGENTCORE_ARN"]
    db.mutate(job_id, lambda j: j.update(agent_runtime="agentcore", agent_session_id=session_id,
                                       agent_runtime_arn=arn, agent_execution=None))
    client = boto3.client("bedrock-agentcore", region_name=os.getenv("AWS_REGION"),
                         config=Config(connect_timeout=15, read_timeout=600, retries={"total_max_attempts": 1}))
    emit(job_id, "agentcore_invoked", session_id=session_id, attempt=job["attempt"])
    try:
        response = client.invoke_agent_runtime(agentRuntimeArn=arn, runtimeSessionId=session_id,
            contentType="application/json", accept="application/json",
            payload=json.dumps({"job_id": job_id, "owner": job["owner"], "attempt": job["attempt"], "session_id": session_id}).encode())
        result = json.loads(response["response"].read())
        if not result.get("saved"):
            raise ValueError(result.get("error", "AgentCore did not save a validated storyboard."))
        finished = db.get(job_id)
        if not finished.get("plan") or finished["attempt"] != job["attempt"]:
            raise ValueError("AgentCore returned without a current storyboard receipt.")
        emit(job_id, "agentcore_completed", session_id=session_id)
        return finished["plan"]
    finally:
        try:
            client.stop_runtime_session(agentRuntimeArn=arn, runtimeSessionId=session_id)
            emit(job_id, "agentcore_session_stopped", session_id=session_id)
        except Exception as exc:
            emit(job_id, "agentcore_session_stop_failed", error_type=type(exc).__name__)
