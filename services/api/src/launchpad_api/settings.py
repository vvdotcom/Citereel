import os
from functools import lru_cache
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[4]
load_dotenv(ROOT / ".env", override=False)
if not os.getenv("AWS_BEARER_TOKEN_BEDROCK") and os.getenv("BEDROCK_API_KEY"):
    os.environ["AWS_BEARER_TOKEN_BEDROCK"] = os.environ["BEDROCK_API_KEY"]
_data_path = Path(os.getenv("LAUNCHPAD_DATA_DIR") or ".launchpad-data")
DATA = (_data_path if _data_path.is_absolute() else ROOT / _data_path).resolve()
DATA.mkdir(parents=True, exist_ok=True)
REGION = os.getenv("AWS_REGION") or "us-east-1"
MODEL = os.getenv("BEDROCK_MODEL_ID") or "amazon.nova-lite-v1:0"
VOICE = os.getenv("LAUNCHPAD_VOICE") or "polly"
API_SECRET = os.getenv("LAUNCHPAD_API_SECRET", "")
FIXTURE = "fixture://northstar"
MAX_VIDEO_DURATION_SECONDS = 180


def positive_integer(name, default):
    try:
        value = int(os.getenv(name, str(default)))
        return value if value > 0 else default
    except ValueError:
        return default


# Enforced during the database transaction before any queue/model work begins.
DAILY_JOB_LIMIT = positive_integer("LAUNCHPAD_DAILY_JOB_LIMIT", 20)


@lru_cache(maxsize=1)
def bedrock_credentials_available():
    if os.getenv("AWS_BEARER_TOKEN_BEDROCK"):
        return True
    try:
        # Use the SDK chain, including default profiles, ECS, EKS and EC2 roles.
        return boto3.Session(region_name=REGION).get_credentials() is not None
    except BotoCoreError:
        return False


def configuration():
    return {
        "model": MODEL,
        "region": REGION,
        "bedrock_configured": bedrock_credentials_available(),
        "voice": VOICE,
        "fixture": FIXTURE,
        "daily_job_limit": DAILY_JOB_LIMIT,
        "max_video_duration_seconds": MAX_VIDEO_DURATION_SECONDS,
        "allowed_origins": [
            x.strip() for x in os.getenv("LAUNCHPAD_ALLOWED_ORIGINS", "").split(",") if x.strip()
        ],
    }
