"""AgentCore HTTP runtime. Only IAM-authorized backend callers can invoke it."""
import time
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from launchpad_api.store import store
from launchpad_api.audit import emit
from launchpad_agent.concierge import make_plan

app = FastAPI()


class Invocation(BaseModel):
    job_id: str = Field(pattern=r"^lp_[a-f0-9]{16}$")
    owner: str
    attempt: int = Field(ge=1)
    session_id: str = Field(min_length=33, max_length=128)


class AttemptStore:
    """Fence late/cancelled model responses out of newer production attempts."""
    def __init__(self, db, invocation):
        self.db, self.invocation = db, invocation

    def verify(self, job):
        i = self.invocation
        if job["attempt"] != i.attempt or job["state"] != "planning" or job.get("cancel_requested") or job.get("agent_session_id") != i.session_id:
            raise InterruptedError("This planning attempt is no longer active.")

    def get(self, job_id):
        job = self.db.get(job_id, self.invocation.owner)
        self.verify(job)
        return job

    def check(self, job_id):
        self.get(job_id)

    def mutate(self, job_id, fn):
        def fenced(job):
            self.verify(job)
            fn(job)
        return self.db.mutate(job_id, fenced, self.invocation.owner)


@app.get("/ping")
def ping():
    return {"status": "Healthy", "time_of_last_update": int(time.time())}


@app.post("/invocations")
def invoke(body: Invocation):
    scoped = AttemptStore(store, body)
    def begin(job):
        if job.get("agent_execution"):
            raise ValueError("This attempt already has a planning invocation.")
        job["agent_execution"] = {"status": "running", "session_id": body.session_id, "at": time.time()}
    try:
        scoped.mutate(body.job_id, begin)
    except (KeyError, ValueError, InterruptedError) as exc:
        raise HTTPException(409, str(exc)) from None
    emit(body.job_id, "agentcore_planning_started", session_id=body.session_id)
    try:
        plan = make_plan(scoped, body.job_id)
        scoped.mutate(body.job_id, lambda j: j["agent_execution"].update(status="completed"))
        return {"saved": True, "job_id": body.job_id, "scenes": len(plan["scenes"])}
    except Exception as exc:
        emit(body.job_id, "agentcore_planning_failed", error_type=type(exc).__name__)
        return {"saved": False, "error": str(exc)[:700] if isinstance(exc, ValueError) else f"{type(exc).__name__}: planning stopped; review the job trace."}
