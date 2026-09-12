"""Visual smoke check against the actual deployment; uses the verification session."""
import json
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = "https://dqhy3yyc3g60j.cloudfront.net"
session = json.loads((Path(tempfile.gettempdir()) / "launchpad-cloud-verification-session.json").read_text())
out = Path("artifacts/cloud-verification")
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(viewport={"width":1440,"height":1000}, device_scale_factor=1)
    context.add_cookies([{"name":"launchpad_session","value":session["cookie"],"url":BASE,"secure":True,"httpOnly":True,"sameSite":"Lax"}])
    page = context.new_page()
    response = page.goto(BASE + "/jobs/", wait_until="networkidle")
    print("studio_status", response.status)
    page.get_by_role("combobox", name="Select production").select_option(session["job_id"])
    page.get_by_role("tab", name="Trace", exact=True).click(timeout=30000)
    page.get_by_text("Policy and decision receipts", exact=False).wait_for(timeout=15000)
    page.screenshot(path=str(out / "cloud-trace-desktop.png"))
    page.set_viewport_size({"width":390,"height":844})
    page.screenshot(path=str(out / "cloud-trace-mobile.png"))
    print("mobile_horizontal_overflow", page.evaluate("document.documentElement.scrollWidth > innerWidth"))
    page.set_viewport_size({"width":1440,"height":1000})
    response = page.goto(BASE + "/verification/", wait_until="networkidle")
    assert response.status == 200
    page.get_by_text("Media integrity: passed", exact=True).wait_for()
    page.locator("video").first.evaluate("video => new Promise((resolve, reject) => { video.addEventListener('seeked', resolve, {once:true}); video.addEventListener('error', reject, {once:true}); video.currentTime = 9; })")
    media = page.locator("video").first.evaluate("video => ({width:video.videoWidth,height:video.videoHeight,duration:video.duration,error:video.error?.code})")
    assert media["width"] == 2560 and not media.get("error")
    print("public_video", json.dumps(media))
    page.screenshot(path=str(out / "cloud-verification-desktop.png"))
    page.set_viewport_size({"width":390,"height":844})
    page.screenshot(path=str(out / "cloud-verification-mobile.png"))
    overflow = page.evaluate("document.documentElement.scrollWidth > innerWidth")
    print("verification_mobile_overflow", overflow)
    assert not overflow
    if page.locator("video").count() > 1:
        page.set_viewport_size({"width":1440,"height":1000})
        video = page.get_by_label("Amazon Bedrock public website demo", exact=True)
        video.scroll_into_view_if_needed()
        video.evaluate("video => new Promise((resolve, reject) => { video.addEventListener('seeked', resolve, {once:true}); video.addEventListener('error', reject, {once:true}); video.currentTime = 9; })")
        assert video.evaluate("video => video.videoWidth === 2560 && !video.error")
        page.screenshot(path=str(out / "cloud-public-site-preview.png"))
        print("aws_public_site_video", "passed")
    context.close()
    browser.close()
