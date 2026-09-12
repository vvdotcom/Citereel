"""Read-only landing page regression checks and desktop/mobile screenshots."""

import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main():
    output = Path("artifacts/screenshots")
    output.mkdir(parents=True, exist_ok=True)
    errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto("http://127.0.0.1:3011/", wait_until="networkidle")
        expect(page.get_by_role("heading", level=1)).to_contain_text("Your product has a story.")
        table = page.get_by_role("table", name="Recorded Northstar sample benchmarks")
        expect(table.get_by_role("columnheader")).to_have_count(5)
        expect(table.get_by_role("row")).to_have_count(10)
        manifest = json.loads(Path("public/examples/manifest.json").read_text())
        expected_size = f"{manifest['presentation']['qa']['bytes'] / 1_000_000:.2f} MB"
        expect(table.get_by_role("row", name="Download size", exact=False)).to_contain_text(
            expected_size
        )
        for mode, label in [
            ("presentation", "presentations"),
            ("product", "product demos"),
            ("spotlight", "spotlights"),
            ("short", "shorts"),
        ]:
            page.get_by_role("link", name=f"Watch {label} benchmark", exact=True).click()
            expect(page.locator("video")).to_have_attribute("aria-label", f"{mode} example")
        page.locator("#benchmarks").screenshot(path=str(output / "landing-benchmarks-desktop.png"))
        for name in ["Presentations", "Product demos", "Spotlights", "Shorts"]:
            tab = page.get_by_role("tab", name=name, exact=True)
            tab.click()
            expect(tab).to_have_attribute("aria-selected", "true")
            video = page.locator("video")
            video.evaluate("async v => { v.muted = true; await v.play(); }")
            page.wait_for_function("document.querySelector('video').currentTime > 0.3")
            video.evaluate("v => v.pause()")
        page.get_by_role("tab", name="Presentations", exact=True).focus()
        page.keyboard.press("ArrowRight")
        expect(page.get_by_role("tab", name="Product demos", exact=True)).to_be_focused()
        page.keyboard.press("End")
        expect(page.get_by_role("tab", name="Shorts", exact=True)).to_have_attribute(
            "aria-selected", "true"
        )
        page.keyboard.press("Home")
        expect(page.get_by_role("tab", name="Presentations", exact=True)).to_have_attribute(
            "aria-selected", "true"
        )
        page.locator("video").evaluate("async v => { v.muted = true; await v.play(); }")
        page.wait_for_function("document.querySelector('video').currentTime > 0.3")
        page.locator("video").evaluate("v => v.pause()")
        question = page.get_by_role("button", name="Which websites can I use?")
        question.click()
        expect(question).to_have_attribute("aria-expanded", "true")
        expect(
            page.get_by_text("Use a public page you are authorized", exact=False)
        ).to_be_visible()
        question.click()
        expect(question).to_have_attribute("aria-expanded", "false")
        page.evaluate("window.scrollTo(0, 0)")
        page.screenshot(path=str(output / "landing-zoom-desktop.png"), full_page=True)
        for width in [320, 390, 768, 1024, 1440]:
            page.set_viewport_size({"width": width, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), (
                f"Overflow at {width}"
            )
        page.set_viewport_size({"width": 390, "height": 844})
        comparison = page.get_by_role("region", name="Video mode benchmark comparison")
        comparison.evaluate("el => el.scrollLeft = el.scrollWidth")
        assert comparison.evaluate("el => el.scrollLeft > 0"), "Mobile comparison must scroll"
        page.locator("#benchmarks").screenshot(path=str(output / "landing-benchmarks-mobile.png"))
        menu = page.get_by_role("button", name="Menu", exact=True)
        menu.click()
        expect(page.get_by_role("button", name="Close menu", exact=True)).to_have_attribute(
            "aria-expanded", "true"
        )
        page.get_by_role("navigation").get_by_role("link", name="FAQs", exact=True).click()
        expect(page.get_by_role("button", name="Menu", exact=True)).to_have_attribute(
            "aria-expanded", "false"
        )
        page.evaluate("window.scrollTo(0, 0)")
        page.screenshot(path=str(output / "landing-zoom-mobile.png"), full_page=True)
        page.get_by_role("link", name="Create your demo").first.click()
        expect(page).to_have_url("http://127.0.0.1:3011/studio")
        assert not errors, errors
        browser.close()
    print(
        "PASS: four video formats, keyboard tabs, FAQ, mobile menu, CTA, five viewport widths; no browser errors."
    )


if __name__ == "__main__":
    main()
