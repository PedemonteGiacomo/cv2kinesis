# Test script for algorithm administration APIs (with Cognito authentication)
param(
    [string] $ApiBase = $env:API_BASE,
    [string] $UserPoolId = $env:USER_POOL_ID,
    [string] $ClientId = $env:USER_POOL_CLIENT_ID,
    [string] $Username,
    [string] $Password
)

if (-not $ApiBase) {
    Write-Error "API_BASE variable not set. Run gen_env.ps1 first"
    exit 1
}

if (-not $UserPoolId -or -not $ClientId) {
    Write-Error "USER_POOL_ID e USER_POOL_CLIENT_ID devono essere impostati"
    exit 1
}

if (-not $Username -or -not $Password) {
    Write-Error "Username e Password sono richiesti per i test"
    Write-Host "Uso: .\test-admin-api.ps1 -Username 'user@example.com' -Password 'YourPassword123!'"
    exit 1
}

Write-Host "🧪 Testing Algorithm Administration API with Cognito Auth" -ForegroundColor Green
Write-Host "API Base: $ApiBase" -ForegroundColor Yellow
Write-Host "User Pool: $UserPoolId" -ForegroundColor Yellow
Write-Host "Username: $Username" -ForegroundColor Yellow
Write-Host

# Function to authenticate with Cognito and get token
function Get-CognitoToken {
    param(
        [string] $Username,
        [string] $Password
    )
    
    try {
        Write-Host "Authenticating with Cognito..." -ForegroundColor Cyan
        
        $authResult = aws cognito-idp initiate-auth `
            --auth-flow USER_PASSWORD_AUTH `
            --client-id $ClientId `
            --auth-parameters "USERNAME=$Username,PASSWORD=$Password" `
            --query 'AuthenticationResult.AccessToken' `
            --output text
            
        if ($LASTEXITCODE -ne 0 -or $authResult -eq "None") {
            throw "Authentication failed"
        }
        
        Write-Host "Authentication successful!" -ForegroundColor Green
        return $authResult
    }
    catch {
        Write-Error "Failed to authenticate: $_"
        throw
    }
}

# Function per invocare API with JWT token
function Invoke-AdminApi {
    param(
        [string] $Method,
        [string] $Path,
        [string] $Token,
        [object] $Body = $null,
        [string] $QueryString = ""
    )
    
    $headers = @{
        'Content-Type' = 'application/json'
        'Authorization' = "Bearer $Token"
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

try {
    # Get authentication token
    $accessToken = Get-CognitoToken -Username $Username -Password $Password
    
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

$result = Invoke-AdminApi -Method POST -Path "/admin/algorithms" -Token $accessToken -Body $algo1
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

$result = Invoke-AdminApi -Method POST -Path "/admin/algorithms" -Token $accessToken -Body $algo2
if ($result) {
    Write-Host "✅ Algorithm registered successfully" -ForegroundColor Green
    $result | ConvertTo-Json -Depth 10 | Write-Host
} else {
    Write-Host "❌ Failed to register algorithm" -ForegroundColor Red
}

Start-Sleep -Seconds 5

Write-Host "`n3. 📋 Listing all algorithms..." -ForegroundColor Cyan
$result = Invoke-AdminApi -Method GET -Path "/admin/algorithms" -Token $accessToken
if ($result) {
    Write-Host "✅ Algorithms listed successfully" -ForegroundColor Green
    $result | ConvertTo-Json -Depth 10 | Write-Host
} else {
    Write-Host "❌ Failed to list algorithms" -ForegroundColor Red
}

Write-Host "`n4. 🔍 Getting specific algorithm details..." -ForegroundColor Cyan
$result = Invoke-AdminApi -Method GET -Path "/admin/algorithms/processing_1" -Token $accessToken
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

$result = Invoke-AdminApi -Method PATCH -Path "/admin/algorithms/processing_1" -Token $accessToken -Body $update
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

} catch {
    Write-Error "Test execution failed: $_"
    exit 1
}
Write-Host "`n🎉 Test completed!" -ForegroundColor Green
Write-Host "Attendere ~60 secondi per permettere al provisioning di completarsi..." -ForegroundColor Yellow
