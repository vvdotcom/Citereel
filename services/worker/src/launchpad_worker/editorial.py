"""Veyframe/ProjectV list-slide arrangements, rendered in Launchpad's Amazon palette.

Geometry follows presentation-story@2's workflow rail, product activity and
workflow highlights masters. Text comes only from the reviewed scene, never
from the reference's specimen claims or an additional model call.
"""

import re

from PIL import Image, ImageDraw

KINDS = (
    "hero",
    "workflow",
    "activity",
    "highlights",
    "wide",
    "workflow-right",
    "bottom-items",
    "focus",
)
LIST_KINDS = {"workflow", "activity", "highlights", "workflow-right", "bottom-items"}
RADIUS = 36
APERTURES = {
    "workflow": (930, 218, 1502, 1022),
    "activity": (128, 218, 1400, 1022),
    "highlights": (876, 218, 1556, 1022),
    "workflow-right": (128, 218, 1502, 1022),
    "bottom-items": (320, 218, 1920, 700),
    "focus": (128, 218, 2304, 1022),
}


def kind(request, index):
    if request["orientation"] == "landscape" and request["format"] in ("presentation", "spotlight"):
        return KINDS[index % len(KINDS)]
    return "standard"


def items(scene):
    # Preserve sentence wording (including punctuation, numbers and URLs).
    sentences = [
        value.strip()
        for value in re.split(r"(?<=[.!?;])\s+(?=[A-Z0-9])", scene["narration"])
        if value.strip()
    ]
    unique = list(dict.fromkeys(sentences))
    if not unique:
        raise ValueError("A list slide needs reviewed narration before rendering.")
    # Merge overflow, rather than silently discard reviewed content.
    return unique[:3] + [" ".join(unique[3:])] if len(unique) > 4 else unique


def text_lines(draw, text, face, width):
    lines, line = [], ""
    for word in text.split():
        trial = (line + " " + word).strip()
        if draw.textlength(trial, font=face) <= width:
            line = trial
            continue
        if line:
            lines.append(line)
            line = ""
        # Long identifiers/URLs must not escape the text region.
        for char in word:
            if line and draw.textlength(line + char, font=face) > width:
                lines.append(line)
                line = ""
            line += char
    if line:
        lines.append(line)
    return lines


def fit_text(draw, text, rect, font_factory, *, size=36, minimum=20, color="#f4f6f8"):
    x, y, width, height = rect
    for candidate in range(size, minimum - 1, -1):
        face = font_factory(candidate)
        lines = text_lines(draw, text, face, width)
        leading = round(candidate * 1.35)
        if len(lines) * leading <= height:
            for i, line in enumerate(lines):
                draw.text((x, y + i * leading), line, font=face, fill=color, anchor="lt")
            return len(lines) * leading
    raise ValueError("Scene text is too long for its list panel. Shorten the reviewed narration.")


def display_items(scene, selected, story_scenes=None):
    if selected not in LIST_KINDS:
        return []
    if selected in ("highlights", "bottom-items") and story_scenes:
        return list(dict.fromkeys(s["on_screen_copy"] for s in story_scenes))[:3]
    return items(scene)


def header_text(scene, index, brand_name, selected):
    if index == 0:
        return brand_name
    return {
        "workflow": "Workflow",
        "workflow-right": "Workflow",
        "activity": "Product details",
        "highlights": "Walkthrough highlights",
        "bottom-items": "At a glance",
    }.get(selected, scene["title"])


def rounded_mask(size, path):
    # Supersampled alpha genuinely clips footage corners, not just its border.
    w, h = size
    radius = min(RADIUS, w // 8, h // 8)
    mask = Image.new("L", (w * 3, h * 3), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, w * 3 - 1, h * 3 - 1), radius=radius * 3, fill=255
    )
    mask.resize((w, h), Image.Resampling.LANCZOS).save(path)


def draw_slide(scene, request, index, total, path, font_factory, brand_name, story_scenes=None):
    selected = kind(request, index)
    assert selected in APERTURES
    primary = (request.get("brand") or {}).get("primary_color") or "#ff9900"
    image = Image.new("RGB", (2560, 1440), "#232f3e")
    draw = ImageDraw.Draw(image)
    fit_text(
        draw,
        header_text(scene, index, brand_name, selected),
        (128, 72, 1800, 74),
        font_factory,
        size=44,
    )
    draw.text((2180, 88), f"{index + 1:02d} / {total:02d}", font=font_factory(30), fill=primary)
    draw.line((128, 176, 2432, 176), fill="#657789", width=2)
    entries = display_items(scene, selected, story_scenes)

    if selected == "focus":
        pass
    elif selected == "bottom-items":
        entries = entries[:2] + [" ".join(entries[2:])] if len(entries) > 3 else entries
        card_width = (2304 - 24 * (len(entries) - 1)) // len(entries)
        for n, entry in enumerate(entries):
            left = 128 + n * (card_width + 24)
            draw.rounded_rectangle(
                (left, 952, left + card_width, 1240),
                radius=RADIUS,
                fill="#182330",
                outline="#748699",
                width=2,
            )
            draw.text((left + 32, 980), f"{n + 1:02d}", font=font_factory(28), fill=primary)
            fit_text(draw, entry, (left + 32, 1036, card_width - 64, 172), font_factory, size=34)
    elif selected == "activity":
        panel_x, panel_width = 1608, 824
        fit_text(draw, scene["title"], (panel_x, 222, panel_width, 102), font_factory, size=46)
        draw.line((panel_x, 340, 2432, 340), fill=primary, width=2)
        gap = 16
        row_height = min(204, (880 - gap * (len(entries) - 1)) // len(entries))
        for n, entry in enumerate(entries):
            top = 360 + n * (row_height + gap)
            draw.rounded_rectangle(
                (panel_x, top, 2432, top + row_height),
                radius=RADIUS,
                fill="#182330",
                outline="#748699",
                width=2,
            )
            draw.text((panel_x + 28, top + 20), f"{n + 1:02d}", font=font_factory(26), fill=primary)
            fit_text(
                draw,
                entry,
                (panel_x + 28, top + 62, panel_width - 56, row_height - 80),
                font_factory,
                size=34,
            )
    else:
        light = selected == "highlights"
        panel_left = 1704 if selected == "workflow-right" else 128
        panel_right = 2432 if selected == "workflow-right" else (804 if light else 858)
        ink = "#232f3e" if light else "#f4f6f8"
        draw.rounded_rectangle(
            (panel_left, 218, panel_right, 1240),
            radius=RADIUS,
            fill="#fff1d6" if light else "#111b26",
            outline="#8997a5" if not light else None,
            width=2,
        )
        left, inner_width = panel_left + 56, panel_right - panel_left - 112
        fit_text(
            draw,
            "In this walkthrough" if light and story_scenes else scene["title"],
            (left, 276, inner_width, 190),
            font_factory,
            size=56,
            color=ink,
        )
        count = len(entries)
        gap = 28 if light else 32
        row_height = min(184, (696 - gap * (count - 1)) // count)
        for n, entry in enumerate(entries):
            top = 500 + n * (row_height + gap)
            if light:
                draw.ellipse((left + 4, top + 13, left + 16, top + 25), fill="#9a5700")
                fit_text(
                    draw,
                    entry,
                    (left + 40, top, inner_width - 40, row_height),
                    font_factory,
                    size=32,
                    color=ink,
                )
            else:
                draw.rounded_rectangle(
                    (left, top, panel_right - 56, top + row_height), radius=24, fill="#34465a"
                )
                draw.rounded_rectangle(
                    (left + 12, top + 20, left + 16, top + row_height - 20), radius=2, fill=primary
                )
                fit_text(
                    draw,
                    entry,
                    (left + 28, top + 22, inner_width - 56, row_height - 44),
                    font_factory,
                    size=32,
                )

    x, y, width, height = APERTURES[selected]
    draw.rounded_rectangle(
        (x - 2, y - 2, x + width + 2, y + height + 2), radius=RADIUS + 2, outline="#8997a5", width=2
    )
    # Caption overlay is unchanged and remains below the product/list panels.
    if index == total - 1:
        fit_text(
            draw,
            request.get("call_to_action", ""),
            (1340, 1370, 1092, 44),
            font_factory,
            size=28,
            color=primary,
        )
    image.save(path)
