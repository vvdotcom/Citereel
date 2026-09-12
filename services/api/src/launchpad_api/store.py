"""Transactional job queue and sessions. No model work occurs while a database transaction is held."""

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

import boto3
from boto3.dynamodb.conditions import Key
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError

from .settings import DAILY_JOB_LIMIT, DATA

ACTIVE = {
    "queued",
    "inspecting",
    "researching",
    "planning",
    "capturing",
    "narrating",
    "rendering",
    "quality_check",
}
UTC_DAY_SECONDS = 24 * 60 * 60
EDGES = {
    "queued": {"inspecting", "narrating"},
    "inspecting": {"researching"},
    "researching": {"planning"},
    "planning": {"capturing", "awaiting_plan_approval"},
    "awaiting_plan_approval": {"queued"},
    "awaiting_changes_approval": {"queued"},
    "capturing": {"narrating"},
    "narrating": {"rendering"},
    "rendering": {"quality_check"},
    "quality_check": {"ready_for_review"},
    "ready_for_review": {"approved", "queued"},
    "approved": {"queued"},
    "blocked": {"queued"},
    "failed": {"queued"},
    "cancelled": set(),
}


class Store:
    def __init__(self, root=DATA):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "launchpad.sqlite3"
        with self.connection() as db:
            db.executescript("""PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, owner TEXT, state TEXT, idem TEXT, payload TEXT, lease REAL DEFAULT 0, UNIQUE(owner,idem));
                CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE,password TEXT);
                CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,owner TEXT,expires REAL);""")

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def create(self, request, owner, planner_mode="bedrock", claim_immediately=False):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT payload FROM jobs WHERE owner=? AND idem=?",
                (owner, request.idempotency_key),
            ).fetchone()
            if existing:
                return json.loads(existing[0])
            now = time.time()
            day_start = now - now % UTC_DAY_SECONDS
            daily_count = db.execute(
                "SELECT count(*) FROM jobs WHERE owner=? AND CAST(json_extract(payload, '$.created_at') AS REAL)>=?",
                (owner, day_start),
            ).fetchone()[0]
            if daily_count >= DAILY_JOB_LIMIT:
                raise ValueError(
                    f"Daily production limit reached ({DAILY_JOB_LIMIT} per UTC day). Try again after midnight UTC."
                )
            if (
                db.execute(
                    "SELECT count(*) FROM jobs WHERE owner=? AND state IN ('queued','inspecting','researching','planning','capturing','narrating','rendering','quality_check')",
                    (owner,),
                ).fetchone()[0]
                >= 2
            ):
                raise ValueError("Two productions are already active. Wait or cancel one.")
            job = {
                "id": "lp_" + uuid.uuid4().hex[:16],
                "owner": owner,
                "state": "queued",
                "request": request.model_dump(),
                "created_at": now,
                "updated_at": now,
                "version": 1,
                "attempt": 1,
                "timeline": [],
                "evidence": [],
                "plan": None,
                "approvals": [],
                "artifacts": [],
                "error": None,
                "cancel_requested": False,
                "tool_receipts": [],
                "claim_ledger": [],
                "trace": [
                    {
                        "component": "api",
                        "event": "job_created",
                        "detail": "Production accepted with an idempotency key.",
                        "at": time.time(),
                    }
                ],
                "budget": {"tool_calls": 10, "planning_tokens": 45000},
                "planner_mode": planner_mode,
            }
            job["timeline"].append(self.event("queued", "Production saved to the durable queue."))
            db.execute(
                "INSERT INTO jobs(id,owner,state,idem,payload,lease) VALUES(?,?,?,?,?,?)",
                (
                    job["id"],
                    owner,
                    "queued",
                    request.idempotency_key,
                    json.dumps(job),
                    time.time() + 90 if claim_immediately else 0,
                ),
            )
        return job

    @staticmethod
    def event(stage, detail):
        return {"stage": stage, "detail": detail, "at": time.time()}

    def get(self, job_id, owner=None):
        with self.connection() as db:
            row = db.execute("SELECT payload,owner FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row or (owner is not None and row["owner"] != owner):
            raise KeyError("Job not found")
        return json.loads(row["payload"])

    def list(self, owner):
        with self.connection() as db:
            return [
                json.loads(x[0])
                for x in db.execute(
                    "SELECT payload FROM jobs WHERE owner=? ORDER BY rowid DESC LIMIT 100", (owner,)
                )
            ]

    def mutate(self, job_id, fn, owner=None):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT payload,owner FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row or (owner is not None and row["owner"] != owner):
                raise KeyError("Job not found")
            job = json.loads(row[0])
            previous_state = job["state"]
            fn(job)
            if previous_state not in ACTIVE and job["state"] in ACTIVE:
                active_count = db.execute(
                    "SELECT count(*) FROM jobs WHERE owner=? AND state IN ('queued','inspecting','researching','planning','capturing','narrating','rendering','quality_check')",
                    (row["owner"],),
                ).fetchone()[0]
                if active_count >= 2:
                    raise ValueError("Two productions are already active. Wait or cancel one.")
            job["version"] += 1
            job["updated_at"] = time.time()
            db.execute(
                "UPDATE jobs SET state=?,payload=? WHERE id=?",
                (job["state"], json.dumps(job), job_id),
            )
        return job

    def stage(self, job_id, state, detail, **updates):
        def change(j):
            if j["cancel_requested"]:
                raise InterruptedError("Production cancelled")
            if (
                state != j["state"]
                and state not in EDGES.get(j["state"], set())
                and state not in {"failed", "blocked", "cancelled"}
            ):
                raise ValueError(f"Invalid transition {j['state']} -> {state}")
            j.update(updates)
            j["state"] = state
            j["timeline"].append(self.event(state, detail))
            j.setdefault("trace", []).append(
                {"component": "worker", "event": state, "detail": detail, "at": time.time()}
            )

        return self.mutate(job_id, change)

    def check(self, job_id):
        if self.get(job_id)["cancel_requested"]:
            raise InterruptedError("Production cancelled")

    def claim(self):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            for row in db.execute(
                "SELECT id,payload FROM jobs WHERE lease>0 AND lease<? AND state NOT IN ('ready_for_review','approved','cancelled','failed','blocked','awaiting_plan_approval','awaiting_changes_approval')",
                (time.time(),),
            ).fetchall():
                j = json.loads(row["payload"])
                j.update(
                    state="blocked",
                    error="Worker stopped before completion. Retry to resume saved artifacts.",
                    version=j["version"] + 1,
                    updated_at=time.time(),
                )
                j["timeline"].append(self.event("blocked", j["error"]))
                db.execute(
                    "UPDATE jobs SET state=?,payload=?,lease=0 WHERE id=?",
                    ("blocked", json.dumps(j), j["id"]),
                )
            row = db.execute(
                "SELECT id,payload FROM jobs WHERE state='queued' AND lease=0 ORDER BY rowid LIMIT 1"
            ).fetchone()
            if not row:
                return None
            db.execute("UPDATE jobs SET lease=? WHERE id=?", (time.time() + 90, row["id"]))
            return json.loads(row["payload"])

    def heartbeat(self, job_id):
        with self.connection() as db:
            db.execute("UPDATE jobs SET lease=? WHERE id=?", (time.time() + 90, job_id))

    def release(self, job_id):
        with self.connection() as db:
            db.execute("UPDATE jobs SET lease=0 WHERE id=?", (job_id,))

    def claim_by_id(self, job_id, attempt):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT payload FROM jobs WHERE id=? AND state='queued' AND lease=0", (job_id,)
            ).fetchone()
            if not row:
                return None
            job = json.loads(row[0])
            if job["attempt"] != attempt:
                return None
            db.execute("UPDATE jobs SET lease=? WHERE id=?", (time.time() + 90, job_id))
            return job

    def session(self, owner):
        token = secrets.token_urlsafe(32)
        with self.connection() as db:
            db.execute(
                "INSERT INTO sessions VALUES(?,?,?)",
                (hashlib.sha256(token.encode()).hexdigest(), owner, time.time() + 7 * 86400),
            )
        return token

    def owner(self, token):
        with self.connection() as db:
            row = db.execute(
                "SELECT owner FROM sessions WHERE token=? AND expires>?",
                (hashlib.sha256(token.encode()).hexdigest(), time.time()),
            ).fetchone()
        if not row:
            raise PermissionError("Please sign in again.")
        return row[0]

    def register_user(self, email, password):
        salt = secrets.token_hex(16)
        user = uuid.uuid4().hex
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 300000).hex()
        try:
            with self.connection() as db:
                db.execute("INSERT INTO users VALUES(?,?,?)", (user, email, salt + ":" + digest))
        except sqlite3.IntegrityError:
            raise ValueError("An account already exists for this email.") from None
        return user

    def authenticate(self, email, password):
        with self.connection() as db:
            row = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        salt, expected = row["password"].split(":") if row else ("missing", "missing")
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 300000).hex()
        if not hmac.compare_digest(actual, expected):
            raise PermissionError("Email or password is incorrect.")
        return row["id"]

    def end_session(self, token):
        with self.connection() as db:
            db.execute("DELETE FROM sessions WHERE token=?", (hashlib.sha256(token.encode()).hexdigest(),))


class DynamoStore(Store):
    """DynamoDB implementation used by the scale-to-zero API and workers.

    Jobs remain a single JSON document so the existing approval, revision and
    trace contract is identical to local SQLite. Conditional writes make a
    stale browser request or duplicate SQS message harmless.
    """

    def __init__(self):
        self.root = Path(os.getenv("LAUNCHPAD_DATA_DIR", "/tmp/launchpad-data"))
        self.root.mkdir(parents=True, exist_ok=True)
        self.table_name = os.environ["LAUNCHPAD_DYNAMODB_TABLE"]
        self.table = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION")).Table(
            self.table_name
        )
        # The resource client installs native-value serializers. Use a separate
        # low-level client for explicitly serialized transaction attributes.
        self.client = boto3.client("dynamodb", region_name=os.getenv("AWS_REGION"))
        self.serializer = TypeSerializer()

    @staticmethod
    def _key(prefix, value, sort):
        return {"pk": f"{prefix}#{value}", "sk": sort}

    def _job_item(self, job, owner):
        return {
            **self._key("JOB", job["id"], "JOB"),
            "entity": "job",
            "owner": owner,
            "created_at": int(job["created_at"] * 1000),
            "state": job["state"],
            "attempt": job["attempt"],
            "version": job["version"],
            "lease": 0,
            "payload": json.dumps(job),
        }

    def _decode(self, result):
        if not result or "Item" not in result:
            return None
        return json.loads(result["Item"]["payload"])

    def _transaction_item(self, item):
        return {key: self.serializer.serialize(value) for key, value in item.items()}

    def create(self, request, owner, planner_mode="bedrock", claim_immediately=False):
        idem = self.table.get_item(Key=self._key("IDEM", f"{owner}#{request.idempotency_key}", "IDEM")).get("Item")
        if idem:
            return self.get(idem["job_id"], owner)
        active = [j for j in self.list(owner) if j["state"] in ACTIVE]
        if len(active) >= 2:
            raise ValueError("Two productions are already active. Wait or cancel one.")
        now = time.time()
        job = {
            "id": "lp_" + uuid.uuid4().hex[:16], "owner": owner, "state": "queued",
            "request": request.model_dump(), "created_at": now, "updated_at": now,
            "version": 1, "attempt": 1, "timeline": [], "evidence": [], "plan": None,
            "approvals": [], "artifacts": [], "error": None, "cancel_requested": False,
            "tool_receipts": [], "claim_ledger": [],
            "trace": [{"component": "api", "event": "job_created", "detail": "Production accepted with an idempotency key.", "at": now}],
            "budget": {"tool_calls": 10, "planning_tokens": 45000}, "planner_mode": planner_mode,
        }
        job["timeline"].append(self.event("queued", "Production saved to the durable queue."))
        day = time.strftime("%Y-%m-%d", time.gmtime(now))
        counter = self._key("LIMIT", f"{owner}#{day}", "DAY")
        idem_key = self._key("IDEM", f"{owner}#{request.idempotency_key}", "IDEM")
        try:
            self.client.transact_write_items(
                TransactItems=[
                    {"Update": {"TableName": self.table_name, "Key": self._transaction_item(counter), "UpdateExpression": "SET job_count = if_not_exists(job_count, :zero) + :one, #ttl = :ttl", "ConditionExpression": "attribute_not_exists(job_count) OR job_count < :limit", "ExpressionAttributeNames": {"#ttl": "ttl"}, "ExpressionAttributeValues": {":zero": {"N": "0"}, ":one": {"N": "1"}, ":limit": {"N": str(DAILY_JOB_LIMIT)}, ":ttl": {"N": str(int(now) + 172800)}}}},
                    {"Put": {"TableName": self.table_name, "Item": self._transaction_item(self._job_item(job, owner))}},
                    {"Put": {"TableName": self.table_name, "Item": self._transaction_item({**idem_key, "job_id": job["id"], "ttl": int(now) + 172800}), "ConditionExpression": "attribute_not_exists(pk)"}},
                ]
            )
        except ClientError as exc:
            existing = self.table.get_item(Key=idem_key).get("Item")
            if existing:
                return self.get(existing["job_id"], owner)
            if exc.response.get("Error", {}).get("Code") == "TransactionCanceledException":
                raise ValueError(f"Daily production limit reached ({DAILY_JOB_LIMIT} per UTC day). Try again after midnight UTC.") from None
            raise
        return job

    def get(self, job_id, owner=None):
        job = self._decode(self.table.get_item(Key=self._key("JOB", job_id, "JOB"), ConsistentRead=True))
        if not job or (owner is not None and job["owner"] != owner):
            raise KeyError("Job not found")
        return job

    def list(self, owner):
        result = self.table.query(
            IndexName="OwnerCreatedIndex", KeyConditionExpression=Key("owner").eq(owner),
            ScanIndexForward=False, Limit=100,
        )
        return [json.loads(item["payload"]) for item in result.get("Items", [])]

    def mutate(self, job_id, fn, owner=None):
        for _ in range(5):
            job = self.get(job_id, owner)
            previous_state = job["state"]
            fn(job)
            if previous_state not in ACTIVE and job["state"] in ACTIVE:
                if len([j for j in self.list(job["owner"]) if j["state"] in ACTIVE]) >= 2:
                    raise ValueError("Two productions are already active. Wait or cancel one.")
            previous_version = job["version"]
            job["version"] += 1
            job["updated_at"] = time.time()
            try:
                self.table.update_item(
                    Key=self._key("JOB", job_id, "JOB"),
                    UpdateExpression="SET #payload=:payload, #state=:state, #version=:version, #attempt=:attempt",
                    ConditionExpression="#version=:previous",
                    ExpressionAttributeNames={"#payload": "payload", "#state": "state", "#version": "version", "#attempt": "attempt"},
                    ExpressionAttributeValues={":payload": json.dumps(job), ":state": job["state"], ":version": job["version"], ":attempt": job["attempt"], ":previous": previous_version},
                )
                return job
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                    raise
        raise ValueError("This job changed. Refresh and try again.")

    def claim_by_id(self, job_id, attempt):
        job = self.get(job_id)
        if job["state"] != "queued" or job["attempt"] != attempt:
            return None
        try:
            self.table.update_item(
                Key=self._key("JOB", job_id, "JOB"),
                UpdateExpression="SET lease=:lease",
                ConditionExpression="#state=:queued AND #attempt=:attempt AND lease=:empty",
                ExpressionAttributeNames={"#state": "state", "#attempt": "attempt"},
                ExpressionAttributeValues={":lease": int(time.time()) + 90, ":queued": "queued", ":attempt": attempt, ":empty": 0},
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return None
            raise
        return job

    def heartbeat(self, job_id):
        self.table.update_item(Key=self._key("JOB", job_id, "JOB"), UpdateExpression="SET lease=:lease", ExpressionAttributeValues={":lease": int(time.time()) + 90})

    def release(self, job_id):
        self.table.update_item(Key=self._key("JOB", job_id, "JOB"), UpdateExpression="SET lease=:lease", ExpressionAttributeValues={":lease": 0})

    def session(self, owner):
        token = secrets.token_urlsafe(32)
        key = self._key("SESSION", hashlib.sha256(token.encode()).hexdigest(), "SESSION")
        self.table.put_item(Item={**key, "owner": owner, "expires": int(time.time()) + 604800, "ttl": int(time.time()) + 604800})
        return token

    def owner(self, token):
        item = self.table.get_item(Key=self._key("SESSION", hashlib.sha256(token.encode()).hexdigest(), "SESSION")).get("Item")
        if not item or item["expires"] <= int(time.time()):
            raise PermissionError("Please sign in again.")
        return item["owner"]

    def register_user(self, email, password):
        user = uuid.uuid4().hex
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 300000).hex()
        email_key = self._key("EMAIL", hashlib.sha256(email.encode()).hexdigest(), "EMAIL")
        try:
            self.table.put_item(Item={**email_key, "owner": user}, ConditionExpression="attribute_not_exists(pk)")
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                raise ValueError("An account already exists for this email.") from None
            raise
        self.table.put_item(Item={**self._key("USER", user, "PROFILE"), "email": email, "password": salt + ":" + digest})
        return user

    def authenticate(self, email, password):
        email_key = self._key("EMAIL", hashlib.sha256(email.encode()).hexdigest(), "EMAIL")
        mapped = self.table.get_item(Key=email_key).get("Item")
        profile = self.table.get_item(Key=self._key("USER", mapped["owner"], "PROFILE")).get("Item") if mapped else None
        salt, expected = profile["password"].split(":") if profile else ("missing", "missing")
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 300000).hex()
        if not hmac.compare_digest(actual, expected):
            raise PermissionError("Email or password is incorrect.")
        return mapped["owner"]

    def end_session(self, token):
        self.table.delete_item(Key=self._key("SESSION", hashlib.sha256(token.encode()).hexdigest(), "SESSION"))


store = DynamoStore() if os.getenv("LAUNCHPAD_STORE") == "dynamodb" else Store()
