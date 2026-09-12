# Running and deploying

For the current versioned AWS release workflow, AgentCore runtime, recovery controls
and live verification, see [AgentCore operations](agentcore-operations.md).

## Windows local

From the Citereel repository root, follow the [README setup and configuration instructions](../README.md). Run `npm ci`, `npm run setup`, configure `.env`, then `npm run dev`. The web app is at `http://127.0.0.1:3011`, with the API at 8011 and a separate queue worker. `npm run build` followed by `npm start` runs the production web build with the same API and worker.

The launcher generates a per-run internal API secret shared only by its children. Start all three services with the launcher so the proxy and backend agree. The private `.env` is loaded by the backend and is excluded from the repository and Docker build context.

If `LAUNCHPAD_ALLOWED_ORIGINS` is nonempty, only those public origins are accepted in addition to the owned fixture. Blank permits public sites individually authorized by the creator; each job remains confined to its authorized origin. Existing scaffold configurations may contain a demo-only origin—replace it with your authorized site before submitting that site.

## Bedrock

Set `AWS_BEARER_TOKEN_BEDROCK` and `BEDROCK_MODEL_ID` in `.env`; `BEDROCK_API_KEY` is also accepted as an alias. Set the correct `AWS_REGION`. Alternatively use an AWS profile or a workload role. A Bedrock API key works for Bedrock; it does not grant Polly, S3, or deployment permissions.

Run `.venv\Scripts\python scripts/bedrock_check.py --invoke` for one small live model call. Then run `.venv\Scripts\python scripts/verify_pipeline.py --bedrock` to test the actual Bedrock/Strands path on the owned fixture. Live calls consume model quota. The normal tests use stubbed responses and do not call AWS.

For Polly, set `LAUNCHPAD_VOICE=polly`, configure signed AWS credentials or a role with `polly:SynthesizeSpeech`, and select `POLLY_VOICE_ID`/`POLLY_ENGINE`. Windows development can use `LAUNCHPAD_VOICE=windows`; the receipt explicitly identifies the voice provider.

Set `LAUNCHPAD_DAILY_JOB_LIMIT=20` in the deployment environment for cloud testing. Launchpad enforces that per signed-in user and UTC day before accepting a queue item; the maximum accepted video duration is three minutes. Change this environment value and restart the service to adjust it later; use infrastructure concurrency limits as a separate protection.

## Container

`docker compose up --build` builds and starts the app on port 3011 with a persistent data volume. Linux uses Polly; configure a workload role or temporary AWS credentials. Sign up/sign in are available; local workspace bypass is disabled. Put the service behind TLS and set `LAUNCHPAD_SECURE_COOKIES=true` for HTTPS deployments.

Before an internet-facing launch, add edge request/login rate limiting and a restrictive egress policy for the browser worker. The built-in accounts do not include email verification, password reset or MFA. Do not treat the local capture controls as a substitute for network isolation of untrusted pages.

Local development uses a single-host SQLite queue and artifact directory. Do not horizontally scale that local mode or place its SQLite WAL file on NFS/EFS. The deployed serverless path uses DynamoDB job state, SQS dispatch, Fargate render workers, private S3 artifacts, a public HTTPS API, and Bedrock AgentCore for Strands planning and revisions. The public cloud verification includes AgentCore execution, recovery, footage reuse, policy enforcement, and output-hash evidence: https://dqhy3yyc3g60j.cloudfront.net/verification/.

## Data

`.launchpad-data/launchpad.sqlite3` contains local sessions, users and jobs. `.launchpad-data/jobs/<id>/attempt-<n>` retains recordings, narration, exports and hashes. Back up the entire data directory. No automatic retention deletion is enabled. Public demo assets are staged only from the owned fixture, with a manifest; user website captures are never automatically published.

## Current production limits

- Requested durations of 30, 45, 60, 90, 120, or 180 seconds; 3–12 scenes; 2560×1440 landscape or 1080×1920 portrait masters.
- A maximum of three same-origin source pages and 30 MB of browser resource fetches.
- Inspected links, safe scrolling, and pointer feedback. Arbitrary form workflows and sign-in are unsupported; the current renderer does not apply animated camera zoom.
- Scene clips can loop to fit the narration; caption highlights use proportional timings, not forced alignment.
- Download/review delivery. External publication integrations, including YouTube OAuth/upload, are not included.
