import json
import uuid

import pytest
from launchpad_agent.concierge import target_scene_count
from launchpad_agent.contracts import GenerationRequest
from launchpad_worker.capture import capture
from launchpad_worker.changes import recording_key
from launchpad_worker.network import SafetyError, inspect_site, reject_verification_page
from launchpad_worker.render import probe
from launchpad_worker.runner import cached_capture_receipts


@pytest.mark.parametrize("seconds", [120, 180])
def test_long_presentations_are_accepted(seconds):
    request = GenerationRequest(
        website_url="fixture://northstar",
        authorization_confirmed=True,
        brief="Show a source-backed product walkthrough.",
        duration_seconds=seconds,
        format="presentation",
        idempotency_key=uuid.uuid4().hex,
    )
    assert request.duration_seconds == seconds


@pytest.mark.parametrize(
    ("seconds", "scenes"),
    [(30, 3), (45, 3), (60, 4), (90, 6), (120, 8), (180, 12)],
)
def test_scene_count_keeps_each_slide_between_ten_and_fifteen_seconds(seconds, scenes):
    assert target_scene_count(seconds) == scenes
    assert 10 <= seconds / scenes <= 15


def test_animated_camera_zoom_is_disabled_by_default():
    request = GenerationRequest(
        website_url="fixture://northstar",
        authorization_confirmed=True,
        brief="Show a source-backed product walkthrough.",
        idempotency_key=uuid.uuid4().hex,
    )
    assert request.zoom is False


@pytest.mark.parametrize(
    "text",
    [
        "In order to continue, we need to verify that you're not a robot.",
        "Please enter the characters you see below.",
        "Verify you are human before continuing.",
    ],
)
def test_verification_is_not_accepted_as_product_evidence(text):
    with pytest.raises(SafetyError, match="human verification"):
        reject_verification_page(text)


def test_capture_cache_changes_with_duration():
    evidence = inspect_site("fixture://northstar")
    scene = {"page_id": evidence[0]["page_id"], "scroll": "top"}
    request = {"orientation": "landscape", "format": "presentation", "duration_seconds": 120}
    assert recording_key(scene, evidence, request) != recording_key(
        scene, evidence, {**request, "duration_seconds": 180}
    )


def test_reused_recordings_preserve_original_click_receipts(tmp_path):
    shot = tmp_path / "attempt-2" / "shot-2"
    shot.mkdir(parents=True)
    clip = shot / "scene-1-ready.mp4"
    clip.touch()
    receipts = [
        {"scene": 1, "action": "goto"},
        {"scene": 2, "action": "click", "recording_seconds": 2.1},
    ]
    (shot.parent / "capture-events.json").write_text(json.dumps(receipts))
    assert cached_capture_receipts(clip, tmp_path) == [receipts[1]]
    clip.with_suffix(".events.json").write_text(json.dumps([receipts[0]]))
    assert cached_capture_receipts(clip, tmp_path) == [receipts[0]]


def test_real_navigation_click_is_kept_in_recorded_clip(tmp_path):
    evidence = inspect_site("fixture://northstar")
    scene = {
        "page_id": evidence[1]["page_id"],
        "scroll": "top",
        "title": "Evidence library",
        "on_screen_copy": "Keep the source beside the finding.",
        "narration": "Open the evidence library. Review each source beside its finding.",
    }
    job = {
        "request": {"format": "presentation", "orientation": "landscape", "duration_seconds": 180},
        "plan": {"scenes": [scene]},
        "evidence": evidence,
        "scene_duration_seconds": 6,
    }
    clips, events = capture(job, tmp_path)
    clicks = [event for event in events if event["action"] == "click"]
    assert len(clicks) == 1
    duration = float(probe(clips[0])["format"]["duration"])
    assert duration >= 5.7
    assert 0 < clicks[0]["recording_seconds"] < duration
    assert any(event["action"] == "interaction_recording" for event in events)
    pointer_events = [event for event in events if event["action"] == "narration_pointer"]
    assert pointer_events
    assert any("Evidence library" in event["target_text"] for event in pointer_events)
