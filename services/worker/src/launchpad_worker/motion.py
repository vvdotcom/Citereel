"""Deterministic product-film composition: staged type, real footage, clean holds.

All text is rendered with Pillow, never interpolated into FFmpeg expressions.
The caller owns the footage and approved copy. No model-generated commands run.
"""

import hashlib
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def command(args, cwd=None, timeout=600):
    result = subprocess.run(args, cwd=cwd, capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(
            "Motion render failed: " + result.stderr.decode(errors="replace")[-1600:]
        )
    return result.stdout


def probe(path):
    return json.loads(
        command(
            ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]
        )
    )


def layout(request, index=0):
    if request["orientation"] == "portrait":
        return (1080, 1920), (48, 590, 984, 1170)
    return (2560, 1440), (96, 292, 2368, 1052)


def typeface(size, weight=400):
    path = Path(__file__).resolve().parents[4] / "assets" / "InterVariable.ttf"
    face = ImageFont.truetype(str(path), max(12, round(size)))
    face.set_variation_by_axes([min(32, max(14, size)), weight])
    return face


def fit_lines(text, width, size, limit, weight=650):
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    first_size = max(12, round(size))
    for current in range(first_size, min(first_size, 18) - 1, -2):
        face = typeface(current, weight)
        lines = []
        for paragraph in text.split("\n"):
            row = ""
            for word in paragraph.split():
                candidate = (row + " " + word).strip()
                if row and draw.textlength(candidate, font=face) > width:
                    lines.append(row)
                    row = word
                else:
                    row = candidate
            if row:
                lines.append(row)
        if len(lines) <= limit and all(draw.textlength(row, font=face) <= width for row in lines):
            return lines, face, current
    raise ValueError("Motion title is too long for the available space. Shorten the reviewed copy.")


def presenter_geometry(size, subtitle_safe_bottom, source_size):
    """A 30/70 text/video split, centered above the subtitle reserve."""
    width, height = size
    scale = width / 1920
    margin = round(48 * scale)
    gap = round(32 * scale)
    available = width - 2 * margin - gap
    copy_width = round(available * 0.30) // 2 * 2
    video_width = (available - copy_width) // 2 * 2
    top = round(120 * scale)
    bottom = height - subtitle_safe_bottom - round(70 * scale)
    center_y = (top + bottom) / 2
    source_width, source_height = source_size
    video_height = min(bottom - top, video_width * source_height / source_width)
    video_height = round(video_height) // 2 * 2
    box = (
        margin + copy_width + gap,
        round(center_y - video_height / 2),
        video_width,
        video_height,
    )
    return box, (margin, copy_width, top, bottom, center_y)


def render_scene(
    clip,
    output,
    *,
    duration,
    title,
    body="",
    brand="",
    logo=None,
    eyebrow="",
    pitch=None,
    accent="#3875e5",
    kind="desktop",
    size=(1920, 1080),
    box=None,
    footage_fit="contain",
    audio=None,
    captions=None,
    note="",
    subtitle_safe_bottom=0,
    check=lambda: None,
):
    """Render reviewed footage; walkthrough keeps the full workspace prominent."""
    if kind not in {
        "desktop",
        "split",
        "mobile",
        "statement",
        "end",
        "pitch",
        "walkthrough",
        "presenter",
    }:
        raise ValueError("Unsupported motion layout.")
    if not 0 < duration <= 1800 or min(size) < 240 or any(v % 2 for v in size):
        raise ValueError("Invalid motion canvas or duration.")
    if footage_fit not in {"contain", "stretch"}:
        raise ValueError("Unsupported footage fit.")
    output = Path(output).resolve()
    folder = output.parent / (output.stem + "-layers")
    folder.mkdir(parents=True, exist_ok=True)
    width, height = size
    if type(subtitle_safe_bottom) is not int or not 0 <= subtitle_safe_bottom <= height // 3:
        raise ValueError("Invalid subtitle reserve.")
    content_height = height - subtitle_safe_bottom
    if kind == "pitch" and (height > width or not clip or not pitch):
        raise ValueError("A pitch slide needs landscape footage and reviewed pitch copy.")
    scale = width / 1920
    margin = round((40 if kind == "walkthrough" else 48 if kind == "presenter" else 72) * scale)
    presenter = None
    if kind == "presenter":
        if not clip or height > width:
            raise ValueError("A presenter scene needs landscape footage.")
        video_info = next(s for s in probe(clip)["streams"] if s["codec_type"] == "video")
        default_box, presenter = presenter_geometry(
            size, subtitle_safe_bottom, (video_info["width"], video_info["height"])
        )
        box = box or default_box
    draw_color = "#f4f7fc"
    image = Image.new("RGB", size, "#101a2a")
    draw = ImageDraw.Draw(image)
    if logo and kind != "walkthrough":
        mark_size = round(44 * scale)
        with Image.open(logo) as source_mark:
            mark = source_mark.convert("RGBA")
            mark.thumbnail((mark_size, mark_size), Image.Resampling.LANCZOS)
            image.paste(mark, (margin, round(30 * scale)), mark)
        draw.text(
            (margin + mark_size + round(12 * scale), round(52 * scale)),
            brand,
            fill=draw_color,
            font=typeface(32 * scale, weight=650),
            anchor="lm",
        )
    elif kind != "walkthrough":
        draw.text((margin, round(34 * scale)), brand, fill=draw_color, font=typeface(24 * scale))
    if kind == "presenter":
        draw.line(
            (margin, round(94 * scale), width - margin, round(94 * scale)),
            fill="#33445e",
            width=max(1, round(scale)),
        )
    if eyebrow and kind != "presenter":
        draw.text(
            (margin, round(height * (0.157 if kind == "pitch" else 0.21))),
            eyebrow,
            fill=accent,
            font=typeface(24 * scale, weight=600),
        )
    if kind != "walkthrough":
        draw.rectangle(
            (
                margin,
                content_height - round(44 * scale),
                margin + round(42 * scale),
                content_height - round(40 * scale),
            ),
            fill=accent,
        )
    if note and kind != "walkthrough":
        draw.text(
            (margin + round(58 * scale), content_height - round(54 * scale)),
            note,
            fill="#a6b5cd",
            font=typeface(17 * scale),
        )
    if box is None:
        if kind == "walkthrough":
            box = (
                margin,
                round(56 * scale),
                (width - 2 * margin) // 2 * 2,
                (content_height - round(68 * scale)) // 2 * 2,
            )
        elif kind == "desktop":
            box = (
                margin,
                round(220 * scale),
                width - 2 * margin,
                content_height - round(300 * scale),
            )
        elif kind == "split":
            box = (
                round(width * 0.41),
                round(content_height * 0.23),
                round(width * 0.55) // 2 * 2,
                round(content_height * 0.64) // 2 * 2,
            )
        elif kind == "mobile":
            box = (
                round(width * 0.67),
                round(content_height * 0.10),
                round(content_height * 0.38) // 2 * 2,
                round(content_height * 0.82) // 2 * 2,
            )
        elif kind == "pitch":
            box = (
                round(832 * scale),
                round(350 * scale),
                round(1016 * scale) // 2 * 2,
                (round(532 * scale) - subtitle_safe_bottom // 2) // 2 * 2,
            )
    if clip and kind not in {"statement", "end"}:
        x, y, bw, bh = box
        border = max(1, round(3 * scale))
        radius = max(border + 1, round(16 * scale))
        if (
            min(bw, bh) <= 0
            or min(x, y) < border
            or x + bw + border > width
            or y + bh + border > content_height
        ):
            raise ValueError("Footage box exceeds the canvas.")
        draw.rounded_rectangle(
            (x - border, y - border, x + bw + border - 1, y + bh + border - 1),
            radius=radius,
            fill="#33445e",
        )
        # A square video overlay otherwise paints over the rounded border corners.
        mask = Image.new("L", (bw * 4, bh * 4), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            (0, 0, bw * 4 - 1, bh * 4 - 1), radius=(radius - border) * 4, fill=255
        )
        mask.resize((bw, bh), Image.Resampling.LANCZOS).save(folder / "footage-mask.png")
    image.save(folder / "base.png")

    if kind == "presenter":
        title_pos = (margin, 0)
        # When a reviewed presenter scene supplies a wider footage box, reserve only
        # the remaining left column for copy. This keeps captions readable instead
        # of allowing them to overlap the recording.
        title_width = box[0] - margin - round(32 * scale)
        if title_width <= 0:
            raise ValueError("Presenter footage leaves no room for the copy column.")
        title_size = max(38 * scale, 66 * scale * min(1, title_width / presenter[1]))
        max_lines = 4
    elif kind == "walkthrough":
        title_pos = (margin, round(8 * scale))
        title_width, title_size, max_lines = width - 2 * margin, 28 * scale, 1
    elif kind == "pitch":
        title_pos = (margin, round(216 * scale))
        title_width, title_size, max_lines = round(660 * scale), 68 * scale, 2
    elif kind in {"statement", "end"}:
        title_pos = (margin, round(height * 0.28))
        title_width, title_size, max_lines = width - 2 * margin, 120 * scale, 3
    elif kind in {"split", "mobile"}:
        title_pos = (margin, round(height * 0.32))
        title_width, title_size, max_lines = (
            round(width * (0.34 if kind == "split" else 0.53)),
            78 * scale,
            3,
        )
    else:
        title_pos = (margin, round(86 * scale))
        title_width, title_size, max_lines = width - 2 * margin, 66 * scale, 1
    if height > width:
        title_pos = (margin, round(height * 0.085))
        title_width, title_size, max_lines = width - 2 * margin, 78 * scale, 3
    lines, face, font_size = fit_lines(title, title_width, title_size, max_lines)
    body_layout = None
    if body:
        body_width = title_width if kind != "desktop" else round(width * 0.85)
        body_layout = fit_lines(
            body, body_width, 28 * scale, 7 if kind == "presenter" else 4, weight=400
        )
    pitch_rows = []
    if kind == "presenter" and pitch:
        for label, key in [
            ("THE PROBLEM", "problem"),
            ("WHO IT IS FOR", "audience"),
            ("WHY IT MATTERS", "value"),
        ]:
            rows, row_face, row_size = fit_lines(pitch[key], title_width, 28 * scale, 3, weight=450)
            pitch_rows.append((label, rows, row_face, row_size))
    if kind == "presenter":
        title_height = round((len(lines) - 1) * font_size * 1.18 + font_size * 1.25)
        group_height = title_height
        if body_layout:
            group_height += round(34 * scale + body_layout[2] * 1.45 * len(body_layout[0]) + 12)
        for _, rows, _, row_size in pitch_rows:
            group_height += round(32 * scale + 24 * scale + 8 * scale + len(rows) * row_size * 1.4)
        if group_height > presenter[3] - presenter[2]:
            raise ValueError("Presenter copy exceeds its column. Shorten the reviewed copy.")
        title_pos = (margin, round(presenter[4] - group_height / 2))
    layers = []
    for index, line in enumerate(lines):
        layer = Image.new("RGBA", (title_width, round(font_size * 1.45)), (0, 0, 0, 0))
        painter = ImageDraw.Draw(layer)
        painter.text(
            (0, 0),
            line,
            font=face,
            fill=accent if index == len(lines) - 1 and len(lines) > 1 else draw_color,
        )
        path = folder / f"title-{index}.png"
        layer.save(path)
        layers.append(
            (path, title_pos[0], title_pos[1] + round(index * font_size * 1.18), 0.2 + index * 0.16)
        )
    if body:
        body_width = title_width if kind != "desktop" else round(width * 0.85)
        body_lines, body_face, body_size = body_layout
        layer = Image.new(
            "RGBA", (body_width, round(body_size * 1.5 * len(body_lines) + 12)), (0, 0, 0, 0)
        )
        painter = ImageDraw.Draw(layer)
        for i, row in enumerate(body_lines):
            painter.text((0, round(i * body_size * 1.45)), row, font=body_face, fill="#afbed3")
        path = folder / "body.png"
        layer.save(path)
        body_y = title_pos[1] + round(len(lines) * font_size * 1.18 + 34 * scale)
        if kind == "desktop":
            body_y = round(173 * scale)
        if body_y + layer.height > content_height - margin:
            raise ValueError("Motion copy would be clipped. Shorten the scene copy.")
        layers.append((path, title_pos[0], body_y, 0.65))

    if pitch_rows:
        row_y = title_pos[1] + title_height
        if body_layout:
            row_y = body_y + layer.height
        for index, (label, rows, row_face, row_size) in enumerate(pitch_rows):
            row_y += round(32 * scale)
            row_height = round(24 * scale + 8 * scale + len(rows) * row_size * 1.4)
            layer = Image.new("RGBA", (title_width, row_height + round(8 * scale)), (0, 0, 0, 0))
            painter = ImageDraw.Draw(layer)
            painter.text((0, 0), label, font=typeface(20 * scale, 600), fill=accent)
            for n, row in enumerate(rows):
                painter.text(
                    (0, round(32 * scale + n * row_size * 1.4)), row, font=row_face, fill=draw_color
                )
            path = folder / f"presenter-pitch-{index}.png"
            layer.save(path)
            layers.append((path, margin, row_y, 0.65 + index * 0.2))
            row_y += row_height

    if kind == "pitch":
        # One continuous slide: all pitch points remain visible beside real footage.
        def copy_layer(name, text, x, y, available_width, font_size, limit, color, weight, delay):
            rows, face, fitted_size = fit_lines(
                text, round(available_width * scale), font_size * scale, limit, weight=weight
            )
            leading = round(fitted_size * 1.4)
            layer = Image.new(
                "RGBA",
                (round(available_width * scale), leading * len(rows) + round(12 * scale)),
                (0, 0, 0, 0),
            )
            painter = ImageDraw.Draw(layer)
            for index, row in enumerate(rows):
                painter.text((0, leading * index), row, font=face, fill=color)
            path = folder / f"pitch-{name}.png"
            layer.save(path)
            layers.append((path, round(x * scale), round(y * scale), delay))

        for name, label, text, x, label_y, text_y, copy_width, copy_size, delay in (
            ("audience", "WHO IT IS FOR", pitch["audience"], 72, 458, 500, 660, 34, 0.45),
            ("value", "WHY IT MATTERS", pitch["value"], 72, 652, 694, 660, 32, 0.65),
            ("solution", "THE SOLUTION", pitch["solution"], 832, 170, 212, 1016, 36, 0.35),
        ):
            copy_layer(name + "-label", label, x, label_y, copy_width, 22, 1, accent, 600, delay)
            copy_layer(
                name, text, x, text_y, copy_width, copy_size, 3, draw_color, 500, delay + 0.1
            )
        if pitch.get("caption"):
            copy_layer(
                "caption",
                pitch["caption"],
                832,
                910 - subtitle_safe_bottom / (2 * scale),
                1016,
                25,
                1,
                "#afbed3",
                400,
                0.8,
            )

    args = [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-threads",
        "2",
        "-loop",
        "1",
        "-framerate",
        "30",
        "-i",
        str(folder / "base.png"),
    ]
    filters = ["[0:v]format=rgba[base]"]
    current = "base"
    input_index = 1
    if clip and kind not in {"statement", "end"}:
        args += ["-i", str(Path(clip).resolve())]
        args += ["-loop", "1", "-framerate", "30", "-i", str(folder / "footage-mask.png")]
        x, y, bw, bh = box
        # Play every recorded interaction once; hold the last frame if needed.
        footage_scale = (
            f"scale={bw}:{bh}:flags=lanczos"
            if footage_fit == "stretch"
            else f"scale={bw}:{bh}:force_original_aspect_ratio=decrease:force_divisible_by=2:flags=lanczos,pad={bw}:{bh}:(ow-iw)/2:(oh-ih)/2:color=0xf5f7fb"
        )
        filters += [
            f"[{input_index}:v]fps=30,{footage_scale},setsar=1,tpad=stop_mode=clone:stop_duration={duration},format=rgb24[footage]",
            f"[{input_index + 1}:v]format=gray[mask]",
            "[footage][mask]alphamerge[rounded]",
            f"[{current}][rounded]overlay={x}:{y}:eof_action=repeat[screen]",
        ]
        current = "screen"
        input_index += 2
    for n, (path, x, y, delay) in enumerate(layers):
        args += ["-loop", "1", "-framerate", "30", "-i", str(path)]
        filters += [
            f"[{input_index}:v]format=rgba,fade=t=in:st={delay}:d=0.42:alpha=1[type{n}]",
            f"[{current}][type{n}]overlay=x={x}:y='{y}+24*pow(1-min(1,max(0,(t-{delay})/0.55)),3)':eof_action=repeat[layer{n}]",
        ]
        current = f"layer{n}"
        input_index += 1
    if captions:
        import shutil

        shutil.copyfile(captions, folder / "captions.ass")
        filters += [f"[{current}]ass=captions.ass[captioned]"]
        current = "captioned"
    if kind in {"walkthrough", "presenter"}:
        filters += [f"[{current}]format=yuv420p[out]"]
    else:
        filters += [
            f"[{current}]fade=t=in:st=0:d=0.16,fade=t=out:st={max(0.2, duration - 0.18)}:d=0.18,format=yuv420p[out]"
        ]
    if audio:
        audio_path, tempo = audio
        args += ["-i", str(Path(audio_path).resolve())]
        filters += [
            f"[{input_index}:a]atempo={tempo:.5f},apad,atrim=0:{duration},afade=t=out:st={duration - 0.15}:d=0.15[sound]"
        ]
    args += ["-filter_complex_threads", "2", "-filter_complex", ";".join(filters), "-map", "[out]"]
    args += ["-map", "[sound]", "-c:a", "aac", "-b:a", "160k"] if audio else ["-an"]
    args += [
        "-t",
        str(duration),
        "-r",
        "30",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "18",
        "-threads",
        "2",
        "-movflags",
        "+faststart",
        str(output),
    ]
    check()
    command(args, cwd=folder, timeout=max(600, duration * 5))
    check()
    return output


def assemble(clips, output, expected_duration):
    """Join codec-compatible scene files and verify the delivery artifact."""
    output = Path(output).resolve()
    listing = output.parent / "motion-concat.txt"
    # Paths are generated local files; escape quote characters for concat syntax.
    listing.write_text(
        "\n".join(
            "file '" + str(Path(p).resolve()).replace("\\", "/").replace("'", "'\\''") + "'"
            for p in clips
        ),
        encoding="utf-8",
    )
    command(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(listing),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    info = probe(output)
    if abs(float(info["format"]["duration"]) - expected_duration) > 0.25:
        raise ValueError("Motion export duration does not match the storyboard.")
    return {
        "duration_seconds": float(info["format"]["duration"]),
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "bytes": output.stat().st_size,
    }
