# Validation script for MIP algorithms
param(
    [Parameter(Mandatory=$true)]
    [string] $AlgorithmPath,
    
    [switch] $Fix,
    [switch] $Verbose
)

$ErrorActionPreference = "Stop"

function Write-Check {
    param([string]$Message, [string]$Status, [string]$Details = "")
    
    $color = switch ($Status) {
        "OK" { "Green" }
        "WARNING" { "Yellow" }
        "ERROR" { "Red" }
        "INFO" { "Cyan" }
    }
    
    $symbol = switch ($Status) {
        "OK" { "✅" }
        "WARNING" { "⚠️" }
        "ERROR" { "❌" }
        "INFO" { "ℹ️" }
    }
    
    Write-Host "$symbol $Message" -ForegroundColor $color
    if ($Details -and $Verbose) {
        Write-Host "   $Details" -ForegroundColor Gray
    }
}

function Test-AlgorithmStructure {
    param([string]$Path)
    
    Write-Host "`n🔍 Validating algorithm structure..." -ForegroundColor Cyan
    
    # Check if directory exists
    if (-not (Test-Path $Path)) {
        Write-Check "Algorithm directory exists" "ERROR" "Path not found: $Path"
        return $false
    }
    
    Write-Check "Algorithm directory exists" "OK"
    
    # Check required files
    $dockerfile = Join-Path $Path "Dockerfile"
    if (-not (Test-Path $dockerfile)) {
        Write-Check "Dockerfile exists" "ERROR" "Missing Dockerfile"
        return $false
    }
    Write-Check "Dockerfile exists" "OK"
    
    # Check README
    $readme = Join-Path $Path "README.md"
    if (-not (Test-Path $readme)) {
        Write-Check "README.md exists" "WARNING" "README.md recommended for documentation"
    } else {
        Write-Check "README.md exists" "OK"
    }
    
    # Detect algorithm type
    $isOpenMP = Test-Path (Join-Path $Path "adapter.py")
    $isPython = Test-Path (Join-Path $Path "algorithm.py")
    
    if ($isOpenMP) {
        Write-Check "Algorithm type: OpenMP" "INFO"
        return Test-OpenMPStructure $Path
    } elseif ($isPython) {
        Write-Check "Algorithm type: Python" "INFO"
        return Test-PythonStructure $Path
    } else {
        Write-Check "Algorithm type detection" "ERROR" "Could not detect algorithm type (missing adapter.py or algorithm.py)"
        return $false
    }
}

function Test-OpenMPStructure {
    param([string]$Path)
    
    Write-Host "`n⚡ Validating OpenMP algorithm..." -ForegroundColor Cyan
    
    # Check adapter.py
    $adapter = Join-Path $Path "adapter.py"
    if (-not (Test-Path $adapter)) {
        Write-Check "adapter.py exists" "ERROR"
        return $false
    }
    Write-Check "adapter.py exists" "OK"
    
    # Check if adapter is executable
    try {
        $content = Get-Content $adapter -Raw
        if ($content -match "#!/usr/bin/env python3") {
            Write-Check "adapter.py has shebang" "OK"
        } else {
            Write-Check "adapter.py has shebang" "WARNING" "Missing #!/usr/bin/env python3"
        }
    } catch {
        Write-Check "adapter.py readable" "ERROR" $_.Exception.Message
        return $false
    }
    
    # Check source directory
    $srcDir = Join-Path $Path "src"
    if (-not (Test-Path $srcDir)) {
        Write-Check "src/ directory exists" "ERROR"
        return $false
    }
    Write-Check "src/ directory exists" "OK"
    
    # Check Makefile
    $makefile = Join-Path $srcDir "Makefile"
    if (-not (Test-Path $makefile)) {
        Write-Check "src/Makefile exists" "ERROR"
        return $false
    }
    Write-Check "src/Makefile exists" "OK"
    
    # Check main.c
    $mainC = Join-Path $srcDir "main.c"
    if (-not (Test-Path $mainC)) {
        Write-Check "src/main.c exists" "ERROR"
        return $false
    }
    Write-Check "src/main.c exists" "OK"
    
    # Check requirements.txt
    $requirements = Join-Path $Path "requirements.txt"
    if (-not (Test-Path $requirements)) {
        Write-Check "requirements.txt exists" "WARNING" "Recommended for Python dependencies"
    } else {
        Write-Check "requirements.txt exists" "OK"
    }
    
    return $true
}

function Test-PythonStructure {
    param([string]$Path)
    
    Write-Host "`n🐍 Validating Python algorithm..." -ForegroundColor Cyan
    
    # Check algorithm.py
    $algorithm = Join-Path $Path "algorithm.py"
    if (-not (Test-Path $algorithm)) {
        Write-Check "algorithm.py exists" "ERROR"
        return $false
    }
    Write-Check "algorithm.py exists" "OK"
    
    # Check algorithm class
    try {
        $content = Get-Content $algorithm -Raw
        if ($content -match "class \w+Processor\(BaseProcessor\)") {
            Write-Check "Algorithm class extends BaseProcessor" "OK"
        } else {
            Write-Check "Algorithm class extends BaseProcessor" "WARNING" "Should extend BaseProcessor"
        }
        
        if ($content -match "def process_image\(") {
            Write-Check "process_image method exists" "OK"
        } else {
            Write-Check "process_image method exists" "ERROR" "Missing required process_image method"
            return $false
        }
    } catch {
        Write-Check "algorithm.py readable" "ERROR" $_.Exception.Message
        return $false
    }
    
    return $true
}

function Test-DockerFile {
    param([string]$Path)
    
    Write-Host "`n🐳 Validating Dockerfile..." -ForegroundColor Cyan
    
    $dockerfile = Join-Path $Path "Dockerfile"
    $content = Get-Content $dockerfile -Raw
    
    # Check base image
    if ($content -match "FROM python:") {
        Write-Check "Uses Python base image" "OK"
    } elseif ($content -match "FROM.*mip-base") {
        Write-Check "Uses MIP base image" "OK"
    } else {
        Write-Check "Base image" "WARNING" "Consider using python:3.11-slim or mip-base"
    }
    
    # Check for AWS CLI
    if ($content -match "aws.*cli") {
        Write-Check "Includes AWS CLI" "OK"
    } else {
        Write-Check "Includes AWS CLI" "WARNING" "AWS CLI recommended for S3 operations"
    }
    
    # Check for OpenMP (if needed)
    if ($content -match "libgomp") {
        Write-Check "Includes OpenMP support" "OK"
    }
    
    # Check ENTRYPOINT/CMD
    if ($content -match "(ENTRYPOINT|CMD)") {
        Write-Check "Has ENTRYPOINT or CMD" "OK"
    } else {
        Write-Check "Has ENTRYPOINT or CMD" "ERROR" "Missing ENTRYPOINT or CMD"
        return $false
    }
    
    return $true
}

function Test-BuildAbility {
    param([string]$Path)
    
    Write-Host "`n🔨 Testing Docker build..." -ForegroundColor Cyan
    
    $algoName = Split-Path $Path -Leaf
    
    try {
        Push-Location $Path
        
        Write-Host "Building container (this may take a while)..." -ForegroundColor Yellow
        $buildOutput = docker build -t "test-$algoName" . 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            Write-Check "Docker build successful" "OK"
            
            # Cleanup test image
            docker rmi "test-$algoName" -f 2>&1 | Out-Null
            return $true
        } else {
            Write-Check "Docker build failed" "ERROR" "See output above"
            if ($Verbose) {
                Write-Host $buildOutput -ForegroundColor Red
            }
            return $false
        }
    } catch {
        Write-Check "Docker build test" "ERROR" $_.Exception.Message
        return $false
    } finally {
        Pop-Location
    }
}

function Test-SecurityBestPractices {
    param([string]$Path)
    
    Write-Host "`n🔒 Checking security best practices..." -ForegroundColor Cyan
    
    $dockerfile = Join-Path $Path "Dockerfile"
    $content = Get-Content $dockerfile -Raw
    
    # Check for apt cleanup
    if ($content -match "rm -rf /var/lib/apt/lists") {
        Write-Check "Cleans apt cache" "OK"
    } else {
        Write-Check "Cleans apt cache" "WARNING" "Add 'rm -rf /var/lib/apt/lists/*' after apt-get install"
    }
    
    # Check for non-root user (optional but recommended)
    if ($content -match "USER \w+") {
        Write-Check "Uses non-root user" "OK"
    } else {
        Write-Check "Uses non-root user" "INFO" "Consider adding non-root user for security"
    }
    
    # Check for secrets in code
    $allFiles = Get-ChildItem $Path -Recurse -File | Where-Object { $_.Extension -in @('.py', '.c', '.cpp', '.h') }
    $hasSecrets = $false
    
    foreach ($file in $allFiles) {
        $content = Get-Content $file.FullName -Raw -ErrorAction SilentlyContinue
        if ($content -match "(password|secret|key|token)\s*=\s*['\"][^'\"]+['\"]") {
            Write-Check "No hardcoded secrets" "WARNING" "Potential secret found in $($file.Name)"
            $hasSecrets = $true
        }
    }
    
    if (-not $hasSecrets) {
        Write-Check "No hardcoded secrets" "OK"
    }
}

function Fix-CommonIssues {
    param([string]$Path)
    
    Write-Host "`n🔧 Attempting to fix common issues..." -ForegroundColor Cyan
    
    # Fix adapter.py permissions
    $adapter = Join-Path $Path "adapter.py"
    if (Test-Path $adapter) {
        $content = Get-Content $adapter -Raw
        if (-not ($content -match "#!/usr/bin/env python3")) {
            $newContent = "#!/usr/bin/env python3`n" + $content
            Set-Content $adapter -Value $newContent
            Write-Check "Added shebang to adapter.py" "OK"
        }
    }
    
    # Create README if missing
    $readme = Join-Path $Path "README.md"
    if (-not (Test-Path $readme)) {
        $algoName = Split-Path $Path -Leaf
        $readmeContent = @"
# $algoName Algorithm

Auto-generated README for $algoName algorithm.

## Quick Start

``````bash
# Build container
docker build -t $algoName .

# Deploy to MIP
.\deploy.ps1

# Test algorithm
curl -X POST "`$API_BASE/process/$algoName" \
  -H "Content-Type: application/json" \
  -d '{"job_id":"test","client_id":"test-client","pacs":{...}}'
``````

## Development

TODO: Add development instructions

## Parameters

TODO: Document algorithm parameters
"@
        Set-Content $readme -Value $readmeContent
        Write-Check "Created README.md" "OK"
    }
}

# Main validation
Write-Host "🔍 Algorithm Validation Tool" -ForegroundColor Green
Write-Host "Validating: $AlgorithmPath" -ForegroundColor Yellow

$algoName = Split-Path $AlgorithmPath -Leaf
$allPassed = $true

# Run validations
$allPassed = (Test-AlgorithmStructure $AlgorithmPath) -and $allPassed
$allPassed = (Test-DockerFile $AlgorithmPath) -and $allPassed

# Security check
Test-SecurityBestPractices $AlgorithmPath

# Build test (optional, can be slow)
if ($env:VALIDATE_BUILD -eq "true") {
    $allPassed = (Test-BuildAbility $AlgorithmPath) -and $allPassed
}

# Fix issues if requested
if ($Fix) {
    Fix-CommonIssues $AlgorithmPath
}

# Summary
Write-Host "`n📊 Validation Summary" -ForegroundColor Cyan
if ($allPassed) {
    Write-Host "✅ Algorithm $algoName passed validation!" -ForegroundColor Green
    Write-Host "Ready for deployment." -ForegroundColor White
} else {
    Write-Host "❌ Algorithm $algoName has validation issues." -ForegroundColor Red
    Write-Host "Please fix the issues above before deployment." -ForegroundColor White
    exit 1
}

Write-Host "`nNext steps:" -ForegroundColor Yellow
Write-Host "1. cd `"$AlgorithmPath`"" -ForegroundColor White
Write-Host "2. .\deploy.ps1" -ForegroundColor White
