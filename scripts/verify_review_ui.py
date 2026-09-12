"""Application acceptance checks for AWS intake, evidence and simulated trials."""

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument("--job", required=True)
args = parser.parse_args()
out = Path(__file__).resolve().parents[1] / "artifacts" / "screenshots"
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={"width": 1600, "height": 1000})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto("http://127.0.0.1:3011/studio", wait_until="networkidle")
    page.get_by_role("button", name="Open local workspace").click()
    page.get_by_role("button", name="Use public Amazon Bedrock example").click()
    assert (
        page.get_by_label("Website URL", exact=True)
        .input_value()
        .startswith("https://docs.aws.amazon.com/")
    )
    assert "Amazon Bedrock" in page.locator('textarea[name="brief"]').input_value()
    assert page.get_by_label("Production mode", exact=True).input_value() == "bedrock"
    page.screenshot(path=str(out / "08-aws-brief.png"), full_page=True)
    page.get_by_role("button", name="Projects", exact=True).click()
    page.locator('[data-job-id="' + args.job + '"]').click()
    page.get_by_role("tab", name="Claims", exact=False).click()
    page.locator(".lp-claims article").first.wait_for()
    assert page.get_by_text("Needs human review", exact=True).count() > 0
    page.screenshot(path=str(out / "09-aws-claims.png"), full_page=True)
    page.get_by_role("tab", name="Trials", exact=True).click()
    page.get_by_role("heading", name="Simulated founder sessions").wait_for()
    assert page.get_by_text("These names are fictional test personas.", exact=False).count() > 0
    page.screenshot(path=str(out / "10-simulated-trials.png"), full_page=True)
    page.get_by_role("tab", name="Preview", exact=True).click()
    if page.locator("video").count():
        page.locator("video").evaluate("(video) => video.play()")
        page.wait_for_function('document.querySelector("video").currentTime > 0.3')
        page.locator("video").evaluate("(video) => video.pause()")
    page.screenshot(path=str(out / "11-aws-export.png"), full_page=True)
    for width in (390, 768):
        page.set_viewport_size({"width": width, "height": 844})
        for tab in ("Storyboard", "Claims", "Sources", "Trace", "Receipts", "Trials"):
            page.get_by_role("tab", name=tab, exact=False).click()
            overflow = page.evaluate(
                "Array.from(document.querySelectorAll('body *')).filter(e => e.getBoundingClientRect().right > innerWidth + 1 && getComputedStyle(e).position !== 'absolute').slice(0, 10).map(e => e.tagName + '.' + e.className)"
            )
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
                width,
                tab,
                overflow,
            )
        page.screenshot(path=str(out / f"12-trials-{width}.png"), full_page=True)
    assert not errors, errors
    browser.close()
print("AWS intake, claims, trials, desktop and mobile checks passed.")
