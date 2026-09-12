param(
  [string]$Region = "us-east-1",
  [string]$StackName = "launchpad-serverless",
  [int]$RetentionDays = 7,
  [int]$WorkerConcurrency = 2
)

$ErrorActionPreference = "Stop"
$account = aws sts get-caller-identity --query Account --output text --region $Region
$assetsBucket = "launchpad-deploy-$account-$Region"
$apiRepository = "launchpad-api"
$workerRepository = "launchpad-worker"

$bucketExists = $true
try { aws s3api head-bucket --bucket $assetsBucket 2>$null | Out-Null } catch { $bucketExists = $false }
if (-not $bucketExists) {
  aws s3api create-bucket --bucket $assetsBucket --region $Region
}
foreach ($repo in @($apiRepository, $workerRepository)) {
  $repositoryExists = $true
  try { aws ecr describe-repositories --repository-names $repo --region $Region 2>$null | Out-Null } catch { $repositoryExists = $false }
  if (-not $repositoryExists) {
    aws ecr create-repository --repository-name $repo --image-scanning-configuration scanOnPush=true --image-tag-mutability IMMUTABLE --region $Region | Out-Null
  }
}

$source = Join-Path $env:TEMP "launchpad-source.zip"
if (Test-Path -LiteralPath $source) { Remove-Item -LiteralPath $source -Force }
$sourceDirectory = Join-Path $env:TEMP "launchpad-build-source"
if (Test-Path -LiteralPath $sourceDirectory) { Remove-Item -LiteralPath $sourceDirectory -Recurse -Force }
New-Item -ItemType Directory -Path $sourceDirectory | Out-Null
Copy-Item Dockerfile.api,Dockerfile.worker,requirements.txt,buildspec.yml -Destination $sourceDirectory
Copy-Item services,assets,infra -Destination $sourceDirectory -Recurse
tar.exe -a -c -f $source -C $sourceDirectory .
aws s3 cp $source "s3://$assetsBucket/source/launchpad-source.zip" --region $Region | Out-Null

$buildRoleName = "LaunchpadCodeBuildServiceRole"
$roleExists = $true
try { aws iam get-role --role-name $buildRoleName 2>$null | Out-Null } catch { $roleExists = $false }
if (-not $roleExists) {
  aws iam create-role --role-name $buildRoleName --path /service-role/ --assume-role-policy-document file://infra/codebuild-trust.json | Out-Null
  aws iam put-role-policy --role-name $buildRoleName --policy-name LaunchpadImageBuild --policy-document file://infra/codebuild-policy.json
}
$roleArn = aws iam get-role --role-name $buildRoleName --query 'Role.Arn' --output text

$project = "launchpad-image-build"
$projectInput = @{
  name = $project
  source = @{ type = "S3"; location = "$assetsBucket/source/launchpad-source.zip"; buildspec = "buildspec.yml" }
  artifacts = @{ type = "NO_ARTIFACTS" }
  environment = @{ type = "LINUX_CONTAINER"; image = "aws/codebuild/standard:7.0"; computeType = "BUILD_GENERAL1_MEDIUM"; privilegedMode = $true }
  serviceRole = $roleArn
} | ConvertTo-Json -Depth 4
$projectInputPath = Join-Path $env:TEMP "launchpad-codebuild-project.json"
Set-Content -LiteralPath $projectInputPath -Value $projectInput -Encoding ascii
$projectExists = $false
try {
  $existingProject = aws codebuild batch-get-projects --names $project --region $Region --query 'projects[0].name' --output text 2>$null
  $projectExists = -not [string]::IsNullOrWhiteSpace($existingProject) -and $existingProject -ne "None"
} catch {}
if (-not $projectExists) {
  aws codebuild create-project --cli-input-json "file://$projectInputPath" --region $Region | Out-Null
} else {
  aws codebuild update-project --cli-input-json "file://$projectInputPath" --region $Region | Out-Null
}
$build = aws codebuild start-build --project-name $project --region $Region --query 'build.id' --output text
do {
  Start-Sleep -Seconds 10
  $status = aws codebuild batch-get-builds --ids $build --region $Region --query 'builds[0].buildStatus' --output text
  Write-Host "Image build: $status"
} while ($status -eq "IN_PROGRESS")
if ($status -ne "SUCCEEDED") { throw "CodeBuild image build failed: $build" }

$apiImage = "$account.dkr.ecr.$Region.amazonaws.com/$apiRepository:latest"
$workerImage = "$account.dkr.ecr.$Region.amazonaws.com/$workerRepository:latest"
$packaged = Join-Path $env:TEMP "launchpad-packaged.yaml"
aws cloudformation package --template-file infra/template.yaml --s3-bucket $assetsBucket --output-template-file $packaged --region $Region
$existingStack = ""
try { $existingStack = aws cloudformation describe-stacks --stack-name $StackName --region $Region --query 'Stacks[0].StackStatus' --output text 2>$null } catch {}
if ($existingStack -eq "ROLLBACK_COMPLETE") {
  aws cloudformation delete-stack --stack-name $StackName --region $Region
  aws cloudformation wait stack-delete-complete --stack-name $StackName --region $Region
}
aws cloudformation deploy --template-file $packaged --stack-name $StackName --capabilities CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND --parameter-overrides "ApiImageUri=$apiImage" "WorkerImageUri=$workerImage" "ArtifactRetentionDays=$RetentionDays" "WorkerConcurrency=$WorkerConcurrency" --region $Region
if ($LASTEXITCODE -ne 0) { throw "CloudFormation deployment failed." }

$bucket = aws cloudformation describe-stacks --stack-name $StackName --region $Region --query "Stacks[0].Outputs[?OutputKey=='WebBucketName'].OutputValue" --output text
$distribution = aws cloudformation describe-stacks --stack-name $StackName --region $Region --query "Stacks[0].Outputs[?OutputKey=='WebsiteUrl'].OutputValue" --output text
$env:NEXT_PUBLIC_API_BASE = "/v1"
$env:LAUNCHPAD_STATIC_EXPORT = "true"
npm run build
aws s3 sync out "s3://$bucket" --delete --region $Region
$domain = ($distribution -replace '^https://', '')
$distributionId = aws cloudfront list-distributions --query "DistributionList.Items[?DomainName=='$domain'].Id | [0]" --output text
aws cloudfront create-invalidation --distribution-id $distributionId --paths '/*' | Out-Null
Write-Host "Launchpad is live at $distribution"
