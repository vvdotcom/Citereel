import os
import subprocess
from pathlib import Path

from launchpad_api.settings import REGION, ROOT, VOICE


def synthesize(text, output: Path, narration_voice="female"):
    if VOICE == "polly":
        import boto3

        voices = {
            "female": os.getenv(
                "POLLY_FEMALE_VOICE_ID", os.getenv("POLLY_VOICE_ID", "Ruth")
            ),
            "male": os.getenv("POLLY_MALE_VOICE_ID", "Matthew"),
        }
        voice_style = narration_voice if narration_voice in voices else "female"
        voice_id = voices[voice_style]
        engine = os.getenv("POLLY_ENGINE", "generative")
        response = boto3.client("polly", region_name=REGION).synthesize_speech(
            Text=text,
            VoiceId=voice_id,
            Engine=engine,
            OutputFormat="mp3",
        )
        output = output.with_suffix(".mp3")
        with response["AudioStream"] as stream:
            output.write_bytes(stream.read())
        return output, {
            "provider": "Amazon Polly",
            "voice": voice_id,
            "voice_style": voice_style,
            "engine": engine,
        }
    if VOICE == "windows" and os.name == "nt":
        textfile = output.with_suffix(".txt")
        textfile.write_text(text, encoding="utf-8")
        subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-File",
                str(ROOT / "scripts" / "speak.ps1"),
                "-TextPath",
                str(textfile),
                "-OutputPath",
                str(output),
            ],
            check=True,
            capture_output=True,
            timeout=120,
        )
        return output, {"provider": "Windows Speech", "voice": "System default (local voice)"}
    raise ValueError("Configure LAUNCHPAD_VOICE=polly with AWS credentials, or windows on Windows.")
