param(
  [string] $Region  = "eu-central-1",
  [string] $Account = "544547773663"
)

$repo = "$Account.dkr.ecr.$Region.amazonaws.com/mip-algos"

# Return to project root
Push-Location (Join-Path $PSScriptRoot "..\..")

# Rebuild the images
docker build -t mip-base:latest             -f containers/base/Dockerfile .
docker build -t mip-processing_1             -f containers/processing_1/Dockerfile .
docker build -t mip-processing_6             -f containers/processing_6/Dockerfile .

# Tag utile per ECR
docker tag mip-processing_1 "${repo}:processing_1"
docker tag mip-processing_6 "${repo}:processing_6"

# Autenticazione a ECR
aws ecr get-login-password --region $Region |
  docker login --username AWS --password-stdin "$Account.dkr.ecr.$Region.amazonaws.com"

# Push su ECR
docker push "${repo}:processing_1"
docker push "${repo}:processing_6"

Write-Host "✅ processing_1 e processing_6 ora in ECR sotto mip-algos ($Region)"

# Ritorna nella cartella originale
Pop-Location
