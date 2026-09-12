# Judge walkthrough and testing protocol

Citereel (formerly Launchpad Concierge) has a hosted AWS demo and a separate local development mode. The public demo and engineering receipts are available; real-customer validation remains to be done.

## Public AWS demonstration

Open the [hosted studio](https://dqhy3yyc3g60j.cloudfront.net/studio/) and create an account. For a repeatable first run, choose the included fictional Northstar product, a 30-second duration, and storyboard review. Hosted generation uses the deployment's AWS configuration. Public samples and the [cloud verification page](https://dqhy3yyc3g60j.cloudfront.net/verification/) require no login.

Alternatively, run the app locally using the [README setup instructions](../README.md), open http://127.0.0.1:3011, and choose Open local workspace. Local live planning and Polly narration require your AWS configuration and consume AWS quota.

For a public website test, choose **Use public Amazon Bedrock example** in Create demo, review the brief, enable storyboard review, confirm permission for read-only inspection, and start the agent.

The example uses the public Amazon Bedrock overview, model availability and quickstart documentation. It is an independent testing demo, not an Amazon endorsement. Amazon shopping/account/checkout flows are not used.

1. Follow the progress and tool trace. Planning should pause for approval.
2. Open Claims. Exact source wording is labeled **Source wording matched**, not “verified.” Other wording requires explicit reviewer acknowledgment. Unknown numerical claims and invalid source IDs are rejected.
3. Edit any claims needing correction. Saving edits invalidates approval. Approve the storyboard to record and render.
4. Play the MP4. Inspect source URLs, captured actions, actual voice provider and media QA in Receipts.
5. Request a founder or social cut. This invokes Bedrock with the prior storyboard and updated brief; it is not sentence truncation. Review the new plan before rendering. Previous exports remain available.
6. Choose **Check website for changes**. An unchanged website is a valid result: no model rewrite or capture occurs.
7. When inspected text changes, inspect the before/after text and affected scene numbers. Approve a proposed rewrite, or keep the current video. Only affected scenes may change; the server locks the others. Approve the resulting storyboard separately before rendering.

Website comparison covers normalized text in up to three previously inspected pages (maximum 6,000 characters each), not a whole-site or visual diff. Layout/image-only changes are not detected. Unchanged source/scroll recordings can be reused; narration is synthesized again for a revised export. Browser resources are cached only within an attempt. Missing/blocked pages do not justify bypassing robots rules, login or CAPTCHA.

AWS documentation capture uses its server-rendered HTML with the body visibility restored because its CSS hides the page until JavaScript runs. Website scripts remain disabled. This is recorded in capture receipts; it is not a demonstration of interactive AWS Console workflows. Visible-text and blank-image checks block unusable recordings.

## Fictional test personas

Landing-page testimonial names, AI-generated portraits, and quotes are fictional testing content. They do not represent customers or measured product outcomes.

Maya Chen, Jordan Brooks, Sam Patel, Alex Rivera and Taylor Morgan are fictional names for test scenarios. The Trials tab records:
- Actual production elapsed time, including queue/review waits.
- Revision-request counts.
- Tester observations.
- Optional tester-entered manual baseline, never an invented default.

It always marks these sessions simulated. It does not infer willingness to use the output, customer testimonials, time saved or commercial impact. Multiple entries on one production are scenario notes, not independent participants.

## Real-user study still needed

Recruit 3–5 actual founders or product marketers separately, with consent. Do not substitute the fictional names above as customer evidence.

Give each person the same task: make a 30-second product introduction from an authorized public page. First time their normal manual approach, then Launchpad (counterbalance order across participants where possible). Record active work separately from waiting time, the correction count, rejected claims, completion/failure, and whether the resulting output is usable as-is, with edits, or not usable. Ask whether they would use it again and why; preserve their exact answer with permission.

A results worksheet should contain participant code, role, date, source URL, manual active/wait seconds, Launchpad active/wait seconds, correction count, usable-output verdict and voluntary feedback. Report unsuccessful sessions and sample size. Do not generalize a small convenience sample into market-wide savings.

## Failure and recovery checks

The automated tests cover unsupported numbers, review acknowledgment, stale versions, account isolation, private/metadata URLs, a failed website check followed by retry, locked scenes, and selective recording reuse. Stubbed tests are labeled and are not represented as live Bedrock runs.

A real capture test exposed blank AWS documentation caused by its hidden body. That attempt was stopped without approving an export; its failure remains in the test job history. Retry uses the saved, reviewed storyboard after the capture correction.

## Deployment boundary

The hosted path uses CloudFront/S3, API Gateway/Lambda, DynamoDB/SQS, Fargate, Bedrock AgentCore, Bedrock, Polly, and private S3 exports. Local mode uses SQLite and a filesystem artifact directory. See [architecture diagrams](architecture/README.md), [deployment](deployment.md), and [AgentCore operations](agentcore-operations.md).

The default daily allowance is 20 accepted productions per account; rendering is asynchronous. Blocked jobs expose the failure and an explicit retry action. Previous completed exports remain available. Scheduled monitoring was absent from the September 12 deployed inventory, so use the manual website-change check for this walkthrough. Full AgentCore span export remains incomplete; correlated service logs and receipts are available.

The entrant must arrange unrestricted judge access and keep the deployment funded and available through the judging period. The quota/access follow-up is tracked in the [submission checklist](hackathon-checklist.md).
