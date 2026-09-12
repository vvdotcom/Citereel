from launchpad_worker import editorial
from launchpad_worker.render import layout
from PIL import Image


def test_brand_is_only_in_the_opening_template_header():
    scene = {"title": "Review the evidence"}
    for i in range(8):
        selected = editorial.KINDS[i]
        label = editorial.header_text(scene, i, "Northstar", selected)
        assert ("Northstar" in label) == (i == 0)
        if selected not in editorial.LIST_KINDS and i:
            assert label == scene["title"]


def test_all_eight_variations_have_even_native_capture_dimensions():
    request = {"format": "presentation", "orientation": "landscape"}
    assert len(set(editorial.KINDS)) == 8
    for i in range(8):
        _, (x, y, w, h) = layout(request, i)
        assert w % 2 == h % 2 == 0
        assert 0 <= x < x + w <= 2560
        assert 0 <= y < y + h <= 1240


def test_alpha_mask_rounds_actual_video_corners(tmp_path):
    path = tmp_path / "mask.png"
    editorial.rounded_mask((600, 400), path)
    with Image.open(path) as mask:
        assert mask.mode == "L"
        assert mask.getpixel((0, 0)) == 0
        assert mask.getpixel((599, 399)) == 0
        assert mask.getpixel((300, 200)) == 255
        assert mask.getpixel((300, 1)) == 255


def test_focus_layout_has_no_items():
    assert editorial.display_items({"narration": "Show the product."}, "focus") == []
