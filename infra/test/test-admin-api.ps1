# Test script per le API di amministrazione degli algoritmi
param(
    [string] $ApiBase = $env:API_BASE,
    [string] $AdminKey = "dev-admin"
)

if (-not $ApiBase) {
    Write-Error "Variabile API_BASE non impostata. Eseguire prima gen_env.ps1"
    exit 1
}

Write-Host "🧪 Testing Algorithm Administration API" -ForegroundColor Green
Write-Host "API Base: $ApiBase" -ForegroundColor Yellow
Write-Host "Admin Key: $AdminKey" -ForegroundColor Yellow
Write-Host

# Function per invocare API
function Invoke-AdminApi {
    param(
        [string] $Method,
        [string] $Path,
        [object] $Body = $null,
        [string] $QueryString = ""
    )
    
    $headers = @{
        'Content-Type' = 'application/json'
        'x-admin-key' = $AdminKey
    }
    
    $uri = "$ApiBase$Path$QueryString"
    
    try {
        if ($Body) {
            $response = Invoke-RestMethod -Uri $uri -Method $Method -Headers $headers -Body ($Body | ConvertTo-Json -Depth 10)
        } else {
            $response = Invoke-RestMethod -Uri $uri -Method $Method -Headers $headers
        }
        return $response
    } catch {
        Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
        if ($_.Exception.Response) {
            $stream = $_.Exception.Response.GetResponseStream()
            $reader = New-Object System.IO.StreamReader($stream)
            $errorBody = $reader.ReadToEnd()
            Write-Host "Response: $errorBody" -ForegroundColor Red
        }
        return $null
    }
}

Write-Host "1. 📝 Registering processing_1 algorithm..." -ForegroundColor Cyan
$algo1 = @{
    algo_id = "processing_1"
    image_uri = "544547773663.dkr.ecr.us-east-1.amazonaws.com/mip-algos:processing_1"
    cpu = 1024
    memory = 2048
    desired_count = 1
    command = @("/app/worker.sh")
    env = @{
        EXTRA_DEBUG = "1"
    }
}

$result = Invoke-AdminApi -Method POST -Path "/admin/algorithms" -Body $algo1
if ($result) {
    Write-Host "✅ Algorithm registered successfully" -ForegroundColor Green
    $result | ConvertTo-Json -Depth 10 | Write-Host
} else {
    Write-Host "❌ Failed to register algorithm" -ForegroundColor Red
}

Write-Host "`n2. 📝 Registering processing_6 algorithm..." -ForegroundColor Cyan
$algo2 = @{
    algo_id = "processing_6"
    image_uri = "544547773663.dkr.ecr.us-east-1.amazonaws.com/mip-algos:processing_6"
    cpu = 1024
    memory = 2048
    desired_count = 1
    command = @("/app/worker.sh")
    env = @{}
}

$result = Invoke-AdminApi -Method POST -Path "/admin/algorithms" -Body $algo2
if ($result) {
    Write-Host "✅ Algorithm registered successfully" -ForegroundColor Green
    $result | ConvertTo-Json -Depth 10 | Write-Host
} else {
    Write-Host "❌ Failed to register algorithm" -ForegroundColor Red
}

Start-Sleep -Seconds 5

Write-Host "`n3. 📋 Listing all algorithms..." -ForegroundColor Cyan
$result = Invoke-AdminApi -Method GET -Path "/admin/algorithms"
if ($result) {
    Write-Host "✅ Algorithms listed successfully" -ForegroundColor Green
    $result | ConvertTo-Json -Depth 10 | Write-Host
} else {
    Write-Host "❌ Failed to list algorithms" -ForegroundColor Red
}

Write-Host "`n4. 🔍 Getting specific algorithm details..." -ForegroundColor Cyan
$result = Invoke-AdminApi -Method GET -Path "/admin/algorithms/processing_1"
if ($result) {
    Write-Host "✅ Algorithm details retrieved successfully" -ForegroundColor Green
    $result | ConvertTo-Json -Depth 10 | Write-Host
} else {
    Write-Host "❌ Failed to get algorithm details" -ForegroundColor Red
}

Write-Host "`n5. ✏️ Updating algorithm..." -ForegroundColor Cyan
$update = @{
    cpu = 2048
    memory = 4096
}

$result = Invoke-AdminApi -Method PATCH -Path "/admin/algorithms/processing_1" -Body $update
if ($result) {
    Write-Host "✅ Algorithm updated successfully" -ForegroundColor Green
    $result | ConvertTo-Json -Depth 10 | Write-Host
} else {
    Write-Host "❌ Failed to update algorithm" -ForegroundColor Red
}

Write-Host "`n6. 🧪 Testing processing request..." -ForegroundColor Cyan
$job = @{
    job_id = "test-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    client_id = "test-client"
    pacs = @{
        study_id = "test-study"
        series_id = "test-series"
        image_id = "test-image"
        scope = "image"
    }
}

try {
    $result = Invoke-RestMethod -Uri "$ApiBase/process/processing_1" -Method POST -Headers @{'Content-Type'='application/json'} -Body ($job | ConvertTo-Json -Depth 10)
    Write-Host "✅ Processing request sent successfully" -ForegroundColor Green
    $result | ConvertTo-Json -Depth 10 | Write-Host
} catch {
    Write-Host "❌ Failed to send processing request: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`n🎉 Test completed!" -ForegroundColor Green
Write-Host "Attendere ~60 secondi per permettere al provisioning di completarsi..." -ForegroundColor Yellow
