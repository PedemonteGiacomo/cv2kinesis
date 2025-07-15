# Build and push script for both services (PowerShell)
param(
    [string]$Region = "eu-central-1",
    [string]$Service = "all"  # "grayscale", "stream", or "all"
)

$ErrorActionPreference = "Stop"

Write-Host "Building and pushing hybrid pipeline services to ECR..." -ForegroundColor Green

# Get AWS account ID
$AccountId = (aws sts get-caller-identity --query Account --output text)
Write-Host "Region: $Region" -ForegroundColor Yellow
Write-Host "Account: $AccountId" -ForegroundColor Yellow

# Get ECR login token
Write-Host "Logging into ECR..." -ForegroundColor Cyan
aws ecr get-login-password --region $Region | docker login --username AWS --password-stdin "$AccountId.dkr.ecr.$Region.amazonaws.com"

function Build-And-Push-Service {
    param(
        [string]$ServiceName,
        [string]$DockerFile,
        [string]$ServicePath
    )
    
    $EcrRepository = "hybrid-pipeline-$ServiceName"
    $ImageTag = "latest"
    $EcrUri = "$AccountId.dkr.ecr.$Region.amazonaws.com/$EcrRepository:$ImageTag"
    
    Write-Host "Building $ServiceName service..." -ForegroundColor Cyan
    
    Push-Location "services\$ServicePath"
    try {
        docker build -f $DockerFile -t "${EcrRepository}:${ImageTag}" .
        docker tag "${EcrRepository}:${ImageTag}" $EcrUri
        docker push $EcrUri
        Write-Host "Successfully pushed $ServiceName: $EcrUri" -ForegroundColor Green
    }
    finally {
        Pop-Location
    }
}

# Build and push based on parameter
if ($Service -eq "grayscale" -or $Service -eq "all") {
    Build-And-Push-Service -ServiceName "grayscale" -DockerFile "Dockerfile_aws" -ServicePath "grayscale_service"
}

if ($Service -eq "stream" -or $Service -eq "all") {
    Build-And-Push-Service -ServiceName "stream" -DockerFile "Dockerfile" -ServicePath "stream_service"
}

Write-Host "`nAll services built and pushed successfully!" -ForegroundColor Green
Write-Host "Now you can deploy the CDK stack with: cdk deploy" -ForegroundColor Yellow

Write-Host "`nService URLs will be available in CDK outputs:" -ForegroundColor Cyan
Write-Host "- Image Input Bucket: images-input-$AccountId-$Region" -ForegroundColor White
Write-Host "- Image Output Bucket: images-output-$AccountId-$Region" -ForegroundColor White
Write-Host "- Video Input Bucket: videos-input-$AccountId-$Region" -ForegroundColor White
Write-Host "- Video Frames Bucket: video-frames-$AccountId-$Region" -ForegroundColor White
