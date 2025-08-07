# PowerShell script to create ECR repositories
param(
  [string] $Region = "us-east-1",
  [string] $Account = "544547773663"
)

aws ecr create-repository --repository-name mip-algos --image-scanning-configuration scanOnPush=true --region $Region
aws ecr create-repository --repository-name pacs-ecr --image-scanning-configuration scanOnPush=true --region $Region
aws ecr create-repository --repository-name mip-admin-portal --image-scanning-configuration scanOnPush=true --region $Region

Write-Host "✅ Repository mip-algos, pacs-ecr e mip-admin-portal creati. Annota gli URI restituiti da AWS."
