# Quick configuration for algorithm testing
# Modify these values based on your environment

# AWS Configuration
$Region = "us-east-1"
$Account = "544547773663"
$AdminKey = "dev-admin"

# API Endpoints (will be populated after deployment)
$ApiBase = $env:API_BASE
$PacsApiBase = $env:PACS_API_BASE
$WsEndpoint = $env:WS_ENDPOINT

# Example algorithms to register
$ExampleAlgorithms = @(
    @{
        algo_id = "processing_1"
        image_uri = "$Account.dkr.ecr.$Region.amazonaws.com/mip-algos:processing_1"
        cpu = 1024
        memory = 2048
        desired_count = 1
        command = @("/app/worker.sh")
        env = @{
            EXTRA_DEBUG = "1"
        }
    },
    @{
        algo_id = "processing_6"
        image_uri = "$Account.dkr.ecr.$Region.amazonaws.com/mip-algos:processing_6"
        cpu = 1024
        memory = 2048
        desired_count = 1
        command = @("/app/worker.sh")
        env = @{}
    },
    @{
        algo_id = "grayscale_openmp"
        image_uri = "$Account.dkr.ecr.$Region.amazonaws.com/mip-algos:grayscale"
        cpu = 2048
        memory = 4096
        desired_count = 1
        command = @("/app/adapter.py")
        env = @{
            OMP_NUM_THREADS = "4"
            ALGORITHM_TYPE = "grayscale"
        }
    }
)

# Funzione helper per registrare un algoritmo
function Register-Algorithm {
    param(
        [hashtable] $AlgoSpec,
        [string] $ApiBase,
        [string] $AdminKey
    )
    
    $headers = @{
        'Content-Type' = 'application/json'
        'x-admin-key' = $AdminKey
    }
    
    try {
        $response = Invoke-RestMethod -Uri "$ApiBase/admin/algorithms" -Method POST -Headers $headers -Body ($AlgoSpec | ConvertTo-Json -Depth 10)
        Write-Host "✅ Registered $($AlgoSpec.algo_id)" -ForegroundColor Green
        return $response
    } catch {
        Write-Host "❌ Failed to register $($AlgoSpec.algo_id): $($_.Exception.Message)" -ForegroundColor Red
        return $null
    }
}

# Funzione helper per testare un algoritmo
function Test-Algorithm {
    param(
        [string] $AlgoId,
        [string] $ApiBase,
        [string] $ClientId = "test-client"
    )
    
    $testJob = @{
        job_id = "test-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
        client_id = $ClientId
        pacs = @{
            study_id = "test-study"
            series_id = "test-series"
            image_id = "test-image"
            scope = "image"
        }
    }
    
    try {
        $response = Invoke-RestMethod -Uri "$ApiBase/process/$AlgoId" -Method POST -Headers @{
            'Content-Type' = 'application/json'
        } -Body ($testJob | ConvertTo-Json -Depth 10)
        
        Write-Host "✅ Test job sent to $AlgoId" -ForegroundColor Green
        return $response
    } catch {
        Write-Host "❌ Failed to test $AlgoId: $($_.Exception.Message)" -ForegroundColor Red
        return $null
    }
}

# Export delle funzioni e variabili
Export-ModuleMember -Variable Region, Account, AdminKey, ApiBase, PacsApiBase, WsEndpoint, ExampleAlgorithms
Export-ModuleMember -Function Register-Algorithm, Test-Algorithm
