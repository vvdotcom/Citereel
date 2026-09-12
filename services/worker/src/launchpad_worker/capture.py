import re
import time
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

from .circuit import content_scale
from .fixture import fixture_html
from .network import (
    BOT_NAME,
    SafetyError,
    fetch_bytes,
    origin,
    policy,
    reject_verification_page,
    validate_url,
)
from .render import layout


def reveal_aws_documentation(page):
    # Use the browser's isolated automation context. add_style_tag waits for page
    # script execution and can stall when website JavaScript is disabled.
    page.locator("body").evaluate(
        "(body) => body.style.setProperty('display', 'block', 'important')"
    )


def prepare_page(page, source, request):
    if not source["fixture"] and origin(source["url"]) == "https://docs.aws.amazon.com":
        reveal_aws_documentation(page)
    zoom = content_scale(request)
    page.locator("html").evaluate(
        "(root, zoom) => root.style.setProperty('zoom', String(zoom))", zoom
    )
    text = page.locator("body").inner_text()[:6000]
    reject_verification_page(text)
    if len(text.strip()) < 80:
        raise SafetyError(
            "The captured page has no usable visible text. Choose a public static page."
        )
    # Our isolated automation overlay works even with website scripts disabled.
    page.locator("html").evaluate(
        """(root, zoom) => {
      document.querySelector('[data-launchpad-pointer]')?.remove();
      const pointer = document.createElement('div');
      pointer.setAttribute('data-launchpad-pointer', '');
      pointer.setAttribute('aria-hidden', 'true');
      pointer.style.cssText = 'position:fixed;z-index:2147483647;pointer-events:none;left:0;top:0;filter:drop-shadow(0 1px 1px #202830)';
      pointer.style.width = (30 / zoom) + 'px';
      pointer.style.height = (36 / zoom) + 'px';
      pointer.innerHTML = '<svg viewBox="0 0 30 36" width="100%" height="100%" aria-hidden="true"><path d="M3 2 L3 28 L10 21 L16 34 L22 31 L16 19 L27 19 Z" fill="#ff9900" stroke="#ffffff" stroke-width="2.4" stroke-linejoin="round"/></svg>';
      root.appendChild(pointer);
    }""",
        zoom,
    )


def pointer_at(page, x, y, zoom, clicked=False):
    page.locator("[data-launchpad-pointer]").evaluate(
        """(pointer, p) => {
      pointer.style.left = (p.x / p.zoom) + 'px';
      pointer.style.top = (p.y / p.zoom) + 'px';
      const shape = pointer.querySelector('path');
      shape.setAttribute('fill', p.clicked ? '#ffffff' : '#ff9900');
      shape.setAttribute('stroke', p.clicked ? '#ff9900' : '#ffffff');
    }""",
        {"x": x, "y": y, "zoom": zoom, "clicked": clicked},
    )


def visible_mouse_move(page, start, end, zoom, check):
    for step in range(1, 19):
        check()
        x = start[0] + (end[0] - start[0]) * step / 18
        y = start[1] + (end[1] - start[1]) * step / 18
        page.mouse.move(x, y)
        pointer_at(page, x, y, zoom)
        page.wait_for_timeout(40)


_STOP_WORDS = {
    "about",
    "after",
    "also",
    "before",
    "from",
    "into",
    "that",
    "their",
    "them",
    "then",
    "these",
    "this",
    "through",
    "with",
    "your",
}


def _terms(text):
    return {
        word
        for word in re.findall(r"[a-z0-9]+", (text or "").lower())
        if len(word) >= 4 and word not in _STOP_WORDS
    }


def narration_cues(scene, limit=3):
    """Return a few narration phrases and their proportional spoken positions."""
    narration = scene.get("narration") or scene.get("on_screen_copy") or scene.get("title") or ""
    phrases = [part.strip() for part in re.split(r"(?<=[.!?;])\s+", narration) if _terms(part)]
    if not phrases:
        return []
    total_words = max(1, sum(len(phrase.split()) for phrase in phrases))
    elapsed = 0
    cues = []
    for phrase in phrases:
        words = len(phrase.split())
        cues.append((phrase, (elapsed + words / 2) / total_words))
        elapsed += words
    if len(cues) <= limit:
        return cues
    indexes = [round(n * (len(cues) - 1) / (limit - 1)) for n in range(limit)]
    return [cues[index] for index in dict.fromkeys(indexes)]


def narration_targets(page, scene, limit=3):
    """Match narration phrases to visible semantic elements using a fixed selector."""
    candidates = []
    elements = page.locator("h1,h2,h3,p,li,a,button,th,td")
    for index in range(min(elements.count(), 120)):
        element = elements.nth(index)
        try:
            text = " ".join(element.inner_text(timeout=500).split())[:260]
            if text and element.is_visible() and _terms(text):
                candidates.append((element, text, _terms(text)))
        except Exception:
            continue

    selected = []
    used = set()
    for cue, progress in narration_cues(scene, limit):
        cue_terms = _terms(cue)
        ranked = sorted(
            (
                (len(cue_terms & candidate_terms), -len(candidate_text), index)
                for index, (_, candidate_text, candidate_terms) in enumerate(candidates)
                if index not in used and cue_terms & candidate_terms
            ),
            reverse=True,
        )
        if not ranked:
            continue
        index = ranked[0][2]
        used.add(index)
        element, target_text, _ = candidates[index]
        selected.append((element, cue, target_text, progress))
    return selected


def wait_for_recording_time(page, recording_start, target_seconds, check):
    while time.monotonic() - recording_start < target_seconds:
        check()
        remaining = target_seconds - (time.monotonic() - recording_start)
        page.wait_for_timeout(min(250, max(1, remaining * 1000)))


def narration_guided_mouse(page, scene, cursor, zoom, scene_duration, recording_start, check):
    """Move the real browser mouse to page content as its narration is spoken."""
    events = []
    targets = narration_targets(page, scene)
    if not targets:
        targets = [(None, scene.get("title", "Scene focus"), "Main content", 0.35)]
    for element, cue, target_text, progress in targets:
        cue_time = scene_duration * (0.18 + min(1, progress) * 0.58)
        wait_for_recording_time(page, recording_start, cue_time, check)
        if element is not None:
            try:
                element.scroll_into_view_if_needed(timeout=1500)
                box = element.bounding_box(timeout=1500)
            except Exception:
                box = None
        else:
            box = None
        if box:
            destination = (
                max(24, min(page.viewport_size["width"] - 24, box["x"] + box["width"] / 2)),
                max(24, min(page.viewport_size["height"] - 24, box["y"] + box["height"] / 2)),
            )
        else:
            destination = (page.viewport_size["width"] * 0.58, page.viewport_size["height"] * 0.46)
        visible_mouse_move(page, cursor, destination, zoom, check)
        cursor = destination
        page.wait_for_timeout(220)
        events.append(
            {
                "action": "narration_pointer",
                "cue": cue[:160],
                "target_text": target_text[:160],
                "recording_seconds": round(time.monotonic() - recording_start, 3),
                "pointer": {"x": round(cursor[0]), "y": round(cursor[1])},
            }
        )
    return cursor, events


def capture(job, folder, check=lambda: None, resource_cache=None):
    evidence = {s["page_id"]: s for s in job["evidence"]}
    clips = []
    events = []
    cache = resource_cache if resource_cache is not None else {}
    fetched = [0]
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--force-webrtc-ip-handling-policy=disable_non_proxied_udp"],
        )
        try:
            for index, scene in enumerate(job["plan"]["scenes"]):
                check()
                source = evidence[scene["page_id"]]
                robots = None if source["fixture"] else policy(source["url"])
                destination = folder / f"capture-{index + 1}"
                destination.mkdir(parents=True, exist_ok=True)
                _, (_, _, capture_width, capture_height) = layout(
                    job["request"], index + job.get("scene_offset", 0)
                )
                context = browser.new_context(
                    viewport={"width": capture_width, "height": capture_height},
                    record_video_dir=str(destination),
                    record_video_size={"width": capture_width, "height": capture_height},
                    accept_downloads=False,
                    service_workers="block",
                    java_script_enabled=source["fixture"],
                )

                # Permit read-only requests to the authorized origin only, and reject private DNS on every request.
                def guard(route, request, *, source=source, robots=robots):
                    check()
                    url = route.request.url
                    if source["fixture"]:
                        parsed = urlsplit(url)
                        parts = [part for part in parsed.path.split("/") if part]
                        if parsed.netloc == "fixture.launchpad.invalid" and len(parts) == 2:
                            site, key = parts
                            if site == source.get("fixture_site", "northstar"):
                                try:
                                    body = fixture_html(key, site)
                                except KeyError:
                                    route.abort()
                                    return
                                route.fulfill(status=200, content_type="text/html", body=body)
                                return
                        route.abort()
                        return
                    try:
                        validate_url(url, origin(source["url"]))
                        if not robots.can_fetch(BOT_NAME, url):
                            raise SafetyError("Robots policy blocks this resource.")
                        if route.request.method != "GET" or route.request.resource_type in (
                            "websocket",
                            "eventsource",
                        ):
                            raise SafetyError("Read-only capture")
                        if route.request.is_navigation_request() and url not in [
                            s["url"] for s in evidence.values()
                        ]:
                            raise SafetyError("Navigation is not in the inspected page plan.")
                        if url not in cache:
                            data, content_type = fetch_bytes(url, origin(source["url"]), 3_000_000)
                            fetched[0] += len(data)
                            if fetched[0] > 30_000_000:
                                raise SafetyError("Capture network budget exceeded.")
                            cache[url] = (data, content_type)
                        data, content_type = cache[url]
                        route.fulfill(status=200, content_type=content_type, body=data)
                    except Exception:
                        route.abort()

                context.route("**/*", guard)
                context.route_web_socket("**/*", lambda ws: ws.close())
                page = context.new_page()
                page.set_default_timeout(15000)
                page.on("popup", lambda popup: popup.close())
                target = (
                    "https://fixture.launchpad.invalid/"
                    + source.get("fixture_site", "northstar")
                    + "/"
                    + scene["page_id"]
                    if source["fixture"]
                    else source["url"]
                )
                first = next(iter(evidence.values()))
                start = (
                    "https://fixture.launchpad.invalid/"
                    + first.get("fixture_site", "northstar")
                    + "/"
                    + first["page_id"]
                    if source["fixture"]
                    else first["url"]
                )
                page.goto(start, wait_until="domcontentloaded", timeout=90000)
                prepare_page(page, first, job["request"])
                zoom = content_scale(job["request"])
                cursor = (capture_width * 0.8, capture_height * 0.7)
                pointer_at(page, *cursor, zoom)
                # Begin after the initial page is visible, BEFORE movement and clicks.
                recording_start = time.monotonic()
                scene_duration = job.get(
                    "scene_duration_seconds",
                    job["request"]["duration_seconds"] / len(job["plan"]["scenes"]),
                )
                page.wait_for_timeout(800)
                # Follow only an already inspected link. No forms or generated locators.
                if target != start:
                    links = page.get_by_role("link")
                    matched = None
                    from urllib.parse import urljoin

                    for n in range(min(links.count(), 100)):
                        link = links.nth(n)
                        if (
                            urljoin(start, link.get_attribute("href") or "") == target
                            and link.is_visible()
                        ):
                            matched = link
                            break
                    if matched:
                        matched.scroll_into_view_if_needed()
                        box = matched.bounding_box()
                        if box:
                            click_at = (box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                            visible_mouse_move(page, cursor, click_at, zoom, check)
                        else:
                            raise SafetyError("The inspected navigation link is not visible.")
                        page.mouse.down()
                        pointer_at(page, *click_at, zoom, clicked=True)
                        page.wait_for_timeout(240)
                        click_time = time.monotonic() - recording_start
                        page.mouse.up()
                        cursor = click_at
                        page.wait_for_url(target, timeout=15000)
                        events.append(
                            {
                                "scene": index + 1,
                                "action": "click",
                                "page_id": source["page_id"],
                                "at": time.time(),
                                "target": target,
                                "recording_seconds": click_time,
                                "pointer": {"x": click_at[0], "y": click_at[1]},
                            }
                        )
                    else:
                        page.goto(target, wait_until="domcontentloaded", timeout=90000)
                        events.append(
                            {
                                "scene": index + 1,
                                "action": "direct_navigation",
                                "detail": "No visible inspected link; no mouse click claimed.",
                            }
                        )
                page.wait_for_timeout(500)
                prepare_page(page, source, job["request"])
                pointer_at(page, *cursor, zoom)
                events.append({"scene": index + 1, "action": "content_reflow", "scale": zoom})
                if not source["fixture"] and origin(source["url"]) == "https://docs.aws.amazon.com":
                    # AWS docs hide the server-rendered body until their JavaScript starts.
                    # Reveal only that existing content; do not execute website scripts.
                    reveal_aws_documentation(page)
                    events.append(
                        {
                            "scene": index + 1,
                            "action": "static_html",
                            "detail": "AWS documentation HTML with body visibility restored; website scripts disabled.",
                        }
                    )
                page.screenshot(path=str(folder / f"scene-{index + 1}.png"))
                from PIL import Image, ImageStat

                with Image.open(folder / f"scene-{index + 1}.png") as screenshot:
                    if ImageStat.Stat(screenshot.convert("L")).stddev[0] < 2:
                        raise SafetyError("Visible-content QA rejected a blank webpage recording.")
                events.append(
                    {
                        "scene": index + 1,
                        "action": "goto",
                        "page_id": source["page_id"],
                        "at": time.time(),
                        "url": source["url"],
                    }
                )
                # A fixed semantic selector maps narration words to visible page content.
                # Narration never becomes executable browser code or a generated selector.
                cursor, pointer_events = narration_guided_mouse(
                    page,
                    scene,
                    cursor,
                    zoom,
                    scene_duration,
                    recording_start,
                    check,
                )
                events.extend({**event, "scene": index + 1} for event in pointer_events)
                if scene["scroll"] != "top":
                    page.mouse.wheel(0, 400 if scene["scroll"] == "middle" else 900)
                    events.append(
                        {
                            "scene": index + 1,
                            "action": "scroll",
                            "position": scene["scroll"],
                            "at": time.time(),
                        }
                    )
                while time.monotonic() - recording_start < scene_duration:
                    check()
                    page.wait_for_timeout(
                        min(
                            1000,
                            max(1, (scene_duration - (time.monotonic() - recording_start)) * 1000),
                        )
                    )
                recorded_seconds = time.monotonic() - recording_start
                video = page.video
                context.close()
                # Retain the entire visible interaction, not just the final hold.
                # Initial loading remains trimmed; exported clicks are never looped.
                from .render import run

                clip = folder / f"scene-{index + 1}-ready.mp4"
                run(
                    [
                        "ffmpeg",
                        "-y",
                        "-v",
                        "error",
                        "-sseof",
                        str(-recorded_seconds),
                        "-i",
                        str(Path(video.path()).resolve()),
                        "-t",
                        str(recorded_seconds),
                        "-an",
                        "-c:v",
                        "libx264",
                        "-preset",
                        "veryfast",
                        "-crf",
                        "17",
                        "-pix_fmt",
                        "yuv420p",
                        str(clip),
                    ]
                )
                events.append(
                    {
                        "scene": index + 1,
                        "action": "interaction_recording",
                        "seconds": recorded_seconds,
                        "clicks_preserved": True,
                    }
                )
                clips.append(str(clip.resolve()))
        finally:
            browser.close()
    return clips, events
