"""Versioned, secret-free CodeBuild uploads. Does not remove existing releases."""
import argparse
import json
import time
import zipfile
import subprocess
from pathlib import Path
import boto3

ROOT = Path(__file__).resolve().parents[1]
REGION = "us-east-1"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["build", "status", "deploy"])
    parser.add_argument("--agent", action="store_true")
    parser.add_argument("--tag")
    parser.add_argument("--enable-agent", action="store_true")
    args = parser.parse_args()
    out = ROOT / "artifacts" / "cloud-releases"
    out.mkdir(parents=True, exist_ok=True)
    state_path = out / ("agent-build.json" if args.agent else "app-build.json")
    build = boto3.client("codebuild", region_name=REGION)
    if args.action == "deploy":
        state = json.loads(state_path.read_text())
        if build.batch_get_builds(ids=[state["build_id"]])["builds"][0]["buildStatus"] != "SUCCEEDED":
            raise SystemExit("Build must succeed before deployment.")
        account = boto3.client("sts").get_caller_identity()["Account"]
        cfn = boto3.client("cloudformation", region_name=REGION)
        existing = cfn.describe_stacks(StackName="launchpad-serverless")["Stacks"][0]
        resources = cfn.list_stack_resources(StackName="launchpad-serverless")["StackResourceSummaries"]
        table = next(r["PhysicalResourceId"] for r in resources if r["LogicalResourceId"] == "Jobs")
        if args.agent:
            template = "infra/agentcore.yaml"
            stack = "launchpad-agentcore"
            params = [f"AgentImageUri={state['images']['launchpad-agent']}", f"JobsTableName={table}"]
        else:
            template = str(out / "packaged.yaml")
            subprocess.run(["aws", "cloudformation", "package", "--template-file", "infra/template.yaml", "--s3-bucket", f"launchpad-deploy-{account}-{REGION}", "--output-template-file", template, "--region", REGION], cwd=ROOT, check=True)
            stack = "launchpad-serverless"
            params = [f"ApiImageUri={state['images']['launchpad-api']}", f"WorkerImageUri={state['images']['launchpad-worker']}"]
            if args.enable_agent:
                runtimes = boto3.client("bedrock-agentcore-control", region_name=REGION).list_agent_runtimes()["agentRuntimes"]
                runtime = next(r for r in runtimes if r["agentRuntimeName"] == "launchpad_concierge")
                params.append(f"AgentRuntimeArn={runtime['agentRuntimeArn']}")
        subprocess.run(["aws", "cloudformation", "deploy", "--template-file", template, "--stack-name", stack, "--capabilities", "CAPABILITY_IAM", "CAPABILITY_AUTO_EXPAND", "--region", REGION, "--no-fail-on-empty-changeset", "--parameter-overrides", *params], cwd=ROOT, check=True)
        return
    if args.action == "status":
        state = json.loads(state_path.read_text())
        item = build.batch_get_builds(ids=[state["build_id"]])["builds"][0]
        print(json.dumps({"tag": state["tag"], "status": item["buildStatus"], "phase": item.get("currentPhase"), "logs": item.get("logs"), "phases": [{"type": p["phaseType"], "status": p.get("phaseStatus"), "contexts": p.get("contexts")} for p in item.get("phases", [])]}, indent=2))
        return
    account = boto3.client("sts").get_caller_identity()["Account"]
    tag = args.tag or time.strftime("release-%Y%m%d-%H%M%S", time.gmtime())
    archive = out / f"{tag}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as target:
        for source in [ROOT / name for name in ["Dockerfile.api", "Dockerfile.worker", "Dockerfile.agent", "requirements.txt", "buildspec.yml", ".dockerignore", "services", "assets", "infra"]]:
            for path in (source.rglob("*") if source.is_dir() else [source]):
                if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc" and not path.name.startswith(".env"):
                    target.write(path, path.relative_to(ROOT).as_posix())
    bucket = f"launchpad-deploy-{account}-{REGION}"
    key = f"source/{tag}.zip"
    boto3.client("s3", region_name=REGION).upload_file(str(archive), bucket, key)
    ecr = boto3.client("ecr", region_name=REGION)
    repos = ["launchpad-agent"] if args.agent else ["launchpad-api", "launchpad-worker"]
    for repo in repos:
        try:
            ecr.describe_repositories(repositoryNames=[repo])
        except ecr.exceptions.RepositoryNotFoundException:
            ecr.create_repository(repositoryName=repo, imageTagMutability="IMMUTABLE")
    project = "launchpad-agent-build" if args.agent else "launchpad-image-build"
    if args.agent and not build.batch_get_projects(names=[project])["projects"]:
        base = build.batch_get_projects(names=["launchpad-image-build"])["projects"][0]
        build.create_project(name=project, source={"type": "S3", "location": f"{bucket}/{key}", "buildspec": "infra/buildspec-agent.yml"},
            artifacts={"type": "NO_ARTIFACTS"}, serviceRole=base["serviceRole"], timeoutInMinutes=20,
            environment={"type": "ARM_CONTAINER", "image": "aws/codebuild/amazonlinux-aarch64-standard:3.0", "computeType": "BUILD_GENERAL1_SMALL", "privilegedMode": True})
    result = build.start_build(projectName=project, sourceLocationOverride=f"{bucket}/{key}",
        environmentVariablesOverride=[{"name": "IMAGE_TAG", "value": tag, "type": "PLAINTEXT"}], timeoutInMinutesOverride=20)
    state = {"tag": tag, "build_id": result["build"]["id"], "images": {r: f"{account}.dkr.ecr.{REGION}.amazonaws.com/{r}:{tag}" for r in repos}}
    state_path.write_text(json.dumps(state, indent=2))
    print(json.dumps(state, indent=2))


if __name__ == "__main__":
    main()
