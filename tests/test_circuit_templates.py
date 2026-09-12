import pytest
from launchpad_worker import circuit
from launchpad_worker.render import background, layout
from PIL import Image


def test_five_references_all_have_native_demo_video_windows():
    assert len(circuit.KINDS) == 5
    for orientation in ("landscape", "portrait"):
        request = {"orientation": orientation, "format": "presentation"}
        for index in range(8):
            (w, h), (x, y, bw, bh) = layout(request, index)
            assert bw > 900 and bh > 600
            assert bw % 2 == bh % 2 == 0
            assert x > 0 and y > 0 and x + bw < w and y + bh < h


def test_footage_first_pack_is_materially_larger_and_clear_of_captions():
    previous = [(730, 460), (680, 440), (790, 620), (810, 460), (700, 400)]
    for index, (old_w, old_h) in enumerate(previous):
        _, (x, y, w, h) = circuit.layout({"orientation": "landscape"}, index)
        assert w * h >= old_w * old_h * 1.6**2 * 1.4
        assert w * h / (2560 * 1440) >= 0.4
        assert y + h < 780 * 1.6  # Subtitles remain outside the demo window.
    _, (_, y, w, h) = circuit.layout({"orientation": "portrait"})
    assert w * h >= 936 * 770 * 1.4
    assert y + h < 1538


def test_capture_content_is_statically_reflowed_before_recording():
    assert circuit.content_scale({"orientation": "landscape"}) == 1.4
    assert circuit.content_scale({"orientation": "portrait"}) == 1.15


def test_template_paper_contrasts_with_white_websites():
    assert circuit.PAPER == "#dfe6ec"


def test_reference_font_is_a_bold_monospace_face():
    face = circuit.heading_font(60)
    assert face.getname()[0] == "Roboto Mono"
    # Variable-font grid fitting can differ by one device pixel per glyph.
    assert abs(face.getlength("III") - face.getlength("WWW")) <= 3


def test_reference_placeholders_are_not_generated_content():
    scene = {"title": "Evidence library", "narration": "Inspect a source. Review a finding."}
    assert circuit.header_text(scene, 0, "Northstar") == "Northstar"
    assert circuit.header_text(scene, 1, "Northstar") == "Evidence library"
    assert circuit.entries(scene) == ["Inspect a source.", "Review a finding."]


def test_legend_uses_three_reviewed_storyboard_entries_with_source_ids():
    scenes = [
        {"title": f"Feature {i}", "on_screen_copy": f"Reviewed copy {i}", "source_ids": [f"s{i}"]}
        for i in range(5)
    ]
    rows = circuit.legend_rows(scenes[3], scenes)
    assert len(rows) == 3
    assert rows[0] == {"title": "Feature 1", "copy": "Reviewed copy 1", "source_ids": ["s1"]}
    assert rows[2]["copy"] == "Reviewed copy 3"


@pytest.mark.parametrize("orientation", ["landscape", "portrait"])
@pytest.mark.parametrize("index", range(5))
def test_each_reference_renders_amazon_frame_and_keeps_aperture_clear(tmp_path, orientation, index):
    request = {
        "format": "presentation",
        "orientation": orientation,
        "brand": {"name": "Northstar"},
        "captions": True,
        "title": "Product overview",
    }
    scene = {
        "title": "Evidence library",
        "on_screen_copy": "Keep sources beside your research.",
        "narration": "Open the source. Review the finding. Keep the context.",
        "source_ids": ["s1"],
    }
    output = tmp_path / f"{orientation}-{index}.png"
    background(scene, request, index, 5, output)
    size, _ = layout(request, index)
    with Image.open(output) as image:
        assert image.size == size
        assert image.getpixel((0, 0)) == (35, 47, 62)
        # The portrait chapter's enlarged shell covers its side-rail orange strip;
        # orange highlighted captions are composited later, outside this background.
        if not (orientation == "portrait" and index == 1):
            assert (255, 153, 0) in image.get_flattened_data()
        _, (x, y, w, h) = layout(request, index)
        scale = 0.75 if orientation == "portrait" else 1.6
        # The same outer shell, navy inner bezel and hardware button on every slide.
        assert image.getpixel((x + w // 2, round(y - 20 * scale))) == (224, 228, 232)
        assert image.getpixel((x + w // 2, round(y - 7 * scale))) == (35, 47, 62)
        assert image.getpixel((round(x + w + 20 * scale), y + h // 2)) == (160, 171, 182)
