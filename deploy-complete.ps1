# Deploy completo dell'architettura MIP
param(
    [string] $Environment = "dev",
    [switch] $SkipInfra,
    [switch] $SkipExamples,
    [switch] $Force,
    [switch] $Verbose
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message, [string]$Status = "INFO")
    
    $color = switch ($Status) {
        "OK" { "Green" }
        "ERROR" { "Red" }
        "INFO" { "Cyan" }
        "WARNING" { "Yellow" }
    }
    
    $symbol = switch ($Status) {
        "OK" { "✅" }
        "ERROR" { "❌" }
        "INFO" { "🚀" }
        "WARNING" { "⚠️" }
    }
    
    Write-Host "$symbol $Message" -ForegroundColor $color
}

function Invoke-SafeCommand {
    param(
        [string]$Command,
        [string]$WorkingDirectory = $PWD,
        [string]$Description = ""
    )
    
    if ($Description) {
        Write-Step "Executing: $Description" "INFO"
    }
    
    if ($Verbose) {
        Write-Host "CMD: $Command" -ForegroundColor Gray
        Write-Host "DIR: $WorkingDirectory" -ForegroundColor Gray
    }
    
    try {
        Push-Location $WorkingDirectory
        Invoke-Expression $Command
        
        if ($LASTEXITCODE -ne 0) {
            throw "Command failed with exit code $LASTEXITCODE"
        }
        
        if ($Description) {
            Write-Step "$Description completed" "OK"
        }
    } catch {
        Write-Step "Failed: $Description" "ERROR"
        Write-Host $_.Exception.Message -ForegroundColor Red
        throw
    } finally {
        Pop-Location
    }
}

function Test-Prerequisites {
    Write-Host "`n🔧 Checking prerequisites..." -ForegroundColor Cyan
    
    # Check AWS CLI
    try {
        aws --version | Out-Null
        Write-Step "AWS CLI available" "OK"
    } catch {
        Write-Step "AWS CLI not found" "ERROR"
        throw "Please install AWS CLI: https://aws.amazon.com/cli/"
    }
    
    # Check CDK
    try {
        cdk --version | Out-Null
        Write-Step "AWS CDK available" "OK"
    } catch {
        Write-Step "AWS CDK not found" "ERROR"
        throw "Please install AWS CDK: npm install -g aws-cdk"
    }
    
    # Check Docker
    try {
        docker --version | Out-Null
        Write-Step "Docker available" "OK"
    } catch {
        Write-Step "Docker not found" "ERROR"
        throw "Please install Docker Desktop"
    }
    
    # Check AWS credentials
    try {
        $identity = aws sts get-caller-identity --output json | ConvertFrom-Json
        Write-Step "AWS credentials configured (Account: $($identity.Account))" "OK"
    } catch {
        Write-Step "AWS credentials not configured" "ERROR"
        throw "Please configure AWS credentials: aws configure"
    }
    
    # Check Node.js (for CDK)
    try {
        node --version | Out-Null
        Write-Step "Node.js available" "OK"
    } catch {
        Write-Step "Node.js not found" "WARNING"
        Write-Host "Node.js recommended for better CDK experience" -ForegroundColor Yellow
    }
}

function Deploy-Infrastructure {
    Write-Host "`n🏗️ Deploying infrastructure..." -ForegroundColor Cyan
    
    $infraDir = "infra"
    
    # Install CDK dependencies
    Invoke-SafeCommand "pip install -r requirements.txt" $infraDir "Installing CDK dependencies"
    
    # CDK bootstrap (if needed)
    try {
        Write-Step "Checking CDK bootstrap status" "INFO"
        $bootstrapStatus = aws cloudformation describe-stacks --stack-name CDKToolkit --region $env:AWS_DEFAULT_REGION 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Step "Bootstrapping CDK (first time setup)" "INFO"
            Invoke-SafeCommand "cdk bootstrap" $infraDir "CDK Bootstrap"
        } else {
            Write-Step "CDK already bootstrapped" "OK"
        }
    } catch {
        Write-Step "CDK bootstrap check failed, proceeding anyway" "WARNING"
    }
    
    # Generate environment configuration
    $envScript = "gen_env\gen_env.ps1"
    if (Test-Path $envScript) {
        Invoke-SafeCommand ".\gen_env\gen_env.ps1 -Environment $Environment" $infraDir "Generating environment config"
    }
    
    # CDK synthesis
    Invoke-SafeCommand "cdk synth" $infraDir "CDK Synthesis"
    
    # CDK deploy
    $deployCmd = if ($Force) { "cdk deploy --all --require-approval never" } else { "cdk deploy --all" }
    Invoke-SafeCommand $deployCmd $infraDir "CDK Deployment"
    
    Write-Step "Infrastructure deployment completed" "OK"
}

function Create-ECR-Repositories {
    Write-Host "`n📦 Creating ECR repositories..." -ForegroundColor Cyan
    
    $ecrScript = "infra\ecr\create-ecr-repos.ps1"
    if (Test-Path $ecrScript) {
        Invoke-SafeCommand ".\infra\ecr\create-ecr-repos.ps1" "." "Creating ECR repositories"
    } else {
        Write-Step "ECR creation script not found, skipping" "WARNING"
    }
}

function Deploy-ExampleAlgorithms {
    Write-Host "`n🧪 Deploying example algorithms..." -ForegroundColor Cyan
    
    $exampleDirs = @(
        "containers\examples\python-simple",
        "containers\examples\python-advanced", 
        "containers\grayscale"
    )
    
    foreach ($dir in $exampleDirs) {
        if (Test-Path $dir) {
            $algoName = Split-Path $dir -Leaf
            Write-Step "Deploying $algoName algorithm" "INFO"
            
            # Validate first
            if (Test-Path "scripts\validate-algorithm.ps1") {
                try {
                    Invoke-SafeCommand ".\scripts\validate-algorithm.ps1 -AlgorithmPath `"$dir`" -Fix" "." "Validating $algoName"
                } catch {
                    Write-Step "Validation failed for $algoName, skipping deployment" "WARNING"
                    continue
                }
            }
            
            # Deploy
            $deployScript = Join-Path $dir "deploy.ps1"
            if (Test-Path $deployScript) {
                try {
                    Invoke-SafeCommand ".\deploy.ps1" $dir "Deploying $algoName"
                } catch {
                    Write-Step "Failed to deploy $algoName" "WARNING"
                    Write-Host "Continuing with other algorithms..." -ForegroundColor Yellow
                }
            } else {
                Write-Step "No deploy script found for $algoName" "WARNING"
            }
        }
    }
}

function Deploy-PACSApi {
    Write-Host "`n🏥 Deploying PACS API..." -ForegroundColor Cyan
    
    $pacsDir = "pacs_api"
    
    if (Test-Path $pacsDir) {
        # Build and push PACS API
        $pushScript = "infra\ecr\push-pacs.ps1"
        if (Test-Path $pushScript) {
            Invoke-SafeCommand ".\infra\ecr\push-pacs.ps1" "." "Building and pushing PACS API"
        } else {
            Write-Step "PACS push script not found" "WARNING"
        }
    } else {
        Write-Step "PACS API directory not found" "WARNING"
    }
}

function Deploy-ReactApp {
    Write-Host "`n⚛️ Building React frontend..." -ForegroundColor Cyan
    
    $reactDir = "infra\clients\react-app"
    
    if (Test-Path $reactDir) {
        # Install dependencies
        Invoke-SafeCommand "npm install" $reactDir "Installing React dependencies"
        
        # Build for production
        Invoke-SafeCommand "npm run build" $reactDir "Building React app"
        
        Write-Step "React app built successfully" "OK"
        Write-Host "Note: Deploy to S3/CloudFront using your preferred method" -ForegroundColor Yellow
    } else {
        Write-Step "React app directory not found" "WARNING"
    }
}

function Test-Deployment {
    Write-Host "`n🧪 Testing deployment..." -ForegroundColor Cyan
    
    # Get API endpoints from CDK outputs
    try {
        $outputs = aws cloudformation describe-stacks --stack-name ImgPipeline --query "Stacks[0].Outputs" --output json | ConvertFrom-Json
        
        $apiEndpoint = ($outputs | Where-Object { $_.OutputKey -eq "ProcessingApiEndpoint" }).OutputValue
        $adminEndpoint = ($outputs | Where-Object { $_.OutputKey -eq "AdminApiEndpoint" }).OutputValue
        
        if ($apiEndpoint) {
            Write-Step "Processing API Endpoint: $apiEndpoint" "OK"
        }
        
        if ($adminEndpoint) {
            Write-Step "Admin API Endpoint: $adminEndpoint" "OK"
        }
        
        # Test health endpoint
        if ($apiEndpoint) {
            try {
                $healthUrl = "$apiEndpoint/health"
                $response = Invoke-RestMethod -Uri $healthUrl -Method GET -TimeoutSec 10
                Write-Step "API health check passed" "OK"
            } catch {
                Write-Step "API health check failed" "WARNING"
                Write-Host "This might be normal if deployment is still propagating" -ForegroundColor Yellow
            }
        }
        
    } catch {
        Write-Step "Could not retrieve API endpoints" "WARNING"
        Write-Host "Check CloudFormation outputs manually" -ForegroundColor Yellow
    }
}

function Show-NextSteps {
    Write-Host "`n✨ Deployment Summary" -ForegroundColor Green
    
    try {
        $outputs = aws cloudformation describe-stacks --stack-name ImgPipeline --query "Stacks[0].Outputs" --output json | ConvertFrom-Json
        
        Write-Host "`n📋 Important Endpoints:" -ForegroundColor Cyan
        foreach ($output in $outputs) {
            Write-Host "  $($output.OutputKey): $($output.OutputValue)" -ForegroundColor White
        }
        
        Write-Host "`n🚀 Next Steps:" -ForegroundColor Yellow
        Write-Host "1. Create your first algorithm:" -ForegroundColor White
        Write-Host "   .\scripts\new-algorithm.ps1 -Name my-algo -Type python" -ForegroundColor Gray
        
        Write-Host "2. Register an algorithm via API:" -ForegroundColor White
        Write-Host "   curl -X POST `"`$ADMIN_ENDPOINT/algorithms`" -H `"x-admin-key: YOUR_KEY`" ..." -ForegroundColor Gray
        
        Write-Host "3. Submit a processing job:" -ForegroundColor White
        Write-Host "   curl -X POST `"`$API_ENDPOINT/process/algorithm-name`" ..." -ForegroundColor Gray
        
        Write-Host "4. Monitor with AWS Console:" -ForegroundColor White
        Write-Host "   - CloudWatch Logs for debugging" -ForegroundColor Gray
        Write-Host "   - DynamoDB for algorithm registry" -ForegroundColor Gray
        Write-Host "   - ECS for running containers" -ForegroundColor Gray
        Write-Host "   - SQS for job queues" -ForegroundColor Gray
        
    } catch {
        Write-Host "Could not retrieve deployment details" -ForegroundColor Yellow
        Write-Host "Check AWS CloudFormation console for stack outputs" -ForegroundColor White
    }
}

# Main deployment sequence
Write-Host "🚀 MIP Complete Deployment" -ForegroundColor Green
Write-Host "Environment: $Environment" -ForegroundColor Yellow

try {
    # Pre-flight checks
    Test-Prerequisites
    
    # Infrastructure
    if (-not $SkipInfra) {
        Deploy-Infrastructure
        Create-ECR-Repositories
    } else {
        Write-Step "Skipping infrastructure deployment" "INFO"
    }
    
    # PACS API
    Deploy-PACSApi
    
    # Example algorithms
    if (-not $SkipExamples) {
        Deploy-ExampleAlgorithms
    } else {
        Write-Step "Skipping example algorithms" "INFO"
    }
    
    # Frontend
    Deploy-ReactApp
    
    # Testing
    Test-Deployment
    
    # Success!
    Write-Host "`n🎉 Deployment Completed Successfully!" -ForegroundColor Green
    Show-NextSteps
    
} catch {
    Write-Host "`n💥 Deployment Failed!" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    
    Write-Host "`n🔧 Troubleshooting:" -ForegroundColor Yellow
    Write-Host "1. Check AWS credentials: aws sts get-caller-identity" -ForegroundColor White
    Write-Host "2. Check CDK status: cdk doctor" -ForegroundColor White
    Write-Host "3. Check logs: CloudWatch Logs in AWS Console" -ForegroundColor White
    Write-Host "4. Retry with -Verbose for detailed output" -ForegroundColor White
    
    exit 1
}
