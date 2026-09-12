"""Check public branding without creating accounts or starting production jobs."""

import re
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = "https://dqhy3yyc3g60j.cloudfront.net"
OUTPUT = Path(__file__).resolve().parents[1] / "artifacts" / "screenshots"
OUTPUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    for route in ("/", "/studio/", "/demo/", "/jobs/", "/projects/", "/verification/"):
        page.goto(BASE + route, wait_until="networkidle")
        expect(page).to_have_title(re.compile("^Citereel"))
        mark = page.locator(".brand-mark").first
        if route != "/verification/":
            expect(mark).to_be_visible()
            assert mark.evaluate("img => img.complete && img.naturalWidth === 64")
            expect(page.get_by_text("citereel", exact=True).first).to_be_visible()
        else:
            expect(page.get_by_text("Media integrity: passed", exact=True)).to_be_visible()
        assert "launchpad" not in page.locator("body").inner_text().lower(), route
        assert page.locator('link[rel="icon"]').get_attribute("href") == "/brand/citereel.svg"
        page.screenshot(path=str(OUTPUT / ("citereel-" + (route.strip("/") or "home") + ".png")))
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), route
        if route != "/verification/":
            expect(mark).to_be_visible()
        if route == "/":
            page.screenshot(path=str(OUTPUT / "citereel-home-mobile.png"))
        page.set_viewport_size({"width": 1440, "height": 1000})
        if route == "/studio/":
            page.route("**/v1/session/login", lambda request: request.fulfill(
                status=403, content_type="application/json",
                body=json.dumps({"detail": "Use the Launchpad web application."}),
            ))
            page.get_by_label("Email", exact=True).fill("branding-check@example.invalid")
            page.get_by_label("Password", exact=True).fill("intercepted-test-only")
            page.get_by_role("button", name="Sign in", exact=True).click()
            expect(page.locator('.lp-error[role="alert"]')).to_have_text("Use the Citereel web application.")
            assert "launchpad" not in page.locator("body").inner_text().lower()
            page.unroute("**/v1/session/login")
        print(route, "branding, icon and mobile layout passed")
    assert not errors, errors
    browser.close()
