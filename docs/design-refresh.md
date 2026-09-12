# Amazon / Preline design refresh

## Current video pack: supplied circuit references

The current renderer uses the five user-supplied `temp1.jpg` through `temp5.jpg`
layouts, replacing the earlier editorial pack described below. Their German
placeholder copy is not interpreted as instructions or used as generated content.
Their photos, world map and placeholder tablet screen are replaced by actual
browser footage. Every slide, including the cover and chapter divider, has a
non-empty, native-resolution demo-video opening.

1. Circuit cover: bold product heading, supporting text and live footage.
2. Chapter rails: numbered section, patterned side rails and footage.
3. Image split: large left heading/body and a large right footage panel.
4. Legend list: top heading, footage in place of the map, and right-side items.
5. Tablet demo: footage inside a device frame with the headline/body on the right.

Navy (#232f3e), orange (#ff9900), light paper and slate replace the references'
purple/blue colors. Bold Roboto Mono approximates their heading style; Inter is
retained for body copy and highlighted subtitles. The cut-corner outer frame and
circuit traces follow the latest references; video windows retain rounded alpha
clipping. The product-name template heading appears only on the opening slide.
Subsequent non-list slides use their scene titles. Source-site branding and
reviewed narration are not erased.

[Roboto Mono](https://github.com/google/fonts/tree/main/ofl/robotomono) is bundled
with its [SIL Open Font License](../assets/RobotoMono-LICENSE.txt).
The website's typography and Preline controls have not been changed by this pack.
`/examples/variations.mp4` now presents the five supplied-reference layouts.

### Footage-first sizing

Every slide now shares slide 5's rounded light-gray device shell, navy inner bezel
and slim side button. The border is drawn outside the video aperture, preserving
the enlarged footage dimensions. Portrait uses a proportionally thinner shell.

The v2 pack enlarges each landscape footage area by 43–124% relative to the
first circuit pack. Covers and chapters use compact headings above the recording;
split, legend and tablet layouts use narrower text columns. Footage now occupies
41–52% of the entire landscape canvas, with subtitles outside the recording.
Portrait footage is 43% larger with the heading and description condensed above it.
Browser content is reflowed at 140% zoom for landscape and 115% for portrait before
native-resolution recording, so controls and text grow as well as the frame.
The footage cache key includes the zoom policy and geometry. Existing approved
job exports remain unchanged; homepage examples are regenerated with original audio.

## Earlier interface and video work

The interface retains Inter and the existing navigation/production layout, with
Preline UI controls, client-owned accordions, larger readable form text, and Amazon
navy (#232f3e) and orange (#ff9900). The uncodixfy guidance informed restrained
borders, spacing and component shapes. No files in ProjectV were changed.

Preline is attributed in README.md; full notices are in assets/Preline-LICENSE.txt.
Use the documented Node 22.22.2 runtime to match Preline 5's engine requirement.

## Video templates

The local ProjectV presentation-story@2 contact sheet and README were inspected
as references: product-first footage, a thin header rule, concise editorial split
scenes, and unobstructed walkthrough scenes. Launchpad renders its own composition;
no ProjectV assets, branding or screenshots are copied.

- Landscape masters: 2560 x 1440; portrait: 1080 x 1920.
- Public examples previously served 1280 x 720 / 720 x 1280. They are re-recorded,
  not enlarged from those files.
- Browser capture uses each template's native footage dimensions. Responsive page
  layout therefore happens at the displayed aperture size, not an oversized desktop
  viewport that is subsequently shrunk. H.264 composition uses CRF 17.
- Presentation scenes use a split opener, stacked list rail, right-side item cards,
  light bullet summary and wide walkthrough. All four formats preserve
  the orange word-highlight subtitles and their existing approximate timing.

### Veyframe list arrangements

The v3 pack adds a mirrored right-hand workflow list, a bottom row of summary
cards and a footage-only focus frame: eight layouts in total. Only the first
template header uses the product name. Later non-list slides put the scene title
in that header location with no duplicate headline or repeating project footer.
Source websites and reviewed narration retain their original product references.

All footage is clipped through a supersampled 36-pixel alpha mask, after camera
motion. Panels and item cards are rounded as well. The subtitle words retain their
orange karaoke highlighting; outlined lettering replaces the square word boxes.
The separate 60-second `/examples/variations.mp4` showcases all eight layouts using
existing reviewed scenes and narration (some scenes repeat to demonstrate layouts).
Generate it with `scripts/refresh_demo_design.py --variation-showcase`.

The v2 renderer explicitly reproduces three layouts from the local ProjectV
`presentation-story@2` templates in Amazon colors:

- Workflow rail: 730-pixel left panel with stacked items, 1502 x 1022 product footage
  on the right (reference slide 04).
- Product activity: 1400 x 1022 footage on the left, numbered item cards on the right
  (reference slide 06). The cards do not claim that an action was observed.
- Workflow highlights: a light warm panel with up to three bullets and 1556 x 1022
  footage on the right (reference slide 07).

List rows preserve the reviewed narration's sentences. Summary bullets reuse the
reviewed storyboard's on-screen copy. No separate AI call invents list contents.
The export QA receipt records each scene's layout, displayed items and source IDs.
Native capture geometry changes with the layout; existing approved exports are
not overwritten. The refreshed presentation demonstrates all three at roughly
6, 12 and 18 seconds, respectively.
- The product name comes from the explicit brand field, then the source domain or
  fixture identity. There is no Launchpad fallback watermark. The intake requires
  a product name; editing a fixture URL clears the fixture's default brand.
- Recording cache keys include template geometry, preventing incompatible old
  footage from being silently reused after layout/orientation changes.

## Refreshing examples

Run ` .venv/Scripts/python scripts/refresh_demo_design.py ` from this folder.
It re-records only the owned Northstar fixture, reuses the exact original narration,
and retains the original planner provenance. It does not call Bedrock or Polly.
All four outputs must pass media QA before publication. Prior public files are
backed up under artifacts/refreshed-examples; existing job exports are untouched.
Rebuild Next after refreshing the statically imported manifest.

## Verification commands

```powershell
npm run lint
npm run typecheck
npm run build
.venv/Scripts/ruff check services tests scripts
$env:PYTHONPATH='services/api/src;services/agent/src;services/worker/src'
.venv/Scripts/python -m pytest -q
# With npm start running
.venv/Scripts/python scripts/verify_ui.py
.venv/Scripts/python scripts/verify_preline_ui.py
.venv/Scripts/python scripts/verify_review_ui.py --job lp_964a1b89ad964272
```

The Preline acceptance test covers mouse and keyboard toggling, page revisits,
evidence panels across job polling, and layouts from 320 to 1600 pixels wide.
These are automated tests, not unfamiliar-user research or customer validation.
