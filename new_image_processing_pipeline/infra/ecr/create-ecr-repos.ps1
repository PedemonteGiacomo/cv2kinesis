# Script PowerShell per creare i repository ECR
param(
  [string] $Region = "eu-central-1",
  [string] $Account = "544547773663"
)

aws ecr create-repository --repository-name mip-algos --image-scanning-configuration scanOnPush=true --region $Region
aws ecr create-repository --repository-name pacs-ecr --image-scanning-configuration scanOnPush=true --region $Region

Write-Host "✅ Repository mip-algos e pacs-ecr creati. Annota gli URI restituiti da AWS."
