import hashlib
import json
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

from launchpad_api.settings import ROOT
from PIL import Image, ImageDraw, ImageFont

from . import circuit, editorial
from .speech import synthesize


def run(args, cwd=None, timeout=180):
    result = subprocess.run(
        args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout
    )
    if result.returncode:
        # Only deterministic media commands reach this runner; never model text as command code.
        raise RuntimeError(
            "Media processing failed: " + result.stderr.decode(errors="replace")[-1400:]
        )
    return result.stdout


def probe(path):
    return json.loads(
        run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)])
    )


def font(size):
    for path in (
        ROOT / "assets" / "InterVariable.ttf",
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size=size)


def wrapped(draw, text, xy, size, width, color, max_lines=5):
    face = font(size)
    lines = []
    line = ""
    for word in text.split():
        trial = (line + " " + word).strip()
        if draw.textlength(trial, font=face) > width and line:
            lines.append(line)
            line = word
        else:
            line = trial
    if line:
        lines.append(line)
    for i, line in enumerate(lines[:max_lines]):
        draw.text((xy[0], xy[1] + i * int(size * 1.25)), line, font=face, fill=color)
    return len(lines[:max_lines]) * int(size * 1.25)


def product_name(request):
    """Explicit product identity, or a source-derived label; never our watermark."""
    name = ((request.get("brand") or {}).get("name") or "").strip()
    if name:
        return name[:60]
    source = urlsplit(request.get("website_url", ""))
    if source.scheme == "fixture":
        return source.netloc.title()[:60]
    return (source.hostname or request.get("title") or "Product demo").removeprefix("www.")[:60]


def layout(request, index=0):
    return circuit.layout(request, index)


def legacy_layout(request, index=0):
    selected = editorial.kind(request, index)
    if selected in editorial.APERTURES:
        return (2560, 1440), editorial.APERTURES[selected]
    if request["orientation"] == "portrait":
        return (1080, 1920), (60, 760, 960, 820)
    if request["format"] == "presentation":
        # Alternate an editorial split with an unobstructed product walkthrough.
        return (
            ((2560, 1440), (880, 248, 1600, 900))
            if selected == "hero"
            else ((2560, 1440), (320, 250, 1920, 960))
        )
    if request["format"] == "spotlight":
        return (2560, 1440), (880, 248, 1600, 900)
    return (2560, 1440), (160, 250, 2240, 960)


def background(scene, request, index, total, path, story_scenes=None):
    return circuit.draw_slide(
        scene, request, index, total, path, font, product_name(request), story_scenes
    )


def legacy_background(scene, request, index, total, path, story_scenes=None):
    if editorial.kind(request, index) in editorial.APERTURES:
        return editorial.draw_slide(
            scene, request, index, total, path, font, product_name(request), story_scenes
        )
    (w, h), box = legacy_layout(request, index)
    scale = w / (720 if request["orientation"] == "portrait" else 1280)

    def unit(value):
        return round(value * scale)

    brand = request.get("brand") or {}
    primary = brand.get("primary_color") or "#ff9900"
    brand_name = editorial.header_text(
        scene, index, product_name(request), editorial.kind(request, index)
    )
    image = Image.new("RGB", (w, h), "#232f3e")
    draw = ImageDraw.Draw(image)
    draw.line((unit(40), unit(72), w - unit(40), unit(72)), fill="#576574", width=unit(1))
    brand_size = unit(22)
    while draw.textlength(brand_name, font=font(brand_size)) > w - unit(230) and brand_size > unit(
        12
    ):
        brand_size -= 1
    draw.text((unit(40), unit(30)), brand_name, font=font(brand_size), fill=primary)
    draw.text(
        (w - unit(150), unit(35)),
        f"{index + 1:02d} / {total:02d}",
        font=font(unit(15)),
        fill=primary,
    )
    if request["orientation"] == "portrait":
        y = unit(110)
        title_size = unit(38)
        width = unit(630)
        x = unit(40)
    elif request["format"] in ("presentation", "spotlight") and not (
        request["format"] == "presentation" and editorial.kind(request, index) == "wide"
    ):
        x = unit(40)
        y = unit(155)
        title_size = unit(36)
        width = box[0] - unit(80)
    else:
        x = unit(40)
        y = unit(85)
        title_size = unit(30)
        width = unit(1200)
    height = (
        wrapped(draw, scene["title"], (x, y), title_size, width, "#ffffff", 4) if index == 0 else 0
    )
    if (
        (request["format"] == "presentation" and editorial.kind(request, index) == "hero")
        or request["orientation"] == "portrait"
        or request["format"] == "spotlight"
    ):
        wrapped(
            draw, scene["on_screen_copy"], (x, y + height + unit(25)), unit(20), width, "#c8d1da", 5
        )
    bx, by, bw, bh = box
    draw.rounded_rectangle(
        (bx - unit(2), by - unit(2), bx + bw + unit(2), by + bh + unit(2)),
        radius=editorial.RADIUS + unit(2),
        outline="#505a64",
        width=unit(2),
    )
    if index == total - 1:
        wrapped(
            draw,
            request.get("call_to_action", ""),
            (w // 2, h - unit(42)),
            unit(16),
            w // 2 - unit(40),
            primary,
            1,
        )
    image.save(path)


def caption_time(t):
    milliseconds = round(t * 1000)
    hours, milliseconds = divmod(milliseconds, 3600000)
    minutes, milliseconds = divmod(milliseconds, 60000)
    seconds, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"


def captions(text, duration, path, size):
    width, height = size
    scale = width / (720 if height > width else 1280)

    def stamp(t):
        centis = round(t * 100)
        seconds, cs = divmod(centis, 100)
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours}:{minutes:02}:{seconds:02}.{cs:02}"

    words = text.replace("\\", "").replace("{", "").replace("}", "").split()
    group_size = 5 if height > width else 8
    groups = [words[i : i + group_size] for i in range(0, len(words), group_size)]
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Inter,{round((30 if height > width else 28) * scale)},&H000099FF,&H00FFFFFF,&H00182028,&H80182028,0,0,0,0,100,100,0,0,1,{round(2 * scale)},0,2,{round(40 * scale)},{round(40 * scale)},{round((180 if height > width else 65) * scale)},1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    elapsed = 0
    for group in groups:
        start = elapsed * duration / len(words)
        elapsed += len(group)
        end = elapsed * duration / len(words)
        highlighted = " ".join(
            "{\\kf" + str(max(1, round(100 * duration / len(words)))) + "}" + word for word in group
        )
        lines.append(f"Dialogue: 0,{stamp(start)},{stamp(end)},Default,,0,0,0,,{highlighted}")
    path.write_text(header + "\n".join(lines), encoding="utf-8")


def render(
    job, folder, clips, check=lambda: None, on_stage=lambda *args: None, *, cached_narration=None
):
    request = job["request"]
    scenes = job["plan"]["scenes"]
    total = request["duration_seconds"]
    duration = total / len(scenes)
    audio = []
    voice_receipts = []
    on_stage("narrating", "Synthesizing the validated scene narration.")
    for i, scene in enumerate(scenes):
        check()
        output, receipt = (
            cached_narration[i]
            if cached_narration is not None
            else synthesize(
                scene["narration"],
                folder / f"voice-{i + 1}.wav",
                request.get("narration_voice", "female"),
            )
        )
        info = probe(output)
        actual = float(info["format"]["duration"])
        ratio = actual / max(1, duration - 0.3)
        if ratio > 1.8:
            raise ValueError(
                "Narration is too long for this duration. Shorten the script in Storyboard."
            )
        audio.append((output, max(0.7, ratio)))
        voice_receipts.append(
            {**receipt, "scene": i + 1, "original_seconds": actual, "target_seconds": duration}
        )
    on_stage("rendering", "Composing real browser footage, narration, typography and captions.")
    (w, h), _ = layout(request)
    for i, scene in enumerate(scenes):
        check()
        _, (x, y, bw, bh) = layout(request, i)
        background(scene, request, i, len(scenes), folder / f"background-{i}.png", scenes)
        captions(scene["narration"], duration, folder / f"captions-{i}.ass", (w, h))
        editorial.rounded_mask((bw, bh), folder / f"mask-{i}.png")
        video_filter = f"[1:v]scale={bw}:{bh}:flags=lanczos:force_original_aspect_ratio=decrease:force_divisible_by=2,pad={bw}:{bh}:(ow-iw)/2:(oh-ih)/2:color=0x121920,setsar=1,fps=24,tpad=stop_mode=clone:stop_duration={duration},format=rgba[clip];[clip][3:v]alphamerge[rounded];[0:v][rounded]overlay={x}:{y}:shortest=1[composed]"
        tail = "[composed]"
        if request["captions"]:
            video_filter += f";[composed]ass=captions-{i}.ass[captioned]"
            tail = "[captioned]"
        video_filter += f";[2:a]atempo={audio[i][1]:.5f},apad,atrim=0:{duration},afade=t=out:st={duration - 0.15}:d=0.15[a]"
        args = [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-loop",
            "1",
            "-i",
            f"background-{i}.png",
            "-i",
            clips[i],
            "-i",
            str(audio[i][0]),
            "-loop",
            "1",
            "-i",
            f"mask-{i}.png",
            "-filter_complex",
            video_filter,
            "-map",
            tail,
            "-map",
            "[a]",
            "-t",
            str(duration),
            "-r",
            "24",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "17",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-movflags",
            "+faststart",
            f"render-{i}.mp4",
        ]
        run(args, cwd=folder, timeout=600)
    (folder / "concat.txt").write_text(
        "\n".join(f"file 'render-{i}.mp4'" for i in range(len(scenes))), encoding="utf-8"
    )
    output = folder / "export.mp4"
    run(
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
            "concat.txt",
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(output),
        ],
        cwd=folder,
    )
    on_stage("quality_check", "Checking video/audio streams, dimensions, duration and file hash.")
    info = probe(output)
    video = next((x for x in info["streams"] if x["codec_type"] == "video"), None)
    sound = next((x for x in info["streams"] if x["codec_type"] == "audio"), None)
    actual = float(info["format"]["duration"])
    if (
        not video
        or not sound
        or (video["width"], video["height"]) != (w, h)
        or abs(actual - total) > 1
    ):
        raise ValueError("Export did not pass stream, dimension or duration checks.")
    run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(output),
            "-ss",
            "2",
            "-frames:v",
            "1",
            str(folder / "poster.png"),
        ]
    )
    qa = {
        "duration_seconds": actual,
        "width": w,
        "height": h,
        "video_codec": video["codec_name"],
        "audio_codec": sound["codec_name"],
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "bytes": output.stat().st_size,
        "product_name": product_name(request),
        "template": "amazon-circuit-reference-v2-footage-first",
        "video_border": "shared-tablet-bezel",
        "browser_content_scale": circuit.content_scale(request),
        "camera_motion": "Disabled",
        "scene_duration_seconds": round(duration, 2),
        "pointer_sync": "Visible pointer follows narration-matched page content",
        "footage_playback": "Recorded interactions once, then hold final frame if needed; no click looping",
        "recorded_clicks": sum(e.get("action") == "click" for e in job.get("capture_events", [])),
        "heading_font": "Roboto Mono Bold",
        "footage_corner_radius": editorial.RADIUS,
        "scene_layouts": [
            {
                "scene": i + 1,
                "layout": circuit.kind(i),
                "reference_image": f"temp{i % len(circuit.KINDS) + 1}.jpg",
                "header": circuit.header_text(scene, i, product_name(request)),
                "items": circuit.legend_rows(scene, scenes)
                if circuit.kind(i) == "legend-list" and request["orientation"] == "landscape"
                else [],
                "source_ids": scene["source_ids"],
            }
            for i, scene in enumerate(scenes)
        ],
        "capture_dimensions": [
            {
                k: next(s for s in probe(clip)["streams"] if s["codec_type"] == "video")[k]
                for k in ("width", "height")
            }
            for clip in clips
        ],
        "captions": "Approximate word highlighting (proportional timings)"
        if request["captions"]
        else "Disabled",
        "voices": voice_receipts,
    }
    (folder / "quality.json").write_text(json.dumps(qa, indent=2), encoding="utf-8")
    return qa
