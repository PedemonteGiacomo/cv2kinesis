param(
  [string] $Region  = "us-east-1",
  [string] $Account = "544547773663"
)

$repo = "$Account.dkr.ecr.$Region.amazonaws.com/pacs-ecr"

# Spostati nella root del progetto e poi nella cartella pacs_api
Push-Location (Join-Path $PSScriptRoot "..\..")
Push-Location "pacs_api"

# Build dell’immagine PACS API
docker build -t mip-pacs-api .

# Tag per ECR
docker tag mip-pacs-api "${repo}:latest"

# Autenticazione a ECR
aws ecr get-login-password --region $Region |
  docker login --username AWS --password-stdin "$Account.dkr.ecr.$Region.amazonaws.com"

# Push su ECR
docker push "${repo}:latest"

Write-Host "✅ PACS API ora in ECR sotto pacs-ecr ($Region)"

# Torna alla cartella originale
Pop-Location
Pop-Location
