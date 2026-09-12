"""Verify cloud narrator choices without creating a production job."""

import json
import secrets
import uuid

from playwright.sync_api import expect, sync_playwright


BASE = "https://dqhy3yyc3g60j.cloudfront.net"


with sync_playwright() as pw:
    browser = pw.chromium.launch()
    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    page = context.new_page()
    request_failures = []
    page.on(
        "requestfailed",
        lambda request: request_failures.append(
            {"url": request.url, "failure": request.failure}
        ),
    )
    page.goto(BASE + "/studio/", wait_until="networkidle")
    page.get_by_role("button", name="Create an account", exact=True).click()
    page.get_by_label("Email", exact=True).fill(
        f"voice-check-{uuid.uuid4().hex[:12]}@example.invalid"
    )
    page.get_by_label("Password", exact=True).fill(secrets.token_urlsafe(32))
    page.get_by_role("button", name="Create account", exact=True).click()
    try:
        expect(page.get_by_role("heading", name="Create a demo", exact=True)).to_be_visible()
    except AssertionError:
        raise AssertionError(f"Registration request failed: {request_failures}")

    narrator = page.get_by_role("combobox", name="Narrator", exact=True)
    expect(narrator).to_have_value("female")
    assert narrator.locator("option").all_text_contents() == [
        "Female (Ruth)",
        "Male (Matthew)",
    ]

    page.get_by_role("button", name="Use public Amazon Bedrock example").click()
    page.locator('input[name="authorization"]').check()
    submissions = []

    def intercept(route):
        submissions.append(route.request.post_data_json)
        route.fulfill(
            status=409,
            content_type="application/json",
            body=json.dumps({"detail": "Voice UI check: no job created."}),
        )

    page.route("**/v1/jobs", intercept)
    for voice in ("female", "male"):
        narrator.select_option(voice)
        page.locator('.lp-intake button[type="submit"]').click()
        expect(page.get_by_role("status")).to_contain_text("no job created")
        assert submissions[-1]["request"]["narration_voice"] == voice
        page.get_by_role("button", name="Dismiss notification").click()

    page.unroute("**/v1/jobs", intercept)
    request = {
        "title": "Voice schema check",
        "website_url": "https://www.wikipedia.org/",
        "authorization_confirmed": False,
        "brief": "Validate the narrator choice without creating a production.",
        "narration_voice": "female",
        "idempotency_key": uuid.uuid4().hex,
    }
    for voice in ("female", "male"):
        request["narration_voice"] = voice
        response = context.request.post(
            BASE + "/v1/jobs", data={"request": request, "planner_mode": "bedrock"}
        )
        assert response.status == 409
        assert "permission" in response.json()["detail"].lower()
    request["narration_voice"] = "unsupported"
    response = context.request.post(
        BASE + "/v1/jobs", data={"request": request, "planner_mode": "bedrock"}
    )
    assert response.status == 422
    browser.close()

print("Female Ruth and male Matthew UI/API choices passed; no production job was created.")
