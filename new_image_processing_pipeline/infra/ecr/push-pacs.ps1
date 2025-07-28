# Script PowerShell per buildare, taggare e pushare l'immagine PACS API su ECR
param(
  [string] $Region = "eu-central-1",
  [string] $Account = "544547773663"
)

$repo = "$Account.dkr.ecr.$Region.amazonaws.com/pacs-ecr"

# Build
cd ..\..
cd new_image_processing_pipeline

docker build -t mip-pacs-api -f pacs_api/Dockerfile .

# Tag

docker tag mip-pacs-api $repo:latest

# Push

docker push $repo:latest

Write-Host "✅ PACS API ora in ECR sotto pacs-ecr"
