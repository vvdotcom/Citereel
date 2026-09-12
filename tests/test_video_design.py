from launchpad_worker.changes import recording_key
from launchpad_worker.render import captions, layout, product_name


def test_product_identity_never_defaults_to_launchpad():
    assert product_name({"brand": {"name": " Amazon Bedrock "}}) == "Amazon Bedrock"
    assert product_name({"website_url": "fixture://northstar"}) == "Northstar"
    assert product_name({"website_url": "https://www.amazon.com/"}) == "amazon.com"
    assert product_name({"title": "Relay"}) == "Relay"
    assert product_name({}) == "Product demo"


def test_hd_templates_keep_footage_inside_canvas():
    for kind in ("presentation", "product", "spotlight", "short"):
        for orientation in ("portrait", "landscape"):
            for index in range(8):
                size, (x, y, w, h) = layout({"format": kind, "orientation": orientation}, index)
                assert size == ((1080, 1920) if orientation == "portrait" else (2560, 1440))
                assert x >= 0 and y >= 0 and x + w <= size[0] and y + h <= size[1]
                assert w % 2 == h % 2 == 0


def test_word_highlighting_is_retained(tmp_path):
    path = tmp_path / "captions.ass"
    captions("Keep the product in focus", 5, path, (2560, 1440))
    text = path.read_text()
    assert "PlayResX: 2560" in text and "PlayResY: 1440" in text
    assert "{\\kf100}Keep" in text
    assert "&H000099FF" in text


def test_capture_cache_accounts_for_template_geometry():
    scene = {"page_id": "a", "scroll": "top"}
    evidence = [{"page_id": "a", "url": "fixture://northstar", "excerpt": "same text"}]
    request = {"format": "presentation", "orientation": "landscape"}
    assert recording_key(scene, evidence, request, 0) != recording_key(scene, evidence, request, 1)
    assert recording_key(scene, evidence, request, 0) == recording_key(scene, evidence, request, 5)
