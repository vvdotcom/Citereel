"""Evidence attribution, not an automated truth guarantee."""

import re
import unicodedata


def normalize(text):
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def claim_ledger(plan, evidence):
    known = {s["id"]: s for s in evidence}
    entries = []
    for index, scene in enumerate(plan["scenes"], 1):
        cited = [known[s] for s in scene["source_ids"] if s in known]
        for kind in ("title", "on_screen_copy", "narration"):
            claim = scene[kind]
            sentences = [x.strip() for x in re.split(r"(?<=[.!?])\s+", claim) if x.strip()]
            matches = []
            for sentence in sentences:
                match = next(
                    (
                        s
                        for s in cited
                        if normalize(sentence).rstrip(".!?")
                        in normalize(s["title"] + " " + s["excerpt"])
                    ),
                    None,
                )
                if match:
                    matches.append({"source_id": match["id"], "quote": sentence})
            entries.append(
                {
                    "scene": index,
                    "kind": kind,
                    "claim": claim,
                    "status": "source_matched"
                    if cited and len(matches) == len(sentences)
                    else "needs_review",
                    "matches": matches,
                    "sources": [
                        {k: s[k] for k in ("id", "title", "url", "sha256", "excerpt")}
                        for s in cited
                    ],
                    "explanation": "Exact wording found in the cited source; this is not independent fact verification."
                    if cited and len(matches) == len(sentences)
                    else "Paraphrase or unsupported wording. A person must review the source before recording.",
                }
            )
    return entries


def reject_unknown_numbers(scene, evidence):
    known = {s["id"]: s for s in evidence}
    source_text = " ".join(
        known[s]["title"] + " " + known[s]["excerpt"] for s in scene.source_ids if s in known
    )
    numbers = set(re.findall(r"\d+(?:[.,]\d+)*%?", source_text))
    claimed = set(
        re.findall(
            r"\d+(?:[.,]\d+)*%?", scene.title + " " + scene.narration + " " + scene.on_screen_copy
        )
    )
    unsupported = sorted(claimed - numbers)
    if unsupported:
        raise ValueError(
            "A numerical claim is absent from the cited evidence. Remove these exact "
            f"unsupported token(s): {', '.join(unsupported)}. Do not resubmit them unless "
            "they appear in the cited source excerpt."
        )
