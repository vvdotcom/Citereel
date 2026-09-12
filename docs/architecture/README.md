# Citereel architecture diagrams

Four architecture views for the Agents for Humans hackathon. Citereel is the public product name; deployment resources and Python packages retain their original Launchpad names.

## Files

| Diagram | PNG for upload | Editable vector |
| --- | --- | --- |
| AWS full stack and hosting | [01-aws-full-stack.png](01-aws-full-stack.png) | [SVG](01-aws-full-stack.svg) |
| Backend production workflow | [02-backend-production-workflow.png](02-backend-production-workflow.png) | [SVG](02-backend-production-workflow.svg) |
| Strands agent reasoning loop | [03-strands-agent-loop.png](03-strands-agent-loop.png) | [SVG](03-strands-agent-loop.svg) |
| Agent lifecycle and policy hooks | [04-agent-policy-hooks.png](04-agent-policy-hooks.png) | [SVG](04-agent-policy-hooks.svg) |

Use diagram 01 as the primary architecture upload. Diagrams 02-04 explain the production workflow, the agent implementation, and its controls. PNGs are exported at twice the SVG dimensions (4400-5200 pixels wide). SVGs contain editable text/shapes and embedded AWS icons, with no remote image dependencies.

## Grounding and scope

- Hosting reflects the deployed `launchpad-serverless` and `launchpad-agentcore` CloudFormation resource inventories checked on 12 September 2026, plus the infrastructure definitions and API implementation. The saved inventory is in [source/deployment-check.json](source/deployment-check.json).
- CloudFront serves the static Next.js export from S3 and forwards `/v1/*` to an API Gateway HTTP API backed by Lambda. Authentication belongs to the application; this deployment does not use Cognito.
- DynamoDB stores jobs, sessions, approvals, attempts and receipts. Its access is shared by the API, dispatcher, worker and agent; not every individual read/write relationship or IAM grant is drawn.
- SQS and the dispatcher launch ECS tasks on Fargate. The worker invokes the single Strands planner through IAM-authenticated AgentCore calls, uses Polly for speech and Playwright/FFmpeg for production, and persists private artifacts in S3.
- ECR supplies versioned container images. CloudWatch provides service logs and an operations dashboard. The diagrams do not claim that full AgentCore transaction tracing is working.
- The production workflow shows the default review-enabled path. The code permits creator-authorized automatic capture when no claim needs review. A worker exits during an approval pause; approval enqueues a new attempt that resumes the existing plan.
- Export playback/download is available after QA. The separate export-approval action records the creator's decision; it does not upload to an external publishing platform.
- Source-monitoring code and a scheduled monitor definition exist locally, but the monitor was absent from the checked live stack inventory. Scheduled monitoring is therefore omitted from the deployed hosting view.
- The hooks view uses the callbacks actually registered by `ProductionPolicy`, not the generic invocation-hook names in the reference image. It shows the tool-calling path through the agent loop.

## Implementation sources

- `infra/template.yaml`, `infra/agentcore.yaml`
- `infra/dispatcher.py`, `infra/recovery.py`
- `services/api/src/launchpad_api/main.py`
- `services/worker/src/launchpad_worker/runner.py`
- `services/agent/src/launchpad_agent/concierge.py`
- `services/agent/src/launchpad_agent/policies.py`
- `services/agent/src/launchpad_agent/runtime.py`, `remote.py`
- `docs/architecture.md`, `docs/agentcore-operations.md`

The supplied `HackathonRules.txt` requires an architecture diagram, a README and a public source repository; it also requires the described functionality to match the working project. These diagrams are architecture deliverables only, not a submitted Devpost entry or a certification of eligibility.

The supplied `guidance-arch.png` informed the AWS icon layout. `archi2.png` and `archi3.png` informed the pastel flowchart boxes, loop boundary and policy branches. Their unrelated services and generic callback names were not imported into the project architecture.

## AWS icon source

Official [AWS Architecture Icons](https://aws.amazon.com/architecture/icons/), July 31, 2026 release. Downloaded from the [official icon package](https://d1.awsstatic.com/onedam/marketing-channels/website/public/shared/architecture-icon-release/Icon-package_07312026.5846e92413caa21490223536cc97f1269e44fa92.zip).

AWS permits use of these assets in architecture diagrams and related materials. AWS service icons remain AWS assets. Selected original SVGs are included in `source/aws-icons/`; they are embedded in diagram 01.

## Rebuild

From the project root:

```powershell
.venv/Scripts/python.exe docs/architecture/source/build_diagrams.py
.venv/Scripts/python.exe docs/architecture/source/render_diagrams.py
```

The SVG builder uses the Python standard library. PNG rendering uses the project's Playwright installation and Chromium. No AWS deployment or API mutation is performed by either build script.
