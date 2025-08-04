# Test script per l'algoritmo grayscale OpenMP
param(
    [string] $ApiBase = $env:API_BASE,
    [string] $AdminKey = "dev-admin",
    [string] $Account = "544547773663",
    [string] $Region = "us-east-1"
)

if (-not $ApiBase) {
    Write-Error "Variabile API_BASE non impostata. Eseguire prima gen_env.ps1"
    exit 1
}

Write-Host "🎨 Testing Grayscale OpenMP Algorithm" -ForegroundColor Green
Write-Host "API Base: $ApiBase" -ForegroundColor Yellow
Write-Host

# Registra algoritmo grayscale
Write-Host "1. 📝 Registering grayscale algorithm..." -ForegroundColor Cyan

$grayscaleAlgo = @{
    algo_id = "grayscale"
    image_uri = "$Account.dkr.ecr.$Region.amazonaws.com/mip-algos:grayscale"
    cpu = 2048
    memory = 4096
    desired_count = 1
    command = @("/app/adapter.py")
    env = @{
        OMP_NUM_THREADS = "4"
        GRAYSCALE_PASSES = "1"
    }
}

try {
    $response = Invoke-RestMethod -Uri "$ApiBase/admin/algorithms" -Method POST -Headers @{
        'Content-Type' = 'application/json'
        'x-admin-key' = $AdminKey
    } -Body ($grayscaleAlgo | ConvertTo-Json -Depth 10)
    
    Write-Host "✅ Grayscale algorithm registered successfully" -ForegroundColor Green
    $response | ConvertTo-Json -Depth 10 | Write-Host
} catch {
    if ($_.Exception.Response.StatusCode -eq 409) {
        Write-Host "⚠️ Algorithm already exists, continuing..." -ForegroundColor Yellow
    } else {
        Write-Host "❌ Failed to register algorithm: $($_.Exception.Message)" -ForegroundColor Red
        exit 1
    }
}

# Attendi provisioning
Write-Host "`n⏱️ Waiting for provisioning to complete..." -ForegroundColor Cyan
Start-Sleep -Seconds 45

# Controlla status
Write-Host "`n2. 🔍 Checking algorithm status..." -ForegroundColor Cyan
try {
    $status = Invoke-RestMethod -Uri "$ApiBase/admin/algorithms/grayscale" -Method GET -Headers @{
        'x-admin-key' = $AdminKey
    }
    
    Write-Host "Algorithm status: $($status.status)" -ForegroundColor $(if ($status.status -eq "ACTIVE") { "Green" } else { "Yellow" })
    $status | ConvertTo-Json -Depth 10 | Write-Host
} catch {
    Write-Host "❌ Failed to check status: $($_.Exception.Message)" -ForegroundColor Red
}

# Test con diversi parametri
Write-Host "`n3. 🧪 Testing grayscale processing..." -ForegroundColor Cyan

$testCases = @(
    @{
        name = "Standard processing"
        job = @{
            job_id = "grayscale-test-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
            client_id = "test-client-grayscale"
            pacs = @{
                study_id = "test-study"
                series_id = "test-series"
                image_id = "test-image"
                scope = "image"
            }
        }
    },
    @{
        name = "Multi-pass processing"
        job = @{
            job_id = "grayscale-multipass-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
            client_id = "test-client-grayscale"
            passes = 3
            threads = 8
            pacs = @{
                study_id = "test-study-multi"
                series_id = "test-series-multi"
                image_id = "test-image-multi"
                scope = "image"
            }
        }
    }
)

foreach ($testCase in $testCases) {
    Write-Host "`nTesting: $($testCase.name)" -ForegroundColor Yellow
    
    try {
        $response = Invoke-RestMethod -Uri "$ApiBase/process/grayscale" -Method POST -Headers @{
            'Content-Type' = 'application/json'
        } -Body ($testCase.job | ConvertTo-Json -Depth 10)
        
        Write-Host "✅ Job submitted successfully!" -ForegroundColor Green
        Write-Host "Job ID: $($testCase.job.job_id)" -ForegroundColor White
        Write-Host "SQS Message ID: $($response.sqs_message_id)" -ForegroundColor White
        
    } catch {
        Write-Host "❌ Job submission failed: $($_.Exception.Message)" -ForegroundColor Red
        if ($_.Exception.Response) {
            $stream = $_.Exception.Response.GetResponseStream()
            $reader = New-Object System.IO.StreamReader($stream)
            $errorBody = $reader.ReadToEnd()
            Write-Host "Response: $errorBody" -ForegroundColor Red
        }
    }
    
    Start-Sleep -Seconds 2
}

Write-Host "`n4. 📊 Algorithm performance info..." -ForegroundColor Cyan
Write-Host "OpenMP Threads: 4 (configurable via env)" -ForegroundColor White
Write-Host "Memory: 4GB (higher for image processing)" -ForegroundColor White
Write-Host "CPU: 2048 units (1 vCPU)" -ForegroundColor White
Write-Host "Supports: PNG, JPEG, BMP, TGA input via STB" -ForegroundColor White
Write-Host "DICOM Support: Auto-conversion via pydicom" -ForegroundColor White

Write-Host "`n🎉 Grayscale test completed!" -ForegroundColor Green
Write-Host "`nMonitor logs in CloudWatch:" -ForegroundColor Yellow
Write-Host "- ECS: /ecs/mip-grayscale" -ForegroundColor White
Write-Host "- Lambda: /aws/lambda/ImgPipeline-*" -ForegroundColor White
