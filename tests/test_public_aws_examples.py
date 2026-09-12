"""Published benchmark claims must match the actual AWS-backed media files."""

import hashlib
import json
from pathlib import Path

import pytest

PUBLIC = Path(__file__).resolve().parents[1] / "public" / "examples"


@pytest.mark.parametrize("mode", ["presentation", "product", "spotlight", "short"])
def test_public_example_has_aws_provenance_and_matching_media(mode):
    entry = json.loads((PUBLIC / "manifest.json").read_text(encoding="utf-8"))[mode]
    assert entry["planner"] == "bedrock"
    assert entry["orchestrator"] == "Strands Agents"
    assert entry["model_usage"]["totalTokens"] > 0
    qa = entry["qa"]
    assert len(qa["voices"]) == len(qa["scene_layouts"])
    assert all(voice["provider"] == "Amazon Polly" for voice in qa["voices"])
    media = (PUBLIC / f"{mode}.mp4").read_bytes()
    assert len(media) == qa["bytes"]
    assert hashlib.sha256(media).hexdigest() == qa["sha256"]
    assert (PUBLIC / f"{mode}.png").is_file()
