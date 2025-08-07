# Complete management of MIP architecture post-deployment
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("list-algorithms", "register-algorithm", "update-algorithm", "delete-algorithm", 
                 "list-jobs", "check-health", "logs", "scale", "cleanup", "backup", "restore")]
    [string] $Action,
    
    [string] $AlgorithmName,
    [string] $AlgorithmPath,
    [string] $JobId,
    [string] $AdminKey,
    [int] $DesiredCount = 1,
    [string] $LogGroup,
    [int] $Hours = 1,
    [switch] $Force,
    [switch] $Verbose
)

$ErrorActionPreference = "Stop"

# Get stack outputs
$global:StackOutputs = $null

function Get-StackOutputs {
    if ($null -eq $global:StackOutputs) {
        try {
            $stacks = @("ImgPipeline", "PacsApi")
            $global:StackOutputs = @{}
            
            foreach ($stackName in $stacks) {
                $outputs = aws cloudformation describe-stacks --stack-name $stackName --query "Stacks[0].Outputs" --output json | ConvertFrom-Json
                foreach ($output in $outputs) {
                    $global:StackOutputs[$output.OutputKey] = $output.OutputValue
                }
            }
        } catch {
            Write-Warning "Could not retrieve stack outputs: $($_.Exception.Message)"
            $global:StackOutputs = @{}
        }
    }
    return $global:StackOutputs
}

function Write-Status {
    param([string]$Message, [string]$Type = "INFO")
    
    $color = switch ($Type) {
        "SUCCESS" { "Green" }
        "ERROR" { "Red" }
        "WARNING" { "Yellow" }
        "INFO" { "Cyan" }
    }
    
    $prefix = switch ($Type) {
        "SUCCESS" { "✅" }
        "ERROR" { "❌" }
        "WARNING" { "⚠️" }
        "INFO" { "ℹ️" }
    }
    
    Write-Host "$prefix $Message" -ForegroundColor $color
}

function Invoke-ApiCall {
    param(
        [string]$Endpoint,
        [string]$Method = "GET",
        [hashtable]$Headers = @{},
        [object]$Body = $null,
        [string]$Description = ""
    )
    
    if ($Description) {
        Write-Status "API Call: $Description" "INFO"
    }
    
    try {
        $params = @{
            Uri = $Endpoint
            Method = $Method
            Headers = $Headers
            ContentType = "application/json"
        }
        
        if ($Body) {
            $params.Body = ($Body | ConvertTo-Json -Depth 10)
        }
        
        $response = Invoke-RestMethod @params
        
        if ($Verbose) {
            Write-Host "Response:" -ForegroundColor Gray
            $response | ConvertTo-Json -Depth 5 | Write-Host -ForegroundColor Gray
        }
        
        return $response
    } catch {
        Write-Status "API call failed: $($_.Exception.Message)" "ERROR"
        if ($_.Exception.Response) {
            $stream = $_.Exception.Response.GetResponseStream()
            $reader = [System.IO.StreamReader]::new($stream)
            $errorBody = $reader.ReadToEnd()
            Write-Host "Error details: $errorBody" -ForegroundColor Red
        }
        throw
    }
}

function Get-AdminKey {
    if ($AdminKey) {
        return $AdminKey
    }
    
    # Try to get from environment
    $envKey = $env:MIP_ADMIN_KEY
    if ($envKey) {
        return $envKey
    }
    
    # Try to get from parameter store
    try {
        $paramName = "/mip/admin/key"
        $adminKey = aws ssm get-parameter --name $paramName --with-decryption --query "Parameter.Value" --output text 2>$null
        if ($adminKey -and $adminKey -ne "None") {
            return $adminKey
        }
    } catch {
        # Ignore
    }
    
    Write-Status "Admin key not found. Set MIP_ADMIN_KEY environment variable or use -AdminKey parameter" "WARNING"
    return $null
}

function Action-ListAlgorithms {
    Write-Host "📋 Listing registered algorithms..." -ForegroundColor Cyan
    
    $outputs = Get-StackOutputs
    $adminEndpoint = $outputs["AdminApiEndpoint"]
    
    if (-not $adminEndpoint) {
        Write-Status "Admin API endpoint not found" "ERROR"
        return
    }
    
    try {
        $algorithms = Invoke-ApiCall "$adminEndpoint/algorithms" "GET" @{} $null "Fetching algorithms"
        
        if ($algorithms) {
            Write-Host "`nRegistered Algorithms:" -ForegroundColor Green
            foreach ($algo in $algorithms) {
                Write-Host "  📦 $($algo.name)" -ForegroundColor White
                Write-Host "     Status: $($algo.status)" -ForegroundColor Gray
                Write-Host "     Image: $($algo.image_uri)" -ForegroundColor Gray
                Write-Host "     Type: $($algo.algorithm_type)" -ForegroundColor Gray
                if ($algo.description) {
                    Write-Host "     Description: $($algo.description)" -ForegroundColor Gray
                }
                Write-Host ""
            }
        } else {
            Write-Status "No algorithms registered" "INFO"
        }
    } catch {
        Write-Status "Failed to list algorithms" "ERROR"
    }
}

function Action-RegisterAlgorithm {
    if (-not $AlgorithmName -or -not $AlgorithmPath) {
        Write-Status "Algorithm name and path required for registration" "ERROR"
        return
    }
    
    $adminKey = Get-AdminKey
    if (-not $adminKey) {
        return
    }
    
    Write-Host "📝 Registering algorithm: $AlgorithmName" -ForegroundColor Cyan
    
    $outputs = Get-StackOutputs
    $adminEndpoint = $outputs["AdminApiEndpoint"]
    
    if (-not $adminEndpoint) {
        Write-Status "Admin API endpoint not found" "ERROR"
        return
    }
    
    # Read algorithm metadata
    $metadataFile = Join-Path $AlgorithmPath "metadata.json"
    if (-not (Test-Path $metadataFile)) {
        Write-Status "metadata.json not found in algorithm path" "ERROR"
        return
    }
    
    try {
        $metadata = Get-Content $metadataFile | ConvertFrom-Json
        
        # Determine image URI (from ECR)
        $accountId = aws sts get-caller-identity --query Account --output text
        $region = aws configure get region
        if (-not $region) { $region = "us-east-1" }
        
        $imageUri = "$accountId.dkr.ecr.$region.amazonaws.com/mip-$AlgorithmName" + ":latest"
        
        $requestBody = @{
            name = $AlgorithmName
            image_uri = $imageUri
            algorithm_type = $metadata.algorithm_type
            description = $metadata.description
            cpu = $metadata.cpu
            memory = $metadata.memory
            parameters = $metadata.parameters
        }
        
        $headers = @{ "x-admin-key" = $adminKey }
        
        $result = Invoke-ApiCall "$adminEndpoint/algorithms" "POST" $headers $requestBody "Registering algorithm"
        
        Write-Status "Algorithm registered successfully" "SUCCESS"
        Write-Host "Algorithm ID: $($result.id)" -ForegroundColor Green
        
    } catch {
        Write-Status "Failed to register algorithm" "ERROR"
    }
}

function Action-UpdateAlgorithm {
    if (-not $AlgorithmName) {
        Write-Status "Algorithm name required for update" "ERROR"
        return
    }
    
    $adminKey = Get-AdminKey
    if (-not $adminKey) {
        return
    }
    
    Write-Host "🔄 Updating algorithm: $AlgorithmName" -ForegroundColor Cyan
    
    $outputs = Get-StackOutputs
    $adminEndpoint = $outputs["AdminApiEndpoint"]
    
    if (-not $adminEndpoint) {
        Write-Status "Admin API endpoint not found" "ERROR"
        return
    }
    
    try {
        $updateBody = @{
            status = "active"
        }
        
        if ($AlgorithmPath) {
            $metadataFile = Join-Path $AlgorithmPath "metadata.json"
            if (Test-Path $metadataFile) {
                $metadata = Get-Content $metadataFile | ConvertFrom-Json
                $updateBody.description = $metadata.description
                $updateBody.cpu = $metadata.cpu
                $updateBody.memory = $metadata.memory
                $updateBody.parameters = $metadata.parameters
            }
        }
        
        $headers = @{ "x-admin-key" = $adminKey }
        
        $result = Invoke-ApiCall "$adminEndpoint/algorithms/$AlgorithmName" "PATCH" $headers $updateBody "Updating algorithm"
        
        Write-Status "Algorithm updated successfully" "SUCCESS"
        
    } catch {
        Write-Status "Failed to update algorithm" "ERROR"
    }
}

function Action-DeleteAlgorithm {
    if (-not $AlgorithmName) {
        Write-Status "Algorithm name required for deletion" "ERROR"
        return
    }
    
    if (-not $Force) {
        $confirm = Read-Host "Are you sure you want to delete algorithm '$AlgorithmName'? (y/N)"
        if ($confirm -ne "y" -and $confirm -ne "Y") {
            Write-Status "Deletion cancelled" "INFO"
            return
        }
    }
    
    $adminKey = Get-AdminKey
    if (-not $adminKey) {
        return
    }
    
    Write-Host "🗑️ Deleting algorithm: $AlgorithmName" -ForegroundColor Cyan
    
    $outputs = Get-StackOutputs
    $adminEndpoint = $outputs["AdminApiEndpoint"]
    
    if (-not $adminEndpoint) {
        Write-Status "Admin API endpoint not found" "ERROR"
        return
    }
    
    try {
        $headers = @{ "x-admin-key" = $adminKey }
        
        Invoke-ApiCall "$adminEndpoint/algorithms/$AlgorithmName" "DELETE" $headers $null "Deleting algorithm"
        
        Write-Status "Algorithm deleted successfully" "SUCCESS"
        
    } catch {
        Write-Status "Failed to delete algorithm" "ERROR"
    }
}

function Action-CheckHealth {
    Write-Host "🏥 Checking system health..." -ForegroundColor Cyan
    
    $outputs = Get-StackOutputs
    
    # Check Processing API
    $processingEndpoint = $outputs["ProcessingApiEndpoint"]
    if ($processingEndpoint) {
        try {
            $health = Invoke-ApiCall "$processingEndpoint/health" "GET" @{} $null "Processing API health"
            Write-Status "Processing API: Healthy" "SUCCESS"
        } catch {
            Write-Status "Processing API: Unhealthy" "ERROR"
        }
    }
    
    # Check Admin API
    $adminEndpoint = $outputs["AdminApiEndpoint"]
    if ($adminEndpoint) {
        try {
            $health = Invoke-ApiCall "$adminEndpoint/health" "GET" @{} $null "Admin API health"
            Write-Status "Admin API: Healthy" "SUCCESS"
        } catch {
            Write-Status "Admin API: Unhealthy" "ERROR"
        }
    }
    
    # Check ECS cluster
    try {
        $clusterName = "mip-cluster"
        $cluster = aws ecs describe-clusters --clusters $clusterName --output json | ConvertFrom-Json
        $clusterInfo = $cluster.clusters[0]
        
        Write-Status "ECS Cluster: $($clusterInfo.status)" "SUCCESS"
        Write-Host "  Active services: $($clusterInfo.activeServicesCount)" -ForegroundColor Gray
        Write-Host "  Running tasks: $($clusterInfo.runningTasksCount)" -ForegroundColor Gray
        
    } catch {
        Write-Status "ECS Cluster: Error checking status" "ERROR"
    }
    
    # Check DynamoDB table
    try {
        $tableName = "mip-algorithms"
        $table = aws dynamodb describe-table --table-name $tableName --output json | ConvertFrom-Json
        Write-Status "DynamoDB Table: $($table.Table.TableStatus)" "SUCCESS"
        
    } catch {
        Write-Status "DynamoDB Table: Error checking status" "ERROR"
    }
}

function Action-ViewLogs {
    Write-Host "📊 Viewing system logs..." -ForegroundColor Cyan
    
    if ($LogGroup) {
        $logGroups = @($LogGroup)
    } else {
        $logGroups = @(
            "/aws/lambda/mip-algos-admin",
            "/aws/lambda/mip-provisioner", 
            "/aws/lambda/mip-dynamic-router",
            "/ecs/mip-algorithms"
        )
    }
    
    $endTime = Get-Date
    $startTime = $endTime.AddHours(-$Hours)
    
    foreach ($group in $logGroups) {
        Write-Host "`n📋 Log Group: $group" -ForegroundColor Yellow
        
        try {
            $startMillis = [Math]::Floor(($startTime.ToUniversalTime() - [datetime]'1970-01-01').TotalMilliseconds)
            $endMillis = [Math]::Floor(($endTime.ToUniversalTime() - [datetime]'1970-01-01').TotalMilliseconds)
            
            $events = aws logs filter-log-events --log-group-name $group --start-time $startMillis --end-time $endMillis --output json | ConvertFrom-Json
            
            foreach ($event in $events.events) {
                $timestamp = [DateTimeOffset]::FromUnixTimeMilliseconds($event.timestamp).ToString("yyyy-MM-dd HH:mm:ss")
                Write-Host "[$timestamp] $($event.message)" -ForegroundColor White
            }
            
            if (-not $events.events) {
                Write-Status "No recent log events found" "INFO"
            }
            
        } catch {
            Write-Status "Could not retrieve logs for $group" "WARNING"
        }
    }
}

function Action-Scale {
    if (-not $AlgorithmName) {
        Write-Status "Algorithm name required for scaling" "ERROR"
        return
    }
    
    Write-Host "⚖️ Scaling algorithm: $AlgorithmName to $DesiredCount instances" -ForegroundColor Cyan
    
    try {
        $serviceName = "mip-$AlgorithmName"
        $clusterName = "mip-cluster"
        
        aws ecs update-service --cluster $clusterName --service $serviceName --desired-count $DesiredCount | Out-Null
        
        Write-Status "Scaling initiated successfully" "SUCCESS"
        Write-Host "Current status:" -ForegroundColor Gray
        
        $service = aws ecs describe-services --cluster $clusterName --services $serviceName --output json | ConvertFrom-Json
        $serviceInfo = $service.services[0]
        
        Write-Host "  Running: $($serviceInfo.runningCount)" -ForegroundColor White
        Write-Host "  Pending: $($serviceInfo.pendingCount)" -ForegroundColor White
        Write-Host "  Desired: $($serviceInfo.desiredCount)" -ForegroundColor White
        
    } catch {
        Write-Status "Failed to scale service" "ERROR"
    }
}

function Action-Cleanup {
    Write-Host "🧹 Cleaning up unused resources..." -ForegroundColor Cyan
    
    if (-not $Force) {
        $confirm = Read-Host "This will clean up stopped tasks and unused images. Continue? (y/N)"
        if ($confirm -ne "y" -and $confirm -ne "Y") {
            Write-Status "Cleanup cancelled" "INFO"
            return
        }
    }
    
    try {
        # Clean up stopped ECS tasks
        Write-Status "Cleaning stopped ECS tasks..." "INFO"
        $stoppedTasks = aws ecs list-tasks --cluster mip-cluster --desired-status STOPPED --output json | ConvertFrom-Json
        
        foreach ($task in $stoppedTasks.taskArns) {
            aws ecs stop-task --cluster mip-cluster --task $task 2>$null
        }
        
        # Clean up old CloudWatch logs (older than 30 days)
        Write-Status "Cleaning old log streams..." "INFO"
        $logGroups = aws logs describe-log-groups --log-group-name-prefix "/ecs/mip" --output json | ConvertFrom-Json
        
        foreach ($group in $logGroups.logGroups) {
            $retentionDays = 30
            aws logs put-retention-policy --log-group-name $group.logGroupName --retention-in-days $retentionDays 2>$null
        }
        
        Write-Status "Cleanup completed" "SUCCESS"
        
    } catch {
        Write-Status "Cleanup failed" "ERROR"
    }
}

# Main action dispatcher
switch ($Action) {
    "list-algorithms" { Action-ListAlgorithms }
    "register-algorithm" { Action-RegisterAlgorithm }
    "update-algorithm" { Action-UpdateAlgorithm }
    "delete-algorithm" { Action-DeleteAlgorithm }
    "check-health" { Action-CheckHealth }
    "logs" { Action-ViewLogs }
    "scale" { Action-Scale }
    "cleanup" { Action-Cleanup }
    default {
        Write-Status "Unknown action: $Action" "ERROR"
        exit 1
    }
}
