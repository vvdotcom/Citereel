"""Preline integration and responsive regression checks against the local app."""

from pathlib import Path

from playwright.sync_api import expect, sync_playwright

OUT = Path(__file__).resolve().parents[1] / "artifacts" / "screenshots"
with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={"width": 1600, "height": 1000})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    for _visit in range(2):
        page.goto("http://127.0.0.1:3011", wait_until="networkidle")
        disclosure = page.locator(".home-questions .hs-accordion").first
        expect(disclosure).to_have_attribute("data-preline-ready", "true")
        button = disclosure.get_by_role("button")
        panel = disclosure.get_by_role("region")
        button.click()
        expect(button).to_have_attribute("aria-expanded", "true")
        expect(panel).to_be_visible()
        button.press("Enter")
        expect(button).to_have_attribute("aria-expanded", "false")
        expect(panel).to_be_hidden()
        button.press("Space")
        expect(panel).to_be_visible()
        page.wait_for_function(
            "(id) => document.getElementById(id).style.height === ''",
            arg=button.get_attribute("aria-controls"),
        )
        assert panel.evaluate("(el) => el.clientHeight >= el.scrollHeight"), (
            "Disclosure content clipped"
        )
        page.screenshot(path=str(OUT / "13-preline-home.png"), full_page=True)
        page.get_by_role("link", name="Open workspace", exact=True).click()
        expect(
            page.get_by_role("button", name="Open local workspace").or_(
                page.get_by_role("heading", name="Production studio")
            )
        ).to_be_visible()
        if page.get_by_role("button", name="Open local workspace").is_visible():
            page.get_by_role("button", name="Open local workspace").click()
        page.get_by_role("heading", name="Production studio").wait_for()
    for width in (320, 390, 768, 1024, 1250, 1400, 1600):
        page.set_viewport_size({"width": width, "height": 900})
        for view in ("Projects", "Create demo"):
            page.get_by_role("button", name=view, exact=True).click()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
                width,
                view,
            )
        if width in (390, 1600):
            page.screenshot(path=str(OUT / f"14-preline-studio-{width}.png"), full_page=True)
    page.get_by_role("button", name="Projects", exact=True).click()
    page.locator('[data-job-id="lp_964a1b89ad964272"]').click()
    page.get_by_role("tab", name="Claims", exact=False).click()
    disclosure = page.locator(".lp-evidence-disclosure").first
    expect(disclosure).to_have_attribute("data-preline-ready", "true")
    button = disclosure.get_by_role("button")
    button.click()
    expect(disclosure.get_by_role("region")).to_be_visible()
    # A jobs refresh must not reset a user-opened evidence disclosure.
    page.wait_for_timeout(3000)
    expect(button).to_have_attribute("aria-expanded", "true")
    expect(disclosure.get_by_role("region")).to_be_visible()
    page.screenshot(path=str(OUT / "15-preline-evidence.png"), full_page=True)
    button.click()
    expect(disclosure.get_by_role("region")).to_be_hidden()
    assert not errors, errors
    browser.close()
print("Preline mouse/keyboard, remount, polling and seven viewport checks passed.")
