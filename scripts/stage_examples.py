"""Stage only owned examples with verified Bedrock/Strands and Polly receipts."""

import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for area in ("api", "agent", "worker"):
    sys.path.insert(0, str(ROOT / "services" / area / "src"))
from launchpad_api.store import store

output = ROOT / "public" / "examples"
output.mkdir(parents=True, exist_ok=True)
manifest = {}
jobs = store.list("local-creator")
for format in ("presentation", "product", "spotlight", "short"):

    def eligible(a, selected_format=format):
        return (
            (
                (a["qa"]["height"] > a["qa"]["width"])
                if selected_format == "short"
                else (a["qa"]["width"] > a["qa"]["height"])
            )
            and bool(a["qa"].get("voices"))
            and all(voice["provider"] == "Amazon Polly" for voice in a["qa"]["voices"])
        )

    candidates = (
        sorted(jobs, key=lambda j: j.get("planner") == "bedrock", reverse=True)
        if format == "presentation"
        else jobs
    )
    job = next(
        (
            j
            for j in candidates
            if j["request"]["format"] == format
            and j["request"]["website_url"] == "fixture://northstar"
            and j.get("planner") == "bedrock"
            and (j.get("model_usage") or {}).get("totalTokens", 0) > 0
            and any(t["component"] == "strands" for t in j.get("trace", []))
            and any(eligible(a) for a in j["artifacts"])
        ),
        None,
    )
    if not job:
        raise SystemExit("Generate the " + format + " Bedrock + Strands + Polly example first.")
    artifact = next(a for a in reversed(job["artifacts"]) if eligible(a))
    folder = store.root / artifact["folder"]
    manifest[format] = {
        "job_id": job["id"],
        "planner": job["planner"],
        "model": job.get("model"),
        "orchestrator": "Strands Agents",
        "model_usage": job["model_usage"],
        "qa": artifact["qa"],
    }
    if job["planner"] == "bedrock":
        proof = {
            "job_id": job["id"],
            "planner": job["planner"],
            "model": job.get("model"),
            "model_usage": job.get("model_usage"),
            "tool_receipts": job["tool_receipts"],
            "capture_events": job.get("capture_events"),
            "qa": artifact["qa"],
        }
        verification = ROOT / "artifacts" / "verification"
        verification.mkdir(parents=True, exist_ok=True)
        (verification / f"bedrock-e2e-{format}.json").write_text(
            json.dumps(proof, indent=2), encoding="utf-8"
        )
# Resolve every eligible sample before replacing any public file; retain a backup.
backup = ROOT / "artifacts" / "verification" / f"previous-examples-{time.time_ns()}"
shutil.copytree(output, backup)
for format, entry in manifest.items():
    job = store.get(entry["job_id"])
    artifact = next(a for a in job["artifacts"] if a["qa"]["sha256"] == entry["qa"]["sha256"])
    folder = store.root / artifact["folder"]
    for source, target in [("export.mp4", format + ".mp4"), ("poster.png", format + ".png")]:
        shutil.copyfile(folder / source, output / target)
(output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print("Staged four Bedrock + Strands + Polly exports. Previous files:", backup)
