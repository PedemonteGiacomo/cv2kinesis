# Script per build e push dell'algoritmo grayscale
param(
    [string] $Region = "us-east-1",
    [string] $Account = "544547773663",
    [string] $Tag = "grayscale"
)

$ErrorActionPreference = "Stop"

Write-Host "🔨 Building and pushing grayscale algorithm" -ForegroundColor Green
Write-Host "Region: $Region, Account: $Account, Tag: $Tag" -ForegroundColor Yellow

# Torna alla root del progetto
Push-Location (Join-Path $PSScriptRoot "..")

try {
    $repo = "$Account.dkr.ecr.$Region.amazonaws.com/mip-algos"
    
    Write-Host "`n📦 Building grayscale container..." -ForegroundColor Cyan
    docker build -t "mip-grayscale:latest" -f "containers/grayscale/Dockerfile" .
    if ($LASTEXITCODE -ne 0) { throw "Docker build failed" }
    
    Write-Host "`n🏷️ Tagging for ECR..." -ForegroundColor Cyan
    docker tag "mip-grayscale:latest" "${repo}:${Tag}"
    if ($LASTEXITCODE -ne 0) { throw "Docker tag failed" }
    
    Write-Host "`n🔐 Authenticating to ECR..." -ForegroundColor Cyan
    aws ecr get-login-password --region $Region | docker login --username AWS --password-stdin "$Account.dkr.ecr.$Region.amazonaws.com"
    if ($LASTEXITCODE -ne 0) { throw "ECR authentication failed" }
    
    Write-Host "`n📤 Pushing to ECR..." -ForegroundColor Cyan
    docker push "${repo}:${Tag}"
    if ($LASTEXITCODE -ne 0) { throw "Docker push failed" }
    
    Write-Host "`n✅ Grayscale algorithm pushed successfully!" -ForegroundColor Green
    Write-Host "Image URI: ${repo}:${Tag}" -ForegroundColor Yellow
    
    Write-Host "`n📋 Next steps:" -ForegroundColor Cyan
    Write-Host "1. Register the algorithm via Admin API:" -ForegroundColor White
    Write-Host @"
curl -X POST "$env:API_BASE/admin/algorithms" \
  -H "Content-Type: application/json" \
  -H "x-admin-key: dev-admin" \
  -d '{
    "algo_id": "grayscale",
    "image_uri": "${repo}:${Tag}",
    "cpu": 2048,
    "memory": 4096,
    "command": ["/app/adapter.py"],
    "env": {
      "OMP_NUM_THREADS": "4",
      "GRAYSCALE_PASSES": "1"
    }
  }'
"@ -ForegroundColor Gray

} catch {
    Write-Host "`n❌ Error: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
} finally {
    Pop-Location
}
