# Script PowerShell per buildare, taggare e pushare le immagini processing_1 e processing_6 su ECR
param(
  [string] $Region = "eu-central-1",
  [string] $Account = "544547773663"
)

$repo = "$Account.dkr.ecr.$Region.amazonaws.com/mip-algos"

# Build delle immagini
cd ..\..
cd new_image_processing_pipeline

docker build -t mip-processing_1 -f containers/processing_1/Dockerfile .
docker build -t mip-processing_6 -f containers/processing_6/Dockerfile .

# Tag

docker tag mip-processing_1 $repo:processing_1
docker tag mip-processing_6 $repo:processing_6

# Push

docker push $repo:processing_1
docker push $repo:processing_6

Write-Host "✅ processing_1 e processing_6 ora in ECR sotto mip-algos"
