<#
.PARAMETER AgentArn   ➜ quello mostrato in console DataSync dopo l'attivazione
.PARAMETER Region     default 'eu-central-1'
.PARAMETER Schedule   es. 'rate(1 minute)'
#>

param(
    [Parameter(Mandatory)][string]$AgentArn,
    [string]$Region   = "eu-central-1",
    [string]$Schedule = "rate(1 minute)"
)

$ErrorActionPreference = 'Stop'
$bucket = (aws s3api list-buckets --query "Buckets[?contains(Name, 'images-input')].Name"| ConvertFrom-Json)[0]
if (-not $bucket) { throw "Bucket images-input-… non trovato." }

Write-Host "`n🍿️  Bucket S3 di destinazione: $bucket"

# 1) crea LOCATION NFS (source)
$srcLocArn = aws datasync create-location-nfs `
  --server-hostname 127.0.0.1 `
  --subdirectory /data `
  --on-prem-config "AgentArns=[$AgentArn]" `
  --mount-options Version=NFS4 `
  --query LocationArn --output text

Write-Host "🔗 NFS Location ARN: $srcLocArn"

# 2) LOCATION S3 (dest)
$roleArn = aws iam create-role --role-name DataSyncToS3Role `
  --assume-role-policy-document '{ "Version": "2012-10-17", "Statement": [{ "Effect": "Allow","Principal": {"Service":"datasync.amazonaws.com"},"Action":"sts:AssumeRole"}]}' `
  --query Role.Arn --output text

aws iam attach-role-policy --role-name DataSyncToS3Role `
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess

$dstLocArn = aws datasync create-location-s3 `
  --s3-bucket-arn arn:aws:s3:::$bucket `
  --s3-config BucketAccessRoleArn=$roleArn `
  --subdirectory / `
  --query LocationArn --output text

Write-Host "🌟 S3 Location ARN: $dstLocArn"

# 3) TASK NFS ➜ S3
$taskArn = aws datasync create-task `
  --source-location-arn  $srcLocArn `
  --destination-location-arn $dstLocArn `
  --schedule "ScheduleExpression=$Schedule" `
  --name NfsToS3-HybridPipeline `
  --excludes "FilterType=SIMPLE_PATTERN,Value=processed/*" `
  --query TaskArn --output text

Write-Host "🗒️  Task creato: $taskArn"
Write-Host "⏳  Avvio immediato…"
aws datasync start-task-execution --task-arn $taskArn | Out-Null
Write-Host "✅  Bootstrap completato — il task girerà ogni $Schedule"
# Usage
# PS> .\datasync_bootstrap.ps1 -AgentArn "arn:aws:datasync:eu-central-1:123456789012:agent/agent-id"

