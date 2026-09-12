import io
import runpy
import uuid
from pathlib import Path

import boto3
import dotenv
import pytest
from launchpad_agent.contracts import GenerationRequest
from launchpad_api import settings
from launchpad_api.store import Store
from launchpad_worker import speech


@pytest.mark.parametrize("mode", ["presentation", "product", "spotlight", "short"])
def test_all_formats_default_to_bedrock(tmp_path, mode):
    request = GenerationRequest(
        website_url="fixture://northstar",
        authorization_confirmed=True,
        brief="Show the evidence library with its source links.",
        format=mode,
        idempotency_key=uuid.uuid4().hex,
    )
    assert Store(tmp_path).create(request, "test-creator")["planner_mode"] == "bedrock"


def test_default_voice_is_polly_on_every_platform(monkeypatch, tmp_path):
    monkeypatch.delenv("LAUNCHPAD_VOICE", raising=False)
    monkeypatch.setenv("LAUNCHPAD_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: None)
    assert runpy.run_path(str(Path(settings.__file__)))["VOICE"] == "polly"


def test_polly_receipt_and_audio(monkeypatch, tmp_path):
    monkeypatch.setattr(speech, "VOICE", "polly")
    monkeypatch.delenv("POLLY_ENGINE", raising=False)
    monkeypatch.delenv("POLLY_MALE_VOICE_ID", raising=False)

    class Polly:
        def synthesize_speech(self, **kwargs):
            assert kwargs["Text"] == "Source-backed product demo."
            assert kwargs["OutputFormat"] == "mp3"
            assert kwargs["VoiceId"] == "Matthew"
            assert kwargs["Engine"] == "generative"
            return {"AudioStream": io.BytesIO(b"mock-polly-audio")}

    monkeypatch.setattr(boto3, "client", lambda *args, **kwargs: Polly())
    output, receipt = speech.synthesize(
        "Source-backed product demo.", tmp_path / "voice.wav", "male"
    )
    assert receipt["provider"] == "Amazon Polly"
    assert receipt["voice"] == "Matthew" and receipt["voice_style"] == "male"
    assert receipt["engine"] == "generative"
    assert output.suffix == ".mp3" and output.read_bytes() == b"mock-polly-audio"


def test_generation_request_offers_female_and_male_narrators():
    female = GenerationRequest(
        website_url="fixture://northstar",
        authorization_confirmed=True,
        brief="Show the evidence library with its source links.",
        idempotency_key=uuid.uuid4().hex,
    )
    male = female.model_copy(update={"narration_voice": "male"})
    assert female.narration_voice == "female"
    assert male.narration_voice == "male"


def test_polly_failure_does_not_fall_back_to_windows(monkeypatch, tmp_path):
    monkeypatch.setattr(speech, "VOICE", "polly")

    def unavailable(*args, **kwargs):
        raise RuntimeError("Polly unavailable")

    monkeypatch.setattr(boto3, "client", unavailable)
    with pytest.raises(RuntimeError, match="Polly unavailable"):
        speech.synthesize("Demo narration", tmp_path / "voice.wav")
    assert not list(tmp_path.iterdir())
