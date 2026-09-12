"""Original, owned product fixtures; no external website or copied media."""

FIXTURES = {
    "northstar": {
        "brand": "northstar",
        "context": "Product research / Demo workspace",
        "label": "Research, with context",
        "pages": {
            "overview": (
                "Northstar research workspace",
                "Bring your research into one workspace. Save source links with your notes. Compare evidence before making a product decision.",
            ),
            "evidence": (
                "Evidence library",
                "Keep the source beside the finding. Each research note includes its source link and review status. Open a saved source to inspect the original context.",
            ),
            "decisions": (
                "Decision review",
                "Review findings with your team. Link each decision to supporting evidence. Mark a decision ready only after a person reviews it.",
            ),
        },
        "rows": [
            ("Customer interviews", "Research notes", "Reviewed"),
            ("Product documentation", "Official source", "Reviewed"),
            ("Launch narrative", "Team decision", "Needs review"),
        ],
    },
    "relay": {
        "brand": "relay",
        "context": "Release operations / Demo workspace",
        "label": "Release work, in one place",
        "pages": {
            "overview": (
                "Relay release workspace",
                "Coordinate every release from a single workspace. Keep owners, launch notes and readiness checks visible to the whole team.",
            ),
            "readiness": (
                "Readiness checks",
                "Track launch criteria before a release moves forward. Every check has an owner, current status and a clear handoff.",
            ),
            "notes": (
                "Launch notes",
                "Turn approved changes into a clear launch narrative. Keep customer-facing notes linked to the work that shipped.",
            ),
        },
        "rows": [
            ("Authentication update", "Engineering", "Ready"),
            ("Customer migration", "Success", "In review"),
            ("Release announcement", "Marketing", "Ready"),
        ],
    },
}

# Kept as a compatibility alias for fixtures and tests that import the original demo pages.
PAGES = FIXTURES["northstar"]["pages"]


def fixture_site(url):
    if not url.startswith("fixture://"):
        raise ValueError("Not an owned fixture URL.")
    site = url.split("://", 1)[1].split("/", 1)[0]
    if site not in FIXTURES:
        raise ValueError("Unknown owned fixture website.")
    return site


def is_fixture_url(url):
    try:
        fixture_site(url)
        return True
    except ValueError:
        return False


def fixture_html(key="overview", site="northstar"):
    fixture = FIXTURES[site]
    pages = fixture["pages"]
    title, body = pages[key]
    links = "".join(
        f'<a href="https://fixture.launchpad.invalid/{site}/{k}" aria-current="{str(k == key).lower()}">{"Overview" if k == "overview" else v[0]}</a>'
        for k, v in pages.items()
    )
    rows = "".join(f"<tr><td>{a}</td><td>{b}</td><td>{c}</td></tr>" for a, b, c in fixture["rows"])
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{title}</title>
    <style>*{{box-sizing:border-box}}body{{margin:0;background:#f6f8f7;color:#203b30;font:16px system-ui}}header{{padding:24px 38px;border-bottom:1px solid #d5dfd9;display:flex;justify-content:space-between;background:white}}header b{{font-size:24px}}.layout{{display:grid;grid-template-columns:220px 1fr;min-height:800px}}nav{{padding:30px 20px;border-right:1px solid #d5dfd9}}a{{display:block;padding:14px;color:#466453;text-decoration:none;border-radius:5px}}a[aria-current=true]{{background:#dfebe3;font-weight:700}}main{{padding:55px 60px;max-width:1050px}}h1{{font-size:52px;line-height:1.04;letter-spacing:-2px;max-width:730px;margin:18px 0}}p{{font-size:19px;line-height:1.7;color:#5a7063;max-width:720px}}table{{width:100%;border-collapse:collapse;background:white;margin-top:40px}}td,th{{text-align:left;padding:22px;border-bottom:1px solid #dce5df}}th{{font-size:13px;color:#6b8175}}footer{{margin-top:95px;border-top:1px solid #dce5df;padding-top:25px;color:#60786b}}.label{{color:#26754d;font-weight:600}}</style></head>
    <body><header><b>{fixture["brand"]}</b><span>{fixture["context"]}</span></header><div class="layout"><nav>{links}</nav><main><span class="label">{fixture["label"]}</span><h1>{title}</h1><p>{body}</p><table><thead><tr><th>Collection</th><th>Type</th><th>Review</th></tr></thead><tbody>{rows}</tbody></table><footer>{fixture['brand'].title()} demonstration workspace.</footer></main></div></body></html>"""
