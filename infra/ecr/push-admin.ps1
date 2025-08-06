# Build and push admin portal to ECR
param(
    [Parameter(Mandatory=$false)]
    [string]$Region = $env:AWS_REGION,
    
    [Parameter(Mandatory=$false)]
    [string]$Account = $env:AWS_ACCOUNT_ID,
    
    [Parameter(Mandatory=$false)]
    [string]$Tag = "latest",
    
    [Parameter(Mandatory=$false)]
    [switch]$NoCache
)

# Get current directory
$ScriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$AdminPath = Join-Path $ScriptPath "..\clients\react-admin"

Write-Host "=== Building and Pushing MIP Admin Portal ===" -ForegroundColor Green

# Validate parameters
if (-not $Region) {
    $Region = (aws configure get region 2>$null)
    if (-not $Region) {
        $Region = "us-east-1"
        Write-Warning "AWS_REGION not set, defaulting to $Region"
    }
}

if (-not $Account) {
    try {
        $Account = (aws sts get-caller-identity --query Account --output text 2>$null)
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to get AWS account ID"
        }
    }
    catch {
        Write-Error "Unable to determine AWS Account ID. Please set AWS_ACCOUNT_ID environment variable or ensure AWS CLI is configured."
        exit 1
    }
}

$RepositoryName = "mip-admin-portal"
$RepositoryUri = "$Account.dkr.ecr.$Region.amazonaws.com/$RepositoryName"

Write-Host "Region: $Region" -ForegroundColor Cyan
Write-Host "Account ID: $Account" -ForegroundColor Cyan
Write-Host "Repository URI: $RepositoryUri" -ForegroundColor Cyan
Write-Host "Tag: $Tag" -ForegroundColor Cyan

# Change to admin directory
Push-Location $AdminPath

try {
    # Check if admin directory exists
    if (-not (Test-Path ".")) {
        Write-Error "Admin portal directory not found at $AdminPath"
        exit 1
    }

    # Check if package.json exists
    if (-not (Test-Path "package.json")) {
        Write-Error "package.json not found. Run from the react-admin directory."
        exit 1
    }

    # Login to ECR
    Write-Host "`n--- Authenticating to ECR ---" -ForegroundColor Yellow
    aws ecr get-login-password --region $Region | docker login --username AWS --password-stdin $RepositoryUri
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to login to ECR"
        exit 1
    }
    Write-Host "Successfully logged in to ECR" -ForegroundColor Green

    # Build the Docker image
    Write-Host "`n--- Building Docker image ---" -ForegroundColor Yellow
    $ImageTag = "${RepositoryUri}:${Tag}"
    
    # Create build arguments for React environment variables
    $BuildArgs = @()
    if ($env:REACT_APP_USER_POOL_ID) {
        $BuildArgs += "--build-arg", "REACT_APP_USER_POOL_ID=$($env:REACT_APP_USER_POOL_ID)"
    }
    if ($env:REACT_APP_USER_POOL_CLIENT_ID) {
        $BuildArgs += "--build-arg", "REACT_APP_USER_POOL_CLIENT_ID=$($env:REACT_APP_USER_POOL_CLIENT_ID)"
    }
    if ($env:REACT_APP_AWS_REGION) {
        $BuildArgs += "--build-arg", "REACT_APP_AWS_REGION=$($env:REACT_APP_AWS_REGION)"
    }
    if ($env:REACT_APP_API_BASE_URL) {
        $BuildArgs += "--build-arg", "REACT_APP_API_BASE_URL=$($env:REACT_APP_API_BASE_URL)"
    }
    
    # Add no-cache flag if requested
    if ($NoCache) {
        $BuildArgs += "--no-cache"
        Write-Host "Building without cache" -ForegroundColor Yellow
    }
    
    Write-Host "Building image: $ImageTag" -ForegroundColor Cyan
    if ($BuildArgs.Count -gt 0) {
        Write-Host "Build arguments: $($BuildArgs -join ' ')" -ForegroundColor Cyan
        docker build -t $ImageTag $BuildArgs .
    } else {
        docker build -t $ImageTag .
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to build Docker image"
        exit 1
    }
    Write-Host "Docker image built successfully" -ForegroundColor Green

    # Push the image to ECR
    Write-Host "`n--- Pushing image to ECR ---" -ForegroundColor Yellow
    docker push $ImageTag
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to push Docker image to ECR"
        exit 1
    }
    Write-Host "Image pushed successfully to ECR" -ForegroundColor Green

    # Tag as latest if not already
    if ($Tag -ne "latest") {
        Write-Host "`n--- Tagging as latest ---" -ForegroundColor Yellow
        $LatestTag = "${RepositoryUri}:latest"
        docker tag $ImageTag $LatestTag
        docker push $LatestTag
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Failed to push latest tag, but main tag was successful"
        } else {
            Write-Host "Latest tag pushed successfully" -ForegroundColor Green
        }
    }

    # Clean up local images (optional)
    Write-Host "`n--- Cleaning up local images ---" -ForegroundColor Yellow
    docker rmi $ImageTag 2>$null
    if ($Tag -ne "latest") {
        docker rmi "${RepositoryUri}:latest" 2>$null
    }

    Write-Host "`n=== Admin Portal Build and Push Complete ===" -ForegroundColor Green
    Write-Host "Image URI: $ImageTag" -ForegroundColor Cyan
    Write-Host "`nTo deploy the admin stack, run:" -ForegroundColor Yellow
    Write-Host "cd ..\infra" -ForegroundColor White
    Write-Host "cdk deploy AdminStack" -ForegroundColor White

}
catch {
    Write-Error "An error occurred: $_"
    exit 1
}
finally {
    Pop-Location
}

# Output image URI for automation
Write-Output $ImageTag
