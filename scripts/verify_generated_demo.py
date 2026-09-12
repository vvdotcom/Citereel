"""Verify and download an actual Launchpad export through its authenticated API."""

import argparse
import hashlib
import json
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument("--job", required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
output = root / "artifacts" / "verification" / args.job
output.mkdir(parents=True, exist_ok=True)
base = "http://127.0.0.1:3011"
with httpx.Client(base_url=base + "/api/backend/", headers={"Origin": base}, timeout=60) as client:
    client.post("session/local").raise_for_status()
    result = client.get("jobs/" + args.job)
    result.raise_for_status()
    job = result.json()
    assert job["state"] in ("ready_for_review", "approved"), (job["state"], job.get("error"))
    artifact = job["artifacts"][-1]
    qa = artifact["qa"]
    assert abs(qa["duration_seconds"] - 180) < 1
    assert (qa["width"], qa["height"]) == (2560, 1440)
    assert job["planner"] == "bedrock" and job["model_usage"]["totalTokens"] > 0
    assert len(job["plan"]["scenes"]) == 8
    assert all(voice["provider"] == "Amazon Polly" for voice in qa["voices"])
    assert qa["recorded_clicks"] > 0
    assert "1.22x" in qa["camera_motion"]
    url = f"jobs/{args.job}/artifacts/{artifact['attempt']}/export.mp4"
    video = client.get(url)
    video.raise_for_status()
    assert hashlib.sha256(video.content).hexdigest() == qa["sha256"]
    (output / "amazon-bedrock-three-minute.mp4").write_bytes(video.content)
    (output / "quality.json").write_text(json.dumps(qa, indent=2), encoding="utf-8")
    (output / "capture-events.json").write_text(
        json.dumps(job["capture_events"], indent=2), encoding="utf-8"
    )

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1600, "height": 1000})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(base + "/studio", wait_until="networkidle")
    page.get_by_role("button", name="Open local workspace").click()
    page.get_by_role("button", name="Projects", exact=True).click()
    page.locator(f'[data-job-id="{args.job}"]').click()
    page.locator("video").wait_for()
    page.wait_for_function('document.querySelector("video").readyState >= 2')
    assert abs(page.locator("video").evaluate("video => video.duration") - 180) < 1
    page.locator("video").evaluate("video => video.play()")
    page.wait_for_function('document.querySelector("video").currentTime > 0.5')
    page.locator("video").evaluate("video => video.pause()")
    page.screenshot(path=str(output / "launchpad-preview.png"), full_page=True)
    for second in (40, 170):
        page.locator("video").evaluate("(video, second) => video.currentTime = second", second)
        page.wait_for_function('!document.querySelector("video").seeking')
        page.screenshot(path=str(output / f"launchpad-{second}s.png"), full_page=True)
    page.get_by_role("tab", name="Receipts", exact=True).click()
    page.get_by_role("heading", name="Production receipt", exact=True).wait_for()
    page.screenshot(path=str(output / "launchpad-receipt.png"), full_page=True)
    assert not errors, errors
    browser.close()
print(
    json.dumps(
        {
            "job": args.job,
            "duration": qa["duration_seconds"],
            "clicks": qa["recorded_clicks"],
            "video": str(output / "amazon-bedrock-three-minute.mp4"),
            "browser_playback": "passed",
        },
        indent=2,
    )
)
