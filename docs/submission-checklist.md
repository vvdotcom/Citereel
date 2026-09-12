# Devpost submission checklist

## Ready in this repository

- [x] Material Strands and Bedrock AgentCore implementation.
- [x] Public cloud verification: https://dqhy3yyc3g60j.cloudfront.net/verification/
- [x] MIT license and setup README.
- [x] Architecture source in [architecture.md](architecture.md), covering CloudFront, Lambda, DynamoDB, SQS, Fargate, AgentCore, Bedrock, Polly, and S3.
- [x] Judge walkthrough and safety/testing protocol in [judge-guide.md](judge-guide.md).
- [x] Opt-in EventBridge source monitoring that pauses for review before any rewrite or render.

## Required before Devpost submission

- [ ] Export the architecture diagram from `architecture.md` as a PDF, PNG, or PPTX and attach it to Devpost.
- [ ] Publish a public YouTube or Vimeo demo under five minutes. Show intake, AgentCore planning, claim review, approval, rendered output, and a monitored change pause.
- [ ] Provide the public code repository URL and confirm the MIT license is visible.
- [ ] Add the AWS Builder ID, selected Professional Agents track, and testing instructions.
- [ ] Use the live CloudFront verification URL as the optional live-demo link.
- [ ] If reporting user outcomes, use only consented real participant data; simulated personas remain explicitly labeled as simulations.

## Suggested five-minute demo structure

1. Problem: product teams repeatedly turn changing websites into accurate launch videos.
2. AgentCore: show the Strands tools, bounded evidence inspection, and claim ledger.
3. Human control: approve the storyboard before recording and any source-driven revision.
4. Cloud execution: show the public HTTPS, SQS, Fargate, Polly, S3, and receipt trail.
5. Background monitoring: enable daily checks, explain that changed content pauses for approval, and show a preserved prior export.
