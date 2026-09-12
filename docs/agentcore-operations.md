# AgentCore rollout and operational verification

Launchpad retains its static Next.js UI, Lambda API, DynamoDB job state, SQS
dispatch, Fargate capture/render worker, Amazon Polly and private S3 exports.
Setting `AgentRuntimeArn` on `launchpad-serverless` routes all live storyboard
planning and AI rewrites through the Strands agent in `launchpad-agentcore`.
The worker inspects sources, calls the agent, persists an approval pause, and
records/renders only after the existing approval policy allows it.

The included deterministic fixture planner is an explicit local test option;
it is never a fallback when AgentCore or Bedrock fails.

## Release procedure

Run from the Launchpad repository with an authorized AWS profile:

```powershell
.venv/Scripts/python.exe scripts/cloud_release.py build
.venv/Scripts/python.exe scripts/cloud_release.py status
.venv/Scripts/python.exe scripts/cloud_release.py deploy
.venv/Scripts/python.exe scripts/cloud_release.py build --agent
.venv/Scripts/python.exe scripts/cloud_release.py status --agent
.venv/Scripts/python.exe scripts/cloud_release.py deploy --agent
.venv/Scripts/python.exe scripts/cloud_release.py deploy --enable-agent
```

Deploy only after the corresponding build reports `SUCCEEDED`. Each upload
contains an explicit source allowlist and excludes environment files, virtual
environments, recordings and credentials. Images use unique release tags.
`artifacts/cloud-releases` records build IDs and image URIs for rollback.

The frontend uses `LAUNCHPAD_STATIC_EXPORT=true` and `NEXT_PUBLIC_API_BASE=/v1`.
Upload the `out` directory to the stack's WebBucketName and invalidate its
CloudFront distribution. Static route rewriting serves `/studio/index.html`
for both `/studio` and `/studio/`.

## Policies and limits

- Strands hooks enforce prerequisite tool order and at most ten tool calls.
- The SDK invocation limits planning to eight turns, 45,000 total tokens and
  10,000 output tokens. Each model response has its own output limit.
- Storyboards must reference inspected pages/sources, fit the speaking budget,
  and exclude numerical claims absent from their cited evidence. Attribution
  does not establish semantic truth; claims still need source review.
- API decisions verify ownership, version and allowed state. A revision resets
  approval when it changes the script. AgentCore responses are fenced to the
  current attempt/session, preventing cancelled or old runs from saving changes.
- DailyJobLimit defaults to 20 new jobs per user per UTC day. WorkerConcurrency
  defaults to two, enforced with conditional DynamoDB worker slots. Job retries
  are limited to three. Video duration is capped at 180 seconds.
- Fargate tasks exit after a 30-minute execution ceiling. AgentCore sessions
  have a 60-second idle limit, a 15-minute maximum lifetime, and an explicit
  stop request after planning. Rendering does not hold AgentCore sessions open.

## Recovery and footage preservation

Every completed browser clip is checkpointed into S3 with a SHA-256 digest and
its original interaction receipts. A fresh task retrieves matching clips and
verifies their digest. Missing expired clips are recaptured. A corrupt checkpoint
blocks the production rather than silently replacing evidence.

EventBridge sends stopped-task events to the recovery Lambda. If the matching
attempt is still active, the job becomes blocked with a retry explanation.
Events from old attempts cannot interrupt a newer attempt. The recovery handler
also frees the task's worker slot and handles exhausted SQS delivery attempts.
Prior completed exports remain downloadable after a failed revision.

## Background monitoring

Deployment status: this scheduler exists in the infrastructure source but was absent from the deployed resource inventory checked September 12, 2026. The paragraph below describes its implementation when deployed, not a verified live capability. Manual source-change checks are available independently.

An owner can opt a completed, source-backed production into a 6-, 12-, or 24-hour source check with `PUT /v1/jobs/{id}/monitor`. EventBridge invokes the monitor Lambda every six hours; it queues only due checks and the worker compares the same bounded, previously inspected pages. A scheduled check never rewrites a storyboard, records footage, renders, or publishes. Any detected change moves the job to `awaiting_changes_approval`, where the owner reviews the affected scenes before authorizing a revision.

## Evidence and observability

Each job exposes policy receipts in its Trace tab and in the authenticated
`/v1/jobs/{id}/receipt` download, alongside sources, claims, model usage,
approvals, artifacts, capture provenance and output hashes.

API, dispatcher, worker and AgentCore logs carry `job_id`. The operations
dashboard shows API errors, queue depth, and worker decisions/outcomes. AWS
console links require the operator's AWS permissions; user-facing receipts do
not. AgentCore uses AWS OpenTelemetry instrumentation and Strands trace
attributes. CloudWatch GenAI's complete transaction-search experience requires
the account's trace destination to be configured; do not claim this is enabled
solely because the agent runtime exists.

The September 9 verification observed HTTP 400 from the ADOT span exporter.
`GetTraceSegmentDestination` still reports `XRay`. Full AgentCore tracing requires
CloudWatch Transaction Search and a `CloudWatchLogs` trace destination, even when
using the newer per-agent span log group. This is an account-wide change and was
not made as part of this application deployment. Obtain the account owner's
approval before enabling it; then verify actual spans, not just runtime metrics.
See [AWS observability configuration](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-configure.html).

## Verification

`scripts/cloud_verify.py` creates a clearly identified synthetic test account
and exercises the public HTTPS API. It keeps its session cookie only in the
operator's temporary directory and never logs authentication material. Saved
results go to `artifacts/cloud-verification`.

```powershell
.venv/Scripts/python.exe scripts/cloud_verify.py start
.venv/Scripts/python.exe scripts/cloud_verify.py status
# Review the saved storyboard and sources before approving the test production.
.venv/Scripts/python.exe scripts/cloud_verify.py approve
.venv/Scripts/python.exe scripts/cloud_verify.py status
.venv/Scripts/python.exe scripts/cloud_verify.py receipt
```

For recovery testing, stop only the identified verification task after it has
saved at least one recording checkpoint. Confirm the app reports a blocked job,
retry it through the app API, then verify the output, reused clip hashes and
original capture receipts. This is a controlled engineering test, not evidence
of real customer demand or time savings.

## Recorded cloud results — September 9, 2026

Public proof: https://dqhy3yyc3g60j.cloudfront.net/verification/

Production `lp_7296bbbf86634eca` used an owned, fictional Northstar site with real
Bedrock, Strands, Polly and browser capture. No fixture planner was used.

- Attempt 2 completed the original cloud export.
- Attempt 3 rewrote the storyboard in AgentCore session
  `9b71bf83-8618-4e6a-9289-f7995fec1044`. A missing source citation was rejected;
  the agent corrected it, and the workflow paused for human approval.
- Attempt 4 was deliberately stopped during rendering. The real ECS EventBridge
  event marked it blocked. The storyboard was unchanged and the previous MP4
  remained downloadable with its original SHA-256.
- One user-requested retry (attempt 5) restored all four clips from S3, recorded
  zero new clips, and produced a 30.043-second H.264/AAC export at 2560 × 1440.
- The downloaded export's SHA-256 was independently verified:
  `3b59da6c4e975d3793203bf7002372d1e0e973b60117604cf687b8ab763b4137`.
- The public receipt includes 84 correlated service log events, source evidence,
  scripts, policy checks, hashes and the interruption test. No session cookie or
  customer identity is published.

Reproduction utilities:

```powershell
# Requires the owned test job with an existing export and an approved revision.
.venv/Scripts/python.exe scripts/cloud_recovery_probe.py
.venv/Scripts/python.exe scripts/cloud_verify.py retry
.venv/Scripts/python.exe scripts/cloud_verify.py watch
.venv/Scripts/python.exe scripts/publish_cloud_proof.py
.venv/Scripts/python.exe scripts/cloud_screenshots.py
```

The publisher asserts successful AgentCore execution, recovery, footage reuse,
correlated logs and the downloaded media hash before creating public proof files.
It does not upload them. Rebuild and deploy the static frontend separately.

Production `lp_08158116daa64d6c` also completed against the public AWS Bedrock
documentation (not a fixture). Its first attempt timed out connecting; after
the bounded IPv4/address-fallback fix, attempt 2 planned successfully in
AgentCore and paused for review. Attempt 3 captured six scenes, narrated with
Polly and rendered a 30.043-second 2560 × 1440 MP4. Export SHA-256:
`7a96100c5d274b981a17faf7cdcd6f8c774ba4b40a20c41072b56551cfd22e83`.
The public verification page includes both example videos.

Verification: 95 backend tests passed; the static production build passed.
Desktop and 390px mobile checks passed without horizontal document overflow;
the public video loaded and sought successfully in Chromium.
The quota remains **per signed-in user**, not an account-wide AWS spending cap. New
registrations, revisions, storage, logs and build usage can still incur charges.
For an unrestricted public launch, add registration/invitation controls and a
global billable-operation budget; do not describe the current quota as a hard
dollar cap.
