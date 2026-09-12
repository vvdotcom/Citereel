"""Re-record owned homepage examples at native template size; reuse original narration.

No Bedrock/Polly calls. Existing job exports remain immutable. Prior public samples
are backed up in the new run folder before replacement.
"""

import argparse
import copy
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for area in ("api", "agent", "worker"):
    sys.path.insert(0, str(ROOT / "services" / area / "src"))
from launchpad_api.store import store
from launchpad_worker.capture import capture
from launchpad_worker.circuit import KINDS
from launchpad_worker.render import background, render, run

public = ROOT / "public" / "examples"
manifest = json.loads((public / "manifest.json").read_text(encoding="utf-8"))
run_folder = ROOT / "artifacts" / "refreshed-examples" / str(time.time_ns())
run_folder.mkdir(parents=True)
updated = {}
parser = argparse.ArgumentParser()
parser.add_argument("--formats", nargs="+", choices=list(manifest), default=list(manifest))
parser.add_argument(
    "--variation-showcase",
    action="store_true",
    help="Create a separate five-reference preview using existing reviewed scenes and audio.",
)
args = parser.parse_args()
for kind, entry in manifest.items():
    if args.variation_showcase and kind != "presentation":
        continue
    if kind not in args.formats:
        continue
    job = copy.deepcopy(store.get(entry["job_id"]))
    assert job["request"]["website_url"] == "fixture://northstar", (
        "Only owned examples may be published"
    )
    # On subsequent runs the manifest retains the original export hash.
    original_hash = entry.get("source_sha256", entry["qa"]["sha256"])
    artifact = next(a for a in job["artifacts"] if a["qa"]["sha256"] == original_hash)
    original = store.root / artifact["folder"]
    job["request"] = copy.deepcopy(artifact.get("request", job["request"]))
    job["plan"] = copy.deepcopy(artifact.get("plan", job["plan"]))
    job["evidence"] = copy.deepcopy(artifact.get("evidence", job["evidence"]))
    job["request"]["brand"] = {"name": "Northstar", "primary_color": "#ff9900"}
    folder = run_folder / kind
    folder.mkdir()
    narration = []
    for index, receipt in enumerate(artifact["qa"]["voices"]):
        voice = next(
            p for p in original.glob(f"voice-{index + 1}.*") if p.suffix in (".mp3", ".wav")
        )
        narration.append((voice, {**receipt, "reused_existing_audio": True}))
    assert len(narration) == len(job["plan"]["scenes"])
    if args.variation_showcase:
        original_scenes = job["plan"]["scenes"]
        original_audio = narration
        job["plan"]["scenes"] = [
            copy.deepcopy(original_scenes[i % len(original_scenes)]) for i in range(len(KINDS))
        ]
        narration = [original_audio[i % len(original_audio)] for i in range(len(KINDS))]
        job["request"]["duration_seconds"] = 30
    for index, scene in enumerate(job["plan"]["scenes"]):
        background(
            scene,
            job["request"],
            index,
            len(job["plan"]["scenes"]),
            folder / f"preflight-{index}.png",
            job["plan"]["scenes"],
        )
    print("Recording", kind, flush=True)
    clips, events = capture(job, folder)
    qa = render(
        job,
        folder,
        clips,
        cached_narration=narration,
        on_stage=lambda state, detail, label=kind: print(state, label, flush=True),
    )
    (folder / "capture-events.json").write_text(json.dumps(events, indent=2))
    if kind in ("presentation", "spotlight"):
        # Show the list layout in the gallery poster, not just the opening scene.
        poster_time = job["request"]["duration_seconds"] / len(job["plan"]["scenes"]) + 1
        run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-ss",
                str(poster_time),
                "-i",
                str(folder / "export.mp4"),
                "-frames:v",
                "1",
                str(folder / "poster.png"),
            ]
        )
    updated[kind] = {
        **entry,
        "source_sha256": original_hash,
        "qa": qa,
        "refresh": "Native-size re-recording, original script and narration",
    }
    print(kind, qa["width"], qa["height"], qa["bytes"], flush=True)

# Publish only after every example passes renderer media QA.
backup = run_folder / "previous-public"
shutil.copytree(public, backup)
for kind in updated:
    target = "variations" if args.variation_showcase else kind
    shutil.copyfile(run_folder / kind / "export.mp4", public / f"{target}.mp4")
    shutil.copyfile(run_folder / kind / "poster.png", public / f"{target}.png")
if args.variation_showcase:
    (public / "variations.json").write_text(
        json.dumps(
            {
                "description": "Five user-reference templates, reusing reviewed Northstar scenes and existing narration.",
                **updated["presentation"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
else:
    manifest.update(updated)
    (public / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if "presentation" in updated and len(updated["presentation"]["qa"]["scene_layouts"]) >= len(
        KINDS
    ):
        for extension in ("mp4", "png"):
            shutil.copyfile(
                public / f"presentation.{extension}", public / f"variations.{extension}"
            )
        (public / "variations.json").write_text(
            json.dumps(
                {
                    "description": "Five user-reference templates with real product footage in every scene.",
                    **updated["presentation"],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
print("Updated", len(updated), "homepage examples. Previous files:", backup, flush=True)
