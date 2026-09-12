"""Automated acceptance test for the locally running application; saves screenshots."""

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts" / "screenshots"
OUTPUT.mkdir(parents=True, exist_ok=True)
with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1600, "height": 1000}, device_scale_factor=1)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto("http://127.0.0.1:3011", wait_until="networkidle")
    for label in ("Presentations", "Product demos", "Spotlights", "Shorts"):
        page.get_by_role("tab", name=label, exact=True).click()
        page.locator("video").evaluate("(video) => video.play()")
        page.wait_for_function('document.querySelector("video").currentTime > 0.3')
        page.locator("video").evaluate("(video) => video.pause()")
    page.get_by_role("tab", name="Presentations", exact=True).click()
    page.screenshot(path=str(OUTPUT / "00-home.png"), full_page=True)
    page.goto("http://127.0.0.1:3011/studio", wait_until="networkidle")
    assert page.get_by_role("button", name="Open local workspace").count() == 0
    response = page.context.request.post("http://127.0.0.1:8011/v1/session/local")
    assert response.ok
    page.reload(wait_until="networkidle")
    page.get_by_role("heading", name="Production studio").wait_for()
    assert page.get_by_label("Production mode", exact=True).count() == 0
    assert page.get_by_label("Included demo source", exact=True).count() == 0
    assert page.get_by_label("Website URL", exact=True).input_value() == ""
    brief = page.locator('.lp-brief-bar textarea[name="brief"]')
    assert brief.count() == 1
    brief_box = brief.bounding_box()
    dock_box = page.locator(".lp-brief-bar").bounding_box()
    assert brief_box and brief_box["width"] > 800 and brief_box["height"] >= 148
    assert dock_box and abs(dock_box["y"] + dock_box["height"] - 1000) <= 1
    for mode in ("presentation", "product", "spotlight", "short"):
        page.get_by_label("Demo format").select_option(mode)
        assert page.get_by_label("Production mode", exact=True).count() == 0
    page.get_by_label("Demo format").select_option("presentation")
    duration = page.locator('select[name="duration"]')
    duration.select_option("120")
    assert duration.locator("option:checked").inner_text() == "2 minutes"
    duration.select_option("180")
    assert duration.locator("option:checked").inner_text() == "3 minutes"
    page.get_by_label("Demo format").select_option("product")
    assert duration.input_value() == "120"
    assert duration.locator('option[value="180"]').count() == 0
    page.get_by_label("Demo format").select_option("presentation")
    duration.select_option("45")
    page.screenshot(path=str(OUTPUT / "01-studio.png"), full_page=True)
    page.get_by_role("button", name="Projects", exact=True).click()
    page.get_by_role("heading", name="Your projects", exact=True).wait_for()
    page.screenshot(path=str(OUTPUT / "02-projects.png"), full_page=True)
    manifest = json.loads(
        (ROOT / "public" / "examples" / "manifest.json").read_text(encoding="utf-8")
    )
    featured = page.locator('[data-job-id="' + manifest["presentation"]["job_id"] + '"]')
    if featured.count():
        featured.click()
    else:
        page.locator(".lp-project").filter(has=page.locator("img")).first.click()
    page.locator("video").wait_for()
    page.locator("video").evaluate("(video) => video.play()")
    page.wait_for_function('document.querySelector("video").currentTime > 0.3')
    page.locator("video").evaluate("(video) => video.pause()")
    page.screenshot(path=str(OUTPUT / "03-export.png"), full_page=True)
    page.get_by_role("tab", name="Storyboard", exact=True).click()
    page.locator(".lp-storyboard article").first.wait_for()
    page.screenshot(path=str(OUTPUT / "04-storyboard.png"), full_page=True)
    page.get_by_role("tab", name="Sources", exact=False).click()
    page.locator(".lp-sources article").first.wait_for()
    page.screenshot(path=str(OUTPUT / "05-sources.png"), full_page=True)
    page.get_by_role("tab", name="Receipts", exact=True).click()
    page.get_by_role("heading", name="Production receipt", exact=True).wait_for()
    page.screenshot(path=str(OUTPUT / "07-receipts.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    page.get_by_role("button", name="Create demo", exact=True).click()
    mobile_brief_box = page.locator('.lp-brief-bar textarea[name="brief"]').bounding_box()
    mobile_dock_box = page.locator(".lp-brief-bar").bounding_box()
    assert mobile_brief_box and mobile_brief_box["width"] >= 280
    assert mobile_dock_box and abs(mobile_dock_box["y"] + mobile_dock_box["height"] - 844) <= 1
    page.screenshot(path=str(OUTPUT / "06-mobile.png"), full_page=True)
    assert not errors, errors
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), (
        "Mobile layout overflows"
    )
    browser.close()
print("Browser acceptance checks passed. Screenshots:", OUTPUT)
