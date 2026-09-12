import json
import uuid
from types import SimpleNamespace
import boto3
import pytest
from moto import mock_aws
from launchpad_agent.contracts import GenerationRequest
from launchpad_agent.concierge import fixture_plan
from launchpad_agent.policies import ProductionPolicy
from launchpad_api.store import DynamoStore, Store
from launchpad_worker.artifacts import checkpoint, restore
from launchpad_agent.runtime import AttemptStore, Invocation


def request():
    return GenerationRequest(website_url="fixture://northstar", authorization_confirmed=True,
        brief="Explain the research workspace with evidence.", idempotency_key=uuid.uuid4().hex)


@mock_aws
def test_dynamo_transaction_has_correct_types_and_one_idempotency_write(monkeypatch, tmp_path):
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("LAUNCHPAD_DYNAMODB_TABLE", "jobs-test")
    monkeypatch.setenv("LAUNCHPAD_DATA_DIR", str(tmp_path))
    boto3.client("dynamodb", region_name="us-east-1").create_table(TableName="jobs-test", BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[{"AttributeName": a, "AttributeType": t} for a,t in [("pk","S"),("sk","S"),("owner","S"),("created_at","N")]],
        KeySchema=[{"AttributeName":"pk","KeyType":"HASH"},{"AttributeName":"sk","KeyType":"RANGE"}],
        GlobalSecondaryIndexes=[{"IndexName":"OwnerCreatedIndex","KeySchema":[{"AttributeName":"owner","KeyType":"HASH"},{"AttributeName":"created_at","KeyType":"RANGE"}],"Projection":{"ProjectionType":"ALL"}}])
    db = DynamoStore()
    r = request()
    job = db.create(r, "alice")
    assert db.create(r, "alice")["id"] == job["id"]
    assert db.claim_by_id(job["id"], 1)
    assert db.claim_by_id(job["id"], 1) is None
    with pytest.raises(KeyError):
        db.get(job["id"], "bob")
    from infra.recovery import recover
    recover(db.table, job["id"], 1, "Stopped test worker; checkpoint preserved")
    assert db.get(job["id"])["state"] == "blocked"
    db.mutate(job["id"], lambda j: j.update(state="queued", attempt=2))
    recover(db.table, job["id"], 1, "Late old event")
    assert db.get(job["id"])["state"] == "queued"
    assert db.claim_by_id(job["id"], 2)


def test_policy_blocks_wrong_order_and_excess_tools(tmp_path):
    db = Store(tmp_path)
    job = db.create(request(), "alice")
    hooks = ProductionPolicy(db, job["id"])
    event = SimpleNamespace(tool_use={"name": "submit_storyboard"}, cancel_tool=False)
    hooks.before_tool(event)
    assert "Read the brief" in event.cancel_tool
    hooks.calls = 10
    event = SimpleNamespace(tool_use={"name": "inspect_authorized_site"}, cancel_tool=False)
    hooks.before_tool(event)
    assert "limit" in event.cancel_tool
    assert len(db.get(job["id"])["policy_receipts"]) == 2


def test_late_agent_cannot_mutate_new_attempt(tmp_path):
    db = Store(tmp_path)
    job = db.create(request(), "alice")
    sid = str(uuid.uuid4())
    db.mutate(job["id"], lambda j: j.update(state="planning", agent_session_id=sid))
    scoped = AttemptStore(db, Invocation(job_id=job["id"], owner="alice", attempt=1, session_id=sid))
    assert scoped.get(job["id"])
    db.mutate(job["id"], lambda j: j.update(attempt=2))
    with pytest.raises(InterruptedError):
        scoped.mutate(job["id"], lambda j: j.update(plan={"bad": True}))
    assert db.get(job["id"])["plan"] is None


@mock_aws
def test_checkpoint_restores_to_fresh_worker_and_checks_hash(monkeypatch, tmp_path):
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("LAUNCHPAD_ARTIFACT_BUCKET", "launchpad-test-recordings")
    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="launchpad-test-recordings")
    clip = tmp_path / "source.webm"
    clip.write_bytes(b"completed scene")
    saved = checkpoint(clip, tmp_path, "lp_abc", "fingerprint", [{"action":"click"}])
    root = tmp_path / "fresh-worker"
    restored = restore(saved, root, "lp_abc")
    from pathlib import Path
    assert Path(restored).read_bytes() == b"completed scene"
    assert json.loads(Path(restored).with_suffix(".events.json").read_text()) == [{"action":"click"}]
    with pytest.raises(ValueError, match="outside"):
        restore(saved, root, "lp_other")
    with pytest.raises(ValueError, match="integrity"):
        restore({**saved, "sha256":"wrong"}, root, "lp_abc")
