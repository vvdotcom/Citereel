# Long presentations and recorded interactions

Presentation mode offers 2-minute (120-second) and 3-minute (180-second) lengths.
The API validates both. Switching from a 3-minute presentation to another format
resets the duration to 2 minutes. The Bedrock planning prompt requests 6–8 scenes
for two minutes and eight scenes for three minutes, with narration proportional
to runtime rather than repeating a short script.

Browser recording starts after the initial page is visible and before navigation.
Only visible links to previously inspected pages can be clicked. A cursor overlay
follows real mouse movement; the click highlight is shown during actual mouse-down.
If no inspected link is visible, Launchpad records direct navigation and does not
claim a click. Read-only network restrictions, robots checks, origin restrictions,
and disabled third-party website scripts remain in place.

The renderer plays recorded interactions once, holding the final frame if needed.
Dynamic zoom stays at 1x for the first three seconds, eases to 1.22x and returns
to 1x; the rounded tablet border and captions stay fixed. AWS documentation uses
a top-left camera anchor to preserve the beginnings of lines; other pages use a
centered anchor. This is not semantic tracking or automatic click-target zoom.

## Requested public-site examples

- Amazon job `lp_914ad1b8b78845d5`: blocked during inspection by the strict
  redirect policy. No storyboard or export was fabricated.
- Wikipedia job `lp_744d9845a09849ab`: requested through Launchpad's normal
  authenticated API at 180 seconds, using Bedrock mode with storyboard review.
  Wikipedia returned HTTP 403 for robots.txt from this machine. The job stopped
  before model planning or narration. No Wikipedia video was produced.

- Replacement AWS documentation job: `lp_de943f1501ea478b`. Bedrock generated
  the initial eight-scene plan; its short narration was expanded from the retrieved
  evidence and saved through Launchpad's storyboard API before approval. Recording,
  Polly narration, rendering and the camera-correction revision all ran through
  Launchpad's authenticated production workflow. Original capture receipts are
  retained when clips are reused during a rerender.
  Export version 3 passed QA at 180.043 seconds, 2560×1440, with six recorded
  navigation clicks and Amazon Polly audio. Browser playback and seeking to
  40 and 170 seconds passed. The authenticated API download and screenshots are
  saved under `artifacts/verification/lp_de943f1501ea478b/`. The footage is AWS's
  static documentation HTML, not an interactive AWS console recording.

`scripts/aws_demo.py` accepts `--website`, `--duration`, `--title`, `--brand`,
`--brief`, `--audience` and `--cta`. It submits through the running app API, never
writes a fabricated job or calls the renderer outside the production workflow.
Use `show` to inspect a job before using `approve` for a reviewed storyboard.

## Verification

Tests cover the duration contract, verification-page rejection, duration-aware
capture caching, a real inspected-link click retained in an owned-fixture recording,
and FFmpeg execution of the dynamic camera. Browser acceptance checks exercise
both duration options and the format-change reset. These checks are not evidence
of a successful live Wikipedia export.
