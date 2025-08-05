# Script completo per deploy e test della nuova architettura
param(
    [string] $Region = "us-east-1",
    [string] $Account = "544547773663",
    [switch] $SkipECR,
    [switch] $SkipDeploy,
    [switch] $TestOnly,
    [switch] $SkipTest
)

$ErrorActionPreference = "Stop"

Write-Host "Deploy completo architettura dinamica MIP" -ForegroundColor Green
Write-Host "Region: $Region, Account: $Account" -ForegroundColor Yellow


# Torna alla root del progetto
Push-Location (Join-Path $PSScriptRoot "..")

# Spostati nella cartella infra per i comandi CDK
Push-Location $PSScriptRoot

try {
    if (-not $TestOnly) {
        # 1. ECR e build immagini
        if (-not $SkipECR) {
            Write-Host "1. Preparing ECR repositories..." -ForegroundColor Cyan
            & "$PSScriptRoot\ecr\create-ecr-repos.ps1" -Region $Region -Account $Account
            # if ($LASTEXITCODE -ne 0) { throw "ECR creation failed" }

            Write-Host "Building and pushing images..." -ForegroundColor Cyan
            & "$PSScriptRoot\ecr\push-algos.ps1" -Region $Region -Account $Account
            if ($LASTEXITCODE -ne 0) { throw "Image push failed" }

            Write-Host "Pushing PACS API..." -ForegroundColor Cyan
            & "$PSScriptRoot\ecr\push-pacs.ps1" -Region $Region -Account $Account
            if ($LASTEXITCODE -ne 0) { throw "PACS push failed" }
        }

        # 2. Deploy CDK
        if (-not $SkipDeploy) {
            $env:AWS_REGION = $Region
            $env:AWS_ACCOUNT = $Account
            Write-Host "Setting AWS region to $env:AWS_REGION and account to $env:AWS_ACCOUNT" -ForegroundColor Yellow

            Write-Host "2. Deploying CDK stacks..." -ForegroundColor Cyan
            

            Write-Host "Deploying Imports stack..." -ForegroundColor Yellow
            cdk deploy Imports --require-approval never
            if ($LASTEXITCODE -ne 0) { throw "Imports deploy failed" }

            Write-Host "Deploying PacsApi stack..." -ForegroundColor Yellow
            cdk deploy PacsApi --require-approval never
            if ($LASTEXITCODE -ne 0) { throw "PacsApi deploy failed" }

            Write-Host "Deploying ImgPipeline stack..." -ForegroundColor Yellow
            $env:ADMIN_KEY = "dev-admin-$(Get-Random)"
            cdk deploy ImgPipeline --require-approval never
            if ($LASTEXITCODE -ne 0) { throw "ImgPipeline deploy failed" }

            # Torna alla root dopo il deploy CDK
            Pop-Location

            Write-Host "All stacks deployed successfully!" -ForegroundColor Green
        }

        # 3. Generate environment variables
        Write-Host "3. Generating environment variables..." -ForegroundColor Cyan
        & "$PSScriptRoot\gen_env\gen_env.ps1" -ImgStack "ImgPipeline" -PacsStack "PacsApi"
        if ($LASTEXITCODE -ne 0) { throw "Environment generation failed" }

        # Import variables
        . "$PSScriptRoot\gen_env\env.ps1"
        Write-Host "Environment variables loaded." -ForegroundColor Green
    }

    if (-not $SkipTest) {
        # 4. Test API amministrazione
        Write-Host "4. Testing administration API..." -ForegroundColor Cyan

        if (-not $env:API_BASE) {
            Write-Host "Loading environment variables..." -ForegroundColor Yellow
            if (Test-Path "$PSScriptRoot\gen_env\env.ps1") {
                . "$PSScriptRoot\gen_env\env.ps1"
            } else {
                throw "Environment file not found. Run without -TestOnly first."
            }
        }

        # Test admin API
        & "$PSScriptRoot\test\test-admin-api.ps1" -AdminKey $env:ADMIN_KEY

        Write-Host "Waiting for provisioning to complete..." -ForegroundColor Cyan
        Start-Sleep -Seconds 60

        # 5. Test end-to-end processing
        Write-Host "5. Testing end-to-end processing..." -ForegroundColor Cyan
        
        $testJob = @{
            job_id = "e2e-test-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
            client_id = "test-client-e2e"
            pacs    = @{
                study_id  = "liver1/phantomx_abdomen_pelvis_dataset/D55-01"
                series_id = "300/AiCE_BODY-SHARP_300_172938.900"
                image_id  = "IM-0135-0095.dcm"
                scope     = "image"
            }
        } | ConvertTo-Json -Depth 4 -Compress

        try {
            Write-Host "Sending test job to processing_1..." -ForegroundColor Yellow
            $response = Invoke-RestMethod -Uri "$env:API_BASE/process/processing_1" -Method POST -Headers @{
                'Content-Type' = 'application/json'
            } -Body ($testJob | ConvertTo-Json -Depth 10)
            
            Write-Host "Job submitted successfully!" -ForegroundColor Green
            $response | ConvertTo-Json -Depth 10 | Write-Host
            
        } catch {
            Write-Host "Job submission failed: $($_.Exception.Message)" -ForegroundColor Red
            if ($_.Exception.Response) {
                $stream = $_.Exception.Response.GetResponseStream()
                $reader = New-Object System.IO.StreamReader($stream)
                $errorBody = $reader.ReadToEnd()
                Write-Host "Response: $errorBody" -ForegroundColor Red
            }
        }
    }

    Write-Host "\nDeploy and test completed!" -ForegroundColor Green
    Write-Host "\nNext steps:" -ForegroundColor Yellow
    Write-Host "1. Check CloudWatch logs for Lambda functions" -ForegroundColor White
    Write-Host "2. Monitor ECS services in the console" -ForegroundColor White
    Write-Host "3. Test with the React frontend" -ForegroundColor White
    Write-Host "\nAPI Endpoints:" -ForegroundColor Yellow
    Write-Host "- Processing: $($env:API_BASE)/process/{algo_id}" -ForegroundColor White
    Write-Host "- Admin: $($env:API_BASE)/admin/algorithms" -ForegroundColor White
    Write-Host "- Admin Key: $($env:ADMIN_KEY)" -ForegroundColor White
    Write-Host "- WebSocket: $($env:WS_ENDPOINT)" -ForegroundColor White
}
catch {
    Write-Host "\nError: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
finally {
    Pop-Location
}
