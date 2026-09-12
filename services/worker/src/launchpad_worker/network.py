import hashlib
import ipaddress
import socket
import time
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx

_policies = {}
_policy_checked = {}
_last_fetch = {}
_delays = {}
BOT_NAME = "Citereel"
USER_AGENT = (
    "Citereel/1.0 (evidence-backed video capture; "
    "+https://dqhy3yyc3g60j.cloudfront.net/verification/)"
)


class SafetyError(ValueError):
    pass


class RedirectSafetyError(SafetyError):
    """A validated fetch stopped at an HTTP redirect for its caller to assess."""

    def __init__(self, location):
        super().__init__("The site redirects.")
        self.location = location


def reject_verification_page(text):
    normalized = " ".join(text.lower().replace("’", "'").split())
    if any(
        phrase in normalized
        for phrase in (
            "verify you are human",
            "checking your browser",
            "complete the captcha",
            "verify that you're not a robot",
            "verify that you are not a robot",
            "enter the characters you see below",
            "sorry, we just need to make sure you're not a robot",
        )
    ):
        raise SafetyError(
            "The website requires human verification. Launchpad cannot record this page automatically; choose an accessible public page or provide authorized footage."
        )


def origin(url):
    u = urlsplit(url)
    return f"{u.scheme.lower()}://{u.netloc.lower()}"


def validate_url(url, allowed=None):
    u = urlsplit(url)
    if (
        u.scheme not in ("https", "http")
        or not u.hostname
        or u.username
        or u.password
        or u.fragment
        or u.port not in (None, 80, 443)
    ):
        raise SafetyError(
            "Use a public HTTP(S) URL without credentials, fragments or custom ports."
        )
    if allowed and origin(url) != allowed:
        raise SafetyError("Navigation left the authorized origin.")
    try:
        addresses = socket.getaddrinfo(
            u.hostname, u.port or (443 if u.scheme == "https" else 80), type=socket.SOCK_STREAM
        )
    except socket.gaierror as exc:
        raise SafetyError("The website hostname could not be resolved.") from exc
    if not addresses or any(not ipaddress.ip_address(x[4][0]).is_global for x in addresses):
        raise SafetyError("Local, private and metadata addresses are not allowed.")
    return urlunsplit((u.scheme, u.netloc, u.path or "/", u.query, ""))


def fetch_bytes(url, allowed, limit=1_500_000):
    validate_url(url, allowed)
    wait = _delays.get(allowed, 0) - (time.monotonic() - _last_fetch.get(allowed, 0))
    if wait > 0:
        time.sleep(wait)
    _last_fetch[allowed] = time.monotonic()
    parsed = urlsplit(url)
    addresses = socket.getaddrinfo(
        parsed.hostname,
        parsed.port or (443 if parsed.scheme == "https" else 80),
        type=socket.SOCK_STREAM,
    )
    if any(not ipaddress.ip_address(x[4][0]).is_global for x in addresses):
        raise SafetyError("Private DNS result rejected.")
    # IPv4-only cloud subnets cannot connect to a first IPv6 DNS answer. Try at
    # most two verified public addresses, without changing origin or bypassing
    # HTTP denials/robots policies. Keep DNS pinning for every connection.
    candidates = list(dict.fromkeys(x[4][0] for x in addresses))
    candidates.sort(key=lambda ip: ":" in ip)
    with httpx.Client(
        timeout=httpx.Timeout(15, connect=8),
        follow_redirects=False,
        trust_env=False,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        for index, ip in enumerate(candidates[:2]):
            pinned = urlunsplit((parsed.scheme, ("[" + ip + "]") if ":" in ip else ip, parsed.path, parsed.query, ""))
            try:
                with client.stream("GET", pinned, headers={"Host": parsed.netloc},
                                   extensions={"sni_hostname": parsed.hostname}) as res:
                    if res.is_redirect:
                        raise RedirectSafetyError(res.headers.get("location", ""))
                    res.raise_for_status()
                    raw = bytearray()
                    for chunk in res.iter_bytes():
                        raw.extend(chunk)
                        if len(raw) > limit:
                            raise SafetyError("The page exceeds the bounded inspection size.")
                    return bytes(raw), res.headers.get("content-type", "application/octet-stream")
            except (httpx.ConnectTimeout, httpx.ConnectError):
                if index == min(len(candidates), 2) - 1:
                    raise SafetyError(f"Could not connect to {parsed.hostname} after bounded public-address attempts. Retry later or choose another accessible page.") from None


def fetch(url, allowed, limit=1_500_000):
    data, _ = fetch_bytes(url, allowed, limit)
    return data.decode("utf-8", errors="replace")


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
        self.links = []
        self.skip = 0
        self.in_title = False
        self.title = ""

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip += 1
        if tag == "title":
            self.in_title = True
        if tag == "a":
            href = dict(attrs).get("href", "")
            if href:
                self.links.append(href)

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self.skip = max(0, self.skip - 1)
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if not self.skip and data.strip():
            self.text.append(data.strip())


def policy(url):
    site_origin = origin(url)
    if site_origin in _policies and time.monotonic() - _policy_checked[site_origin] < 300:
        return _policies[site_origin]
    robots = RobotFileParser()
    robots_url = site_origin + "/robots.txt"
    visited = set()
    for _ in range(6):
        if robots_url in visited:
            raise SafetyError("Robots policy redirect loop detected.")
        visited.add(robots_url)
        try:
            rules = fetch(robots_url, origin(robots_url), 100_000)
            robots.parse(rules.splitlines())
            break
        except RedirectSafetyError as exc:
            if not exc.location:
                raise SafetyError("Robots policy redirect had no destination.") from exc
            redirected = validate_url(urljoin(robots_url, exc.location))
            if urlsplit(robots_url).scheme == "https" and urlsplit(redirected).scheme != "https":
                raise SafetyError("Robots policy redirect attempted to downgrade HTTPS.") from exc
            robots_url = redirected
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 404:
                raise SafetyError("Robots policy could not be verified.") from exc
            robots.parse([])
            break
    else:
        raise SafetyError("Robots policy exceeded the bounded redirect limit.")
    delay = max(
        robots.crawl_delay(BOT_NAME) or 0,
        5 if site_origin == "https://docs.aws.amazon.com" else 0,
    )
    if delay > 30:
        raise SafetyError("The website crawl delay exceeds this worker's bounded execution policy.")
    _delays[site_origin] = delay
    _policies[site_origin] = robots
    _policy_checked[site_origin] = time.monotonic()
    return robots


def inspect_site(url, pages=None):
    from .fixture import FIXTURES, fixture_html, fixture_site, is_fixture_url

    if is_fixture_url(url):
        site = fixture_site(url)
        pages = FIXTURES[site]["pages"]
        return [
            {
                "id": f"source-{i + 1}",
                "page_id": k,
                "url": f"fixture://{site}/{k}",
                "title": v[0],
                "excerpt": v[1],
                "sha256": hashlib.sha256(fixture_html(k, site).encode()).hexdigest(),
                "fixture": True,
                "fixture_site": site,
            }
            for i, (k, v) in enumerate(pages.items())
        ]
    target = validate_url(url)
    site_origin = origin(target)
    robots = policy(target)
    if not robots.can_fetch(BOT_NAME, target):
        raise SafetyError("The website disallows automated inspection.")
    pending = list(pages)[:3] if pages else [target]
    result = []
    seen = set()
    while pending and len(result) < 3:
        current = pending.pop(0)
        if current in seen:
            continue
        seen.add(current)
        if not robots.can_fetch(BOT_NAME, current):
            continue
        try:
            raw = fetch(current, site_origin)
        except httpx.HTTPStatusError as exc:
            if pages and exc.response.status_code in (404, 410):
                continue
            raise
        parser = PageParser()
        parser.feed(raw)
        excerpt = " ".join(parser.text)[:6000]
        reject_verification_page(excerpt)
        if len(excerpt) < 80:
            continue
        result.append(
            {
                "id": f"source-{len(result) + 1}",
                "page_id": f"page-{len(result) + 1}",
                "url": current,
                "title": parser.title[:150] or current,
                "excerpt": excerpt,
                "sha256": hashlib.sha256(raw.encode()).hexdigest(),
                "fixture": False,
                "retrieved_at": time.time(),
            }
        )
        if len(result) == 1 and not pages:
            for link in parser.links:
                candidate = urljoin(current, link).split("#")[0]
                u = urlsplit(candidate)
                if (
                    origin(candidate) == site_origin
                    and u.path.startswith(urlsplit(target).path.rsplit("/", 1)[0] + "/")
                    and not u.query
                    and not u.path.endswith((".pdf", ".md", ".zip", ".json"))
                    and not any(
                        x in u.path.lower()
                        for x in ["logout", "delete", "checkout", "login", "signup", "download"]
                    )
                    and candidate not in pending
                ):
                    pending.append(candidate)
                    if len(pending) >= 5:
                        break
    if not result:
        raise SafetyError("No usable official page evidence was found.")
    return result
