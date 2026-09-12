"""Read-only cloud UI checks; intercept submissions so no paid job is created."""

import json
import re
import tempfile
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = "https://dqhy3yyc3g60j.cloudfront.net"
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts" / "screenshots"
OUTPUT.mkdir(parents=True, exist_ok=True)
session = json.loads(
    (Path(tempfile.gettempdir()) / "launchpad-cloud-verification-session.json").read_text()
)

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(BASE + "/studio/", wait_until="networkidle")
    expect(page.get_by_role("button", name="Sign in", exact=True)).to_be_visible()
    expect(page.get_by_role("button", name="Open local workspace")).to_have_count(0)
    page.screenshot(path=str(OUTPUT / "cloud-clean-signin.png"))
    context.add_cookies([{
        "name": "launchpad_session", "value": session["cookie"], "url": BASE,
        "secure": True, "httpOnly": True, "sameSite": "Lax",
    }])
    page.reload(wait_until="networkidle")
    expect(page.get_by_role("heading", name="Create a demo", exact=True)).to_be_visible()
    expect(page.get_by_role("link", name="Citereel home")).to_be_visible()
    expect(page.get_by_role("tab", name="Trials", exact=True)).to_have_count(0)
    assert "launchpad" not in page.locator("body").inner_text().lower()
    for label in ("Production mode", "Included demo source"):
        expect(page.get_by_label(label, exact=True)).to_have_count(0)
    expect(page.get_by_label("Website URL", exact=True)).to_have_value("")
    expect(page.get_by_label("Brand name", exact=True)).to_have_value("")
    expect(page.get_by_label("Describe your video", exact=True)).to_have_value("")
    expect(page.get_by_role("combobox", name="Narrator", exact=True)).to_have_value("female")
    assert page.locator(".lp-intake form").evaluate(
        "form => form.lastElementChild.classList.contains('lp-brief-bar')"
    )
    desktop_brief_box = page.get_by_label("Describe your video", exact=True).bounding_box()
    desktop_dock_box = page.locator(".lp-brief-bar").bounding_box()
    assert desktop_brief_box and desktop_brief_box["width"] > 700
    assert desktop_brief_box["height"] >= 148
    assert desktop_dock_box and abs(desktop_dock_box["y"] + desktop_dock_box["height"] - 1000) <= 1
    page.get_by_role("button", name="Use public Amazon Bedrock example").click()
    assert "Explain Amazon Bedrock" in page.get_by_label("Describe your video").input_value()
    page.locator('input[name="authorization"]').check()
    submissions = []

    def intercept(route):
        if route.request.method == "POST":
            submissions.append(route.request.post_data_json)
            route.fulfill(status=400, content_type="application/json",
                          body=json.dumps({"detail": "UI test: no job created."}))
        else:
            route.continue_()

    page.route("**/v1/jobs", intercept)
    for index, mode in enumerate(("presentation", "product", "spotlight", "short")):
        voice = "female" if index % 2 == 0 else "male"
        page.get_by_label("Demo format").select_option(mode)
        page.get_by_role("combobox", name="Narrator", exact=True).select_option(voice)
        page.locator('.lp-intake button[type="submit"]').click()
        expect(page.get_by_role("status")).to_contain_text("UI test: no job created.")
        assert submissions[-1]["planner_mode"] == "bedrock"
        assert submissions[-1]["request"]["format"] == mode
        assert submissions[-1]["request"]["narration_voice"] == voice
        assert submissions[-1]["request"]["brief"].startswith("Explain Amazon Bedrock")
        page.get_by_role("button", name="Dismiss notification").click()
    assert len(submissions) == 4
    page.get_by_label("Demo format").select_option("presentation")
    page.locator('select[name="duration"]').select_option("180")
    page.locator(".lp-brief-bar").scroll_into_view_if_needed()
    page.screenshot(path=str(OUTPUT / "cloud-bottom-brief-desktop.png"))
    page.set_viewport_size({"width": 390, "height": 844})
    page.locator(".lp-brief-bar").scroll_into_view_if_needed()
    mobile_brief_box = page.get_by_label("Describe your video", exact=True).bounding_box()
    mobile_dock_box = page.locator(".lp-brief-bar").bounding_box()
    assert mobile_brief_box and mobile_brief_box["width"] >= 280
    assert mobile_dock_box and abs(mobile_dock_box["y"] + mobile_dock_box["height"] - 844) <= 1
    page.screenshot(path=str(OUTPUT / "cloud-bottom-brief-mobile.png"))
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.set_viewport_size({"width": 1440, "height": 1000})
    page.goto(BASE + "/jobs/", wait_until="networkidle")
    page.get_by_role("combobox", name="Select production").select_option(session["job_id"])
    expect(page.get_by_role("heading", name="Job report", exact=True)).to_be_visible()
    expect(page.get_by_label("Job progress", exact=True).first).to_be_visible()
    if not page.get_by_role("region", name="Timestamped activity log").is_visible():
        page.get_by_text(re.compile(r"^Activity log \(\d+ saved updates\)$")).click()
    expect(page.get_by_role("region", name="Timestamped activity log")).to_be_visible()
    report_link = page.get_by_text("Download report (.json)", exact=True)
    expect(report_link).to_be_visible()
    report_href = report_link.get_attribute("href")
    report_response = context.request.get(
        report_href if report_href.startswith("http") else BASE + report_href
    )
    assert report_response.ok
    saved_report = report_response.json()
    assert saved_report["id"] == session["job_id"]
    assert len(saved_report["timeline"]) > 0
    page.screenshot(path=str(OUTPUT / "cloud-job-report-desktop.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    expect(page.get_by_role("heading", name="Job report", exact=True)).to_be_visible()
    expect(page.get_by_label("Job progress", exact=True).first).to_be_visible()
    page.screenshot(path=str(OUTPUT / "cloud-job-report-mobile.png"), full_page=True)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.set_viewport_size({"width": 1440, "height": 1000})
    video = page.locator(".lp-preview video").first
    media = video.evaluate("""video => new Promise((resolve, reject) => {
      const done = () => resolve({
        duration: video.duration,
        width: video.videoWidth,
        height: video.videoHeight,
      });
      if (video.readyState >= 1) return done();
      video.addEventListener("loadedmetadata", done, { once: true });
      setTimeout(() => reject(new Error("Video metadata timed out")), 10000);
    })""")
    expected_duration = saved_report["artifacts"][-1]["qa"]["duration_seconds"]
    assert abs(media["duration"] - expected_duration) <= 1, media
    assert media["width"] == 2560 and media["height"] == 1440, media
    panels = {
        "Preview": ".lp-preview video", "Storyboard": ".lp-storyboard article",
        "Claims": ".lp-claims article", "Sources": ".lp-sources article",
        "Trace": ".lp-trace li", "Receipts": ".lp-receipts",
    }
    expect(page.get_by_role("tab", name="Trials", exact=True)).to_have_count(0)
    expect(page.get_by_role("tablist", name="Production views").get_by_role("tab")).to_have_count(6)
    for name, selector in panels.items():
        tab = page.get_by_role("tab", name=re.compile("^" + name + r"(?: \(|$)"))
        tab.click()
        expect(tab).to_have_attribute("aria-selected", "true")
        expect(page.locator(selector).first).to_be_visible()
        assert "launchpad" not in page.locator("body").inner_text().lower(), name
        print(name, "panel loaded")
    for name in ("Settings", "Projects"):
        page.get_by_role("button", name=name, exact=True).click()
        assert "launchpad" not in page.locator("body").inner_text().lower(), name
    assert not errors, errors
    browser.close()
print("Sign-in, bottom brief, four Bedrock submission payloads, mobile and six tabs passed; Trials removed.")
print("No cloud production was created or changed.")
