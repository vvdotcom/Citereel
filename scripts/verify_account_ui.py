"""Account UI regression check. Credentials come from environment, never source."""
import argparse
import json
import os
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument("--url", default="http://127.0.0.1:3011")
parser.add_argument("--live", action="store_true")
parser.add_argument("--mobile-start", action="store_true")
parser.add_argument("--legacy", action="store_true", help="Verify login before deploying UI")
args = parser.parse_args()
email = os.environ.get("CITEREEL_TEST_EMAIL", "reviewer@example.test")
password = os.environ.get("CITEREEL_TEST_PASSWORD", "local-ui-test-only")
output = Path("artifacts/account-ui")
output.mkdir(parents=True, exist_ok=True)


def contrast(foreground, background):
    def luminance(color):
        channels = [int(x) / 255 for x in re.findall(r"\d+", color)[:3]]
        linear = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in channels]
        return sum(x * weight for x, weight in zip(linear, [0.2126, 0.7152, 0.0722]))
    levels = sorted([luminance(foreground), luminance(background)])
    return (levels[1] + 0.05) / (levels[0] + 0.05)


def check_contrast(locator, background_locator=None):
    foreground = locator.evaluate("e => getComputedStyle(e).color")
    background = (background_locator or locator).evaluate("e => getComputedStyle(e).backgroundColor")
    assert contrast(foreground, background) >= 4.5, (foreground, background)

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={"width": 390, "height": 844} if args.mobile_start else {"width": 1600, "height": 1000})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    state = {"authenticated": False}

    def mock(route):
        path = route.request.url.split("/v1/", 1)[-1]
        result, status = {}, 200
        if path == "session/login":
            state["authenticated"] = True
            result = {"owner": "ui-test", "email": email}
        elif path == "session/logout":
            state["authenticated"] = False
        elif path == "session":
            result = {"owner": "ui-test", "email": email}
            status = 200 if state["authenticated"] else 401
        elif path == "jobs":
            result = []
        route.fulfill(status=status, json=result)

    if not args.live:
        page.route("**/v1/**", mock)
    page.goto(args.url, wait_until="networkidle")
    if args.mobile_start:
        page.get_by_role("button", name="Menu", exact=True).click()
    nav = page.get_by_role("navigation", name="Main navigation")
    nav.get_by_role("link", name="Open workspace" if args.legacy else "Sign in").click()
    page.get_by_role("button", name="Sign in", exact=True).wait_for()
    if not args.legacy:
        assert page.get_by_role("button", name="Enter judge demo").count() == 0
        check_contrast(page.get_by_role("button", name="Sign in", exact=True))
        check_contrast(page.get_by_role("button", name="Create an account", exact=True))
        check_contrast(page.locator(".lp-login p").first, page.locator(".lp-login > section"))
        page.screenshot(path=str(output / ("login-mobile-start.png" if args.mobile_start else "login-desktop.png")))
    page.locator('input[name="email"]').fill(email)
    page.locator('input[name="password"]').fill(password)
    if not args.legacy:
        page.get_by_role("button", name="Show password").click()
        assert page.locator('input[name="password"]').get_attribute("type") == "text"
        page.get_by_role("button", name="Hide password").click()
    with page.expect_response(lambda r: r.url.endswith("/session/login")) as login:
        page.get_by_role("button", name="Sign in", exact=True).click()
    assert login.value.status == 200, f"Login returned {login.value.status}"
    page.locator(".lp-app").wait_for()
    page.reload(wait_until="networkidle")
    page.locator(".lp-app").wait_for()
    if not args.legacy:
        assert page.locator(".lp-account-email").inner_text() == email
        check_contrast(page.locator(".lp-account-email"), page.locator(".lp-nav"))
        check_contrast(page.get_by_role("button", name="Log out", exact=True))
        for width, height in [(1600, 1000), (1280, 900), (390, 844)]:
            page.set_viewport_size({"width": width, "height": height})
            button = page.get_by_role("button", name="Log out", exact=True)
            assert button.is_visible()
            box = button.bounding_box()
            assert box and box["height"] >= 44
            assert box["x"] >= 0 and box["y"] + box["height"] <= height
            assert page.locator(".lp-account-email").is_visible()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(output / f"workspace-{width}.png"))
        page.get_by_role("button", name="Log out", exact=True).click()
        page.get_by_role("button", name="Sign in", exact=True).wait_for()
        page.reload(wait_until="networkidle")
        page.get_by_role("button", name="Sign in", exact=True).wait_for()
        page.screenshot(path=str(output / "login-mobile.png"))
    else:
        page.get_by_role("button", name="Sign out", exact=True).click()
        page.get_by_role("button", name="Sign in", exact=True).wait_for()
    assert not errors, errors
    print(json.dumps({"url": args.url, "live": args.live, "mobile_start": args.mobile_start, "login": "passed", "session_refresh": "passed", "logout": "passed", "new_ui_checked": not args.legacy}))
    browser.close()
