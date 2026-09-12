import pytest
from launchpad_worker import editorial
from launchpad_worker.render import font
from launchpad_worker.render import legacy_background as background
from launchpad_worker.render import legacy_layout as layout
from PIL import Image, ImageDraw


def test_layouts_follow_reference_list_and_activity_arrangements():
    request = {"format": "presentation", "orientation": "landscape"}
    assert [editorial.kind(request, i) for i in range(5)] == [
        "hero",
        "workflow",
        "activity",
        "highlights",
        "wide",
    ]
    assert layout(request, 1)[1] == (930, 218, 1502, 1022)
    assert layout(request, 2)[1] == (128, 218, 1400, 1022)
    assert layout(request, 3)[1] == (876, 218, 1556, 1022)


def test_list_items_preserve_approved_words_and_do_not_invent_fillers():
    scene = {"narration": "Open the library. Review the source. Save a finding."}
    assert editorial.items(scene) == ["Open the library.", "Review the source.", "Save a finding."]
    assert editorial.items({"narration": "One reviewed statement."}) == ["One reviewed statement."]
    with pytest.raises(ValueError, match="reviewed narration"):
        editorial.items({"narration": "   "})


def test_many_sentences_are_merged_without_dropping_content():
    narration = "First sentence. Second sentence. Third sentence. Fourth sentence. Fifth sentence."
    result = editorial.items({"narration": narration})
    assert len(result) == 4
    assert " ".join(result) == narration


def test_highlights_reuse_reviewed_storyboard_copy():
    scenes = [
        {"on_screen_copy": text}
        for text in ("Evidence library", "Decision review", "Source links", "Source links")
    ]
    assert editorial.display_items({}, "highlights", scenes) == [
        "Evidence library",
        "Decision review",
        "Source links",
    ]


def test_long_identifiers_wrap_inside_the_declared_region():
    draw = ImageDraw.Draw(Image.new("RGB", (800, 600)))
    text = "https://example.com/" + "identifier" * 20
    lines = editorial.text_lines(draw, text, font(32), 200)
    assert "".join(lines) == text
    assert all(draw.textlength(line, font=font(32)) <= 200 for line in lines)


@pytest.mark.parametrize("index", [1, 2, 3])
def test_list_templates_render_real_text_in_safe_regions(tmp_path, index):
    request = {
        "format": "presentation",
        "orientation": "landscape",
        "title": "Amazon Bedrock overview",
        "brand": {"name": "Amazon Bedrock"},
    }
    scene = {
        "title": "Review the available foundation models",
        "on_screen_copy": "Use the official documentation.",
        "narration": "Open the model documentation. Compare the available models. Review the source.",
        "source_ids": ["source-1"],
    }
    destination = tmp_path / f"slide-{index}.png"
    background(scene, request, index, 5, destination)
    with Image.open(destination) as image:
        assert image.size == (2560, 1440)
        # The light bullet panel is intentionally distinct from the dark rails.
        assert image.getpixel((140, 300)) == (
            (255, 241, 214) if index == 3 else ((17, 27, 38) if index == 1 else (35, 47, 62))
        )
