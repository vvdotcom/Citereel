"""Regression coverage for evidence review, selective updates and honest test personas."""

import copy
import time
from pathlib import Path

import pytest
from launchpad_agent.concierge import fixture_plan, validate_plan
from launchpad_agent.contracts import Storyboard
from launchpad_agent.grounding import claim_ledger
from launchpad_api.store import Store
from launchpad_worker import runner
from launchpad_worker.changes import compare_sources, recording_key
from test_core import client as client
from test_core import request


def test_static_aws_body_reveal_does_not_require_website_javascript():
    from launchpad_worker.capture import reveal_aws_documentation
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(java_script_enabled=False)
        page.set_content(
            "<html><head><style>body{display:none}</style></head><body>Visible source content</body></html>"
        )
        reveal_aws_documentation(page)
        assert page.locator("body").inner_text() == "Visible source content"
        browser.close()


def prepared(db, **kwargs):
    job = db.create(request(**kwargs), "alice", planner_mode="fixture")
    fixture_plan(db, job["id"])
    db.mutate(job["id"], lambda j: j.update(state="ready_for_review", plan_approved=True))
    return db.get(job["id"])


def test_paraphrase_is_not_automatically_verified(tmp_path):
    db = Store(tmp_path)
    j = prepared(db)
    j["plan"]["scenes"][0]["narration"] = "This product transforms every team into a market leader."
    ledger = claim_ledger(j["plan"], j["evidence"])
    assert ledger[0]["status"] == "source_matched"
    assert ledger[2]["status"] == "needs_review"
    assert not ledger[2]["matches"]


@pytest.mark.parametrize("field", ["title", "on_screen_copy", "narration"])
def test_invented_numeric_claim_is_rejected(tmp_path, field):
    db = Store(tmp_path)
    j = prepared(db)
    j["plan"]["scenes"][0][field] = "Save 99% of your costs."
    with pytest.raises(ValueError, match=r"numerical claim.*99%"):
        validate_plan(Storyboard.model_validate(j["plan"]), j["evidence"], j["request"])


def test_acknowledgment_and_fresh_version_required(client):
    api, db = client
    j = prepared(db)
    plan = copy.deepcopy(j["plan"])
    plan["scenes"][0]["narration"] = "Review research with context."
    db.mutate(
        j["id"], lambda x: x.update(plan=plan, state="awaiting_plan_approval", plan_approved=False)
    )
    j = db.get(j["id"])
    path = f"/v1/jobs/{j['id']}/decision"
    body = {"action": "approve_plan", "version": j["version"]}
    assert api.post(path, json=body).status_code == 409
    assert not db.get(j["id"])["plan_approved"]
    assert api.post(path, json={**body, "claims_reviewed": True}).status_code == 200
    assert api.post(path, json={**body, "claims_reviewed": True}).status_code == 409


def test_diff_preserves_source_identity_and_finds_only_affected_scenes(tmp_path):
    db = Store(tmp_path)
    j = prepared(db)
    fresh = copy.deepcopy(list(reversed(j["evidence"])))
    fresh[0]["excerpt"] += " New release note."
    diff = compare_sources(j, fresh)
    assert diff["affected_scenes"] == [3]
    assert diff["evidence"][0]["id"] == j["evidence"][2]["id"]
    assert diff["changes"][0]["kind"] == "changed"
    assert recording_key(j["plan"]["scenes"][0], j["evidence"]) == recording_key(
        j["plan"]["scenes"][0], diff["evidence"]
    )
    assert recording_key(j["plan"]["scenes"][2], j["evidence"]) != recording_key(
        j["plan"]["scenes"][2], diff["evidence"]
    )


def test_removed_page_and_whitespace_only_changes(tmp_path):
    db = Store(tmp_path)
    j = prepared(db)
    fresh = copy.deepcopy(j["evidence"][:-1])
    fresh[0]["excerpt"] = fresh[0]["excerpt"].replace(" ", "  ")
    proposal = compare_sources(j, fresh)
    assert proposal["affected_scenes"] == [3]
    assert len(proposal["changes"]) == 1 and proposal["changes"][0]["kind"] == "removed"


def test_update_check_does_not_invoke_model_or_capture(client, monkeypatch):
    api, db = client
    j = prepared(db)
    fresh = copy.deepcopy(j["evidence"])
    fresh[1]["excerpt"] += " Updated source text."
    monkeypatch.setattr(runner, "inspect_site", lambda *a: fresh)
    monkeypatch.setattr(runner, "make_plan", lambda *a: pytest.fail("Unauthorized model call"))
    monkeypatch.setattr(runner, "capture", lambda *a: pytest.fail("Unauthorized capture"))
    res = api.post(f"/v1/jobs/{j['id']}/changes", json={"version": j["version"]})
    assert res.status_code == 200
    runner.process(db.claim(), db)
    pending = db.get(j["id"])
    assert pending["state"] == "awaiting_changes_approval"
    assert pending["plan"] == j["plan"]
    assert pending["evidence"] == j["evidence"]
    proposal = pending["change_proposal"]
    assert proposal["affected_scenes"] == [2]
    response = api.post(
        f"/v1/jobs/{j['id']}/decision",
        json={"action": "approve_changes", "version": pending["version"]},
    )
    queued = response.json()
    assert response.status_code == 200 and queued["plan"] is None
    assert queued["revision_context"]["locked_scenes"] == {
        "0": j["plan"]["scenes"][0],
        "2": j["plan"]["scenes"][2],
    }
    assert queued["planner_mode"] == "bedrock" and not queued["plan_approved"]


def test_no_change_restores_approved_state(client, monkeypatch):
    api, db = client
    j = prepared(db)
    db.mutate(j["id"], lambda x: x.update(state="approved"))
    j = db.get(j["id"])
    monkeypatch.setattr(runner, "inspect_site", lambda *a: j["evidence"])
    api.post(f"/v1/jobs/{j['id']}/changes", json={"version": j["version"]})
    runner.process(db.claim(), db)
    done = db.get(j["id"])
    assert done["state"] == "approved"
    assert done["change_proposal"]["changes"] == []
    # Even a read-only cloud check needs a fresh dispatch identity, otherwise
    # ECS idempotency would return the previous (already stopped) task.
    assert done["attempt"] == j["attempt"] + 1


def test_worker_reuses_only_unchanged_recordings(tmp_path, monkeypatch):
    db = Store(tmp_path)
    j = prepared(db)
    cache = {}
    for index, scene in enumerate(j["plan"]["scenes"]):
        clip = tmp_path / f"approved-{index}.webm"
        clip.write_bytes(b"prior recording")
        cache[recording_key(scene, j["evidence"], j["request"], index)] = str(clip)
    fresh = copy.deepcopy(j["evidence"])
    fresh[1]["excerpt"] += " New text."
    db.mutate(
        j["id"],
        lambda x: x.update(
            state="queued",
            evidence=fresh,
            recordings=cache,
            artifacts=[{"attempt": 1, "qa": {"sha256": "prior"}}],
            attempt=2,
        ),
    )
    captured = []

    def capture(job, folder, check, **kwargs):
        captured.append(job["plan"]["scenes"][0]["page_id"])
        path = folder / "new.webm"
        path.write_bytes(b"new recording")
        return [str(path)], [{"action": "goto"}]

    def render(job, folder, clips, check, stage):
        for state in ("narrating", "rendering", "quality_check"):
            stage(state, "Test double, not a real render.")
        assert len(clips) == 3
        return {"sha256": "new-test-double"}

    monkeypatch.setattr(runner, "capture", capture)
    monkeypatch.setattr(runner, "render", render)
    runner.process(db.claim(), db)
    done = db.get(j["id"])
    assert done["state"] == "ready_for_review", done["error"]
    assert captured == [j["plan"]["scenes"][1]["page_id"]]
    assert done["capture_reuse"] == {"reused": 2, "recorded": 1}
    assert done["artifacts"][0]["qa"]["sha256"] == "prior"
    assert all(Path(path).read_bytes() == b"prior recording" for path in cache.values())


def test_simulated_trials_never_invent_real_outcomes(client):
    api, db = client
    j = prepared(db)
    db.mutate(j["id"], lambda x: x.update(artifacts=[{"created_at": time.time()}]))
    j = db.get(j["id"])
    response = api.post(
        f"/v1/jobs/{j['id']}/trial",
        json={"participant": "Maya Chen", "version": j["version"], "notes": "Synthetic test."},
    )
    assert response.status_code == 200
    session = response.json()["test_sessions"][0]
    assert session["simulated"] is True
    assert session["manual_baseline_seconds"] is None and session["would_use"] is None
    assert session["production_elapsed_seconds"] >= 0
    assert "Fictional" in session["disclosure"]


def test_locked_scene_and_count_contract(tmp_path):
    from launchpad_agent.concierge import validate_revision

    db = Store(tmp_path)
    j = prepared(db)
    context = {
        "affected_scenes": [2],
        "previous_plan": j["plan"],
        "locked_scenes": {"0": j["plan"]["scenes"][0], "2": j["plan"]["scenes"][2]},
    }
    with pytest.raises(ValueError, match="requested rewrite"):
        validate_revision(j["plan"], {"previous_plan": j["plan"]})
    changed = copy.deepcopy(j["plan"])
    changed["scenes"][1]["narration"] = "Revised affected scene."
    validate_revision(changed, context)
    changed["scenes"][0]["narration"] = "Unexpected unrelated rewrite."
    with pytest.raises(ValueError, match="unaffected"):
        validate_revision(changed, context)
    with pytest.raises(ValueError, match="scene count"):
        validate_revision({"scenes": j["plan"]["scenes"][:-1]}, {**context, "locked_scenes": {}})


def test_edit_cannot_leave_stale_approval(client):
    api, db = client
    j = prepared(db)
    res = api.put(
        f"/v1/jobs/{j['id']}/storyboard", json={"version": j["version"], "plan": j["plan"]}
    )
    assert res.status_code == 200
    edited = res.json()
    assert edited["state"] == "awaiting_plan_approval" and not edited["plan_approved"]


def test_failed_check_preserves_export_and_can_retry(client, monkeypatch):
    api, db = client
    j = prepared(db)
    db.mutate(
        j["id"], lambda x: x.update(artifacts=[{"attempt": 1, "qa": {"sha256": "approved-export"}}])
    )
    j = db.get(j["id"])

    def unavailable(*args):
        raise ValueError("Robots policy could not be verified.")

    monkeypatch.setattr(runner, "inspect_site", unavailable)
    api.post(f"/v1/jobs/{j['id']}/changes", json={"version": j["version"]})
    runner.process(db.claim(), db)
    failed = db.get(j["id"])
    assert failed["state"] == "blocked"
    assert failed["artifacts"] == j["artifacts"] and failed["plan"] == j["plan"]
    res = api.post(
        f"/v1/jobs/{j['id']}/decision", json={"action": "retry", "version": failed["version"]}
    )
    assert res.status_code == 200
    monkeypatch.setattr(runner, "inspect_site", lambda *a: j["evidence"])
    runner.process(db.claim(), db)
    assert db.get(j["id"])["state"] == "ready_for_review"


def test_change_proposal_is_owner_scoped_and_dismissible(client, monkeypatch):
    api, db = client
    j = prepared(db)
    fresh = copy.deepcopy(j["evidence"])
    fresh[0]["excerpt"] += " New source."
    monkeypatch.setattr(runner, "inspect_site", lambda *a: fresh)
    api.cookies.clear()
    api.cookies.set("launchpad_session", db.session("bob"))
    assert (
        api.post(f"/v1/jobs/{j['id']}/changes", json={"version": j["version"]}).status_code == 404
    )
    api.cookies.clear()
    api.cookies.set("launchpad_session", db.session("alice"))
    api.post(f"/v1/jobs/{j['id']}/changes", json={"version": j["version"]})
    runner.process(db.claim(), db)
    pending = db.get(j["id"])
    response = api.post(
        f"/v1/jobs/{j['id']}/decision",
        json={"action": "dismiss_changes", "version": pending["version"]},
    )
    assert response.status_code == 200
    assert response.json()["evidence"] == j["evidence"]
    assert response.json()["change_proposal"]["decision"] == "dismissed"
