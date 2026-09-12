"""Checks configuration without printing secrets. --invoke makes one small Bedrock call."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for area in ("api", "agent", "worker"):
    sys.path.insert(0, str(ROOT / "services" / area / "src"))
from launchpad_agent.concierge import model
from launchpad_api.settings import configuration

parser = argparse.ArgumentParser()
parser.add_argument("--invoke", action="store_true")
args = parser.parse_args()
result = configuration()
result["invoked"] = False
if args.invoke:
    try:
        from strands import Agent

        agent = Agent(model=model(), callback_handler=None)
        response = agent(
            "Reply with the single word READY.",
            limits={"turns": 1, "total_tokens": 1000, "output_tokens": 20},
        )
        result.update(invoked=True, model_responded=bool(str(response).strip()))
    except Exception as exc:
        from botocore.exceptions import ClientError

        result["error"] = (
            ("AWS " + exc.response.get("Error", {}).get("Code", "Error"))
            if isinstance(exc, ClientError)
            else str(exc)
            if isinstance(exc, ValueError)
            else type(exc).__name__
        )
output = ROOT / "artifacts" / "verification"
output.mkdir(parents=True, exist_ok=True)
(output / "bedrock-readiness.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result, indent=2))
sys.exit(0 if not args.invoke or result.get("model_responded") else 1)
