"""Text-based website changes and safe reuse of unchanged browser footage."""

import hashlib
import json
import time


def text_hash(source):
    return hashlib.sha256(" ".join(source["excerpt"].split()).encode()).hexdigest()


def recording_key(scene, evidence, request=None, index=0):
    from .circuit import content_scale
    from .render import layout

    geometry = layout(request, index)[1][2:] if request else (1600, 900)
    source = next(s for s in evidence if s["page_id"] == scene["page_id"])
    return hashlib.sha256(
        json.dumps(
            [
                source["url"],
                text_hash(source),
                scene["scroll"],
                "visible-interactions-v6",
                geometry,
                content_scale(request) if request else 1.4,
                request.get("duration_seconds", 45) if request else 45,
            ]
        ).encode()
    ).hexdigest()


def compare_sources(job, fresh):
    old_by_url = {s["url"]: s for s in job["evidence"]}
    normalized = []
    for n, source in enumerate(fresh):
        source = dict(source)
        old = old_by_url.get(source["url"])
        source.update(
            id=old["id"] if old else f"new-source-{n}",
            page_id=old["page_id"] if old else f"new-page-{n}",
        )
        normalized.append(source)
    new_by_url = {s["url"]: s for s in normalized}
    changes = []
    changed_ids = set()
    for url, old in old_by_url.items():
        new = new_by_url.get(url)
        if new is None or text_hash(old) != text_hash(new):
            changed_ids.add(old["id"])
            changes.append(
                {
                    "url": url,
                    "source_id": old["id"],
                    "before": old["excerpt"],
                    "after": new["excerpt"] if new else None,
                    "kind": "changed" if new else "removed",
                }
            )
    for url, new in new_by_url.items():
        if url not in old_by_url:
            changes.append(
                {
                    "url": url,
                    "source_id": new["id"],
                    "before": None,
                    "after": new["excerpt"],
                    "kind": "added",
                }
            )
    affected = [
        n + 1
        for n, s in enumerate(job["plan"]["scenes"])
        if changed_ids.intersection(s["source_ids"])
    ]
    return {
        "checked_at": time.time(),
        "changes": changes,
        "affected_scenes": affected,
        "evidence": normalized,
        "method": "Comparison of normalized inspected text; not a visual or whole-site diff.",
    }
