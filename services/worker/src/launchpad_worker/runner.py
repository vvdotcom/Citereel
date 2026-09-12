import json
import threading
import time
from pathlib import Path

from launchpad_agent.concierge import claim_ledger, fixture_plan, make_plan
from launchpad_api.store import store
from launchpad_api.audit import checked_action, policy, emit, digest

from .capture import capture
from .artifacts import publish, checkpoint, restore
from .changes import compare_sources, recording_key
from .network import inspect_site
from .render import render


def cached_capture_receipts(clip, root):
    """Keep original interaction provenance when an export reuses footage."""
    path = Path(clip).resolve()
    if not path.is_relative_to(root.resolve()):
        return []
    sidecar = path.with_suffix(".events.json")
    if sidecar.is_file():
        return json.loads(sidecar.read_text(encoding="utf-8"))
    # Earlier recordings stored all scene events together in the attempt folder.
    aggregate = path.parent.parent / "capture-events.json"
    shot = path.parent.name.removeprefix("shot-")
    if shot.isdigit() and aggregate.is_file():
        return [
            event
            for event in json.loads(aggregate.read_text(encoding="utf-8"))
            if event.get("scene") == int(shot) and event.get("action") != "reuse"
        ]
    return []


def process(job, db=store, fixture=False):
    job_id = job["id"]
    folder = db.root / "jobs" / job_id / f"attempt-{job['attempt']}"
    folder.mkdir(parents=True, exist_ok=True)
    stop = threading.Event()

    def heartbeat():
        while not stop.wait(20):
            db.heartbeat(job_id)

    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()

    def check():
        db.check(job_id)

    try:
        emit(job_id, "worker_started", attempt=job["attempt"])
        if not job["request"].get("authorization_confirmed"):
            policy(db, job_id, "capture_authorization", "before", "blocked", "Authorization is required")
            raise ValueError("Capture authorization is required.")
        db.stage(job_id, "inspecting", "Inspecting the authorized website.")
        if job.get("operation") == "check_changes":
            fresh = inspect_site(job["request"]["website_url"], [s["url"] for s in job["evidence"]])
            proposal = compare_sources(job, fresh)

            def save_check(j):
                j.update(
                    change_proposal=proposal,
                    operation=None,
                    state="awaiting_changes_approval"
                    if proposal["changes"]
                    else j.get("resume_state", "ready_for_review"),
                )
                j["timeline"].append(
                    db.event(
                        j["state"],
                        f"Website check: {len(proposal['changes'])} changed pages; {len(proposal['affected_scenes'])} affected scenes.",
                    )
                )

            db.mutate(job_id, save_check)
            return
        db.stage(job_id, "researching", "Gathering official page evidence.")
        db.stage(job_id, "planning", "Preparing a grounded storyboard.")
        current = db.get(job_id)
        if not current.get("plan"):
            if not fixture and not current.get("evidence"):
                evidence = inspect_site(current["request"]["website_url"])
                db.mutate(job_id, lambda j: j.update(evidence=evidence))
            with checked_action(db, job_id, "storyboard", "Authorized brief; bounded model and tool calls; evidence validation required"):
                if not fixture and __import__("os").getenv("LAUNCHPAD_AGENTCORE_ARN"):
                    from launchpad_agent.remote import remote_plan
                    remote_plan(db, job_id)
                else:
                    (fixture_plan if fixture else make_plan)(db, job_id)
        current = db.get(job_id)
        ledger = claim_ledger(current["plan"], current["evidence"])
        db.mutate(job_id, lambda j: j.update(claim_ledger=ledger))
        needs_review = any(c["status"] == "needs_review" for c in ledger)
        if (current["request"]["review_plan"] or needs_review) and not current.get("plan_approved"):
            policy(db, job_id, "capture_approval", "before", "awaiting_human", "Review the storyboard and its cited evidence")
            db.stage(
                job_id,
                "awaiting_plan_approval",
                "Review scene copy, narration and sources before recording.",
            )
            return
        policy(db, job_id, "capture_approval", "before", detail="Approved plan or creator-authorized automatic capture; evidence attribution checked")
        db.stage(job_id, "capturing", "Recording the inspected pages in an isolated browser.")
        current = db.get(job_id)
        recordings = current.get("recordings", {})
        clips = []
        events = []
        reused = 0
        resource_cache = {}
        for index, scene in enumerate(current["plan"]["scenes"]):
            check()
            db.stage(
                job_id,
                "capturing",
                f"Preparing recording {index + 1} of {len(current['plan']['scenes'])}. Public-site crawl delays are respected.",
            )
            key = recording_key(scene, current["evidence"], current["request"], index)
            cached = recordings.get(key)
            if not cached or not Path(cached).is_file():
                cached = restore(current.get("recording_checkpoints", {}).get(key), db.root, job_id)
            if cached and Path(cached).is_file():
                clips.append(cached)
                reused += 1
                events.append({"scene": index + 1, "action": "reuse", "page_id": scene["page_id"]})
                events.extend(
                    {**event, "scene": index + 1, "reused": True}
                    for event in cached_capture_receipts(cached, db.root)
                )
                policy(db, job_id, "reuse_recording", "after", detail=f"Scene {index + 1}: reused matching capture with provenance")
            else:
                scene_folder = folder / f"shot-{index + 1}"
                scene_folder.mkdir(parents=True, exist_ok=True)
                policy(db, job_id, "capture_scene", "before", detail=f"Scene {index + 1}: bounded actions on inspected page {scene['page_id']}")
                captured, receipts = capture(
                    {
                        **current,
                        "plan": {"scenes": [scene]},
                        "scene_offset": index,
                        "scene_duration_seconds": current["request"]["duration_seconds"]
                        / len(current["plan"]["scenes"]),
                    },
                    scene_folder,
                    check,
                    resource_cache=resource_cache,
                )
                clips.append(captured[0])
                recordings[key] = captured[0]
                Path(captured[0]).with_suffix(".events.json").write_text(
                    json.dumps(receipts, indent=2), encoding="utf-8"
                )
                events.extend({**event, "scene": index + 1} for event in receipts)
                db.mutate(job_id, lambda j: j.update(recordings=dict(recordings)))
                saved = checkpoint(captured[0], db.root, job_id, key, receipts)
                if saved:
                    db.mutate(job_id, lambda j: j.setdefault("recording_checkpoints", {}).update({key: saved}))
                policy(db, job_id, "capture_scene", "after", detail=f"Scene {index + 1}: recording and capture receipts saved")
        db.mutate(
            job_id,
            lambda j: j.update(
                clips=clips,
                capture_events=events,
                capture_reuse={"reused": reused, "recorded": len(clips) - reused},
            ),
        )
        (folder / "capture-events.json").write_text(json.dumps(events, indent=2), encoding="utf-8")
        with checked_action(db, job_id, "narrate_render_qa", "Validated storyboard; Polly narration; duration and media checks before export"):
            qa = render(db.get(job_id), folder, clips, check, lambda state, detail: db.stage(job_id, state, detail))
        relative_folder = str(folder.relative_to(db.root)).replace("\\", "/")
        with checked_action(db, job_id, "save_export", "Save private artifacts only after media QA passes"):
            publish(folder, relative_folder)
        artifact = {
            "attempt": current["attempt"],
            "folder": relative_folder,
            "qa": qa,
            "created_at": time.time(),
            "request": current["request"],
            "plan": current["plan"],
            "evidence": current["evidence"],
            "capture_reuse": {"reused": reused, "recorded": len(clips) - reused},
            "plan_sha256": digest(current["plan"]),
            "export_sha256": qa["sha256"],
        }
        db.stage(
            job_id,
            "ready_for_review",
            "Export passed media checks. Ready for playback and review.",
            artifacts=db.get(job_id)["artifacts"] + [artifact],
        )
        emit(job_id, "export_ready", attempt=job["attempt"], reused_scenes=reused)
    except InterruptedError:
        db.mutate(job_id, lambda j: j.update(state="cancelled", error=None))
    except Exception as exc:
        if db.get(job_id)["cancel_requested"]:
            db.mutate(job_id, lambda j: j.update(state="cancelled", error=None))
            return
        # Exceptions can contain remote request metadata. Keep credentials out of persisted/user-visible errors.
        from botocore.exceptions import ClientError

        if isinstance(exc, ClientError):
            detail = (
                "AWS "
                + exc.response.get("Error", {}).get("Code", "Error")
                + ": verify model access, region and credentials."
            )
        elif isinstance(exc, (ValueError, RuntimeError)):
            detail = str(exc)[:1500]
        else:
            detail = (
                f"{type(exc).__name__}: the stage failed. Check the configured services and retry."
            )
        db.mutate(job_id, lambda j: j.update(state="blocked", error=detail))
        policy(db, job_id, "worker", "after", "blocked", detail)
        emit(job_id, "worker_blocked", attempt=job["attempt"], error_type=type(exc).__name__)
    finally:
        stop.set()
        thread.join(timeout=1)
        db.release(job_id)


def main():
    print("Launchpad worker ready", flush=True)
    while True:
        job = store.claim()
        if not job:
            time.sleep(1)
            continue
        process(job, fixture=job.get("planner_mode") == "fixture")


if __name__ == "__main__":
    main()
