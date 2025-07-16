#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: $0 <agent_arn> [nfs_server] [schedule]" >&2
}

AGENT_ARN=${1-}
NFS_SERVER=${2-$(ip route | awk '$1=="default"{print $3}')}
SCHEDULE=${3-'rate(1 minute)'}

if [[ -z "$AGENT_ARN" ]]; then
    usage
    exit 1
fi

BUCKET=$(aws s3api list-buckets --query "Buckets[?contains(Name,'images-input')].Name" --output text)
if [[ -z "$BUCKET" ]]; then
    echo "Bucket images-input-… non trovato." >&2
    exit 1
fi

echo "🏷️  Bucket S3 di destinazione: $BUCKET"

SRC_LOC=$(aws datasync create-location-nfs \
  --server-hostname "$NFS_SERVER" \
  --subdirectory /data \
  --on-prem-config AgentArns=[$AGENT_ARN] \
  --mount-options Version=NFS4 \
  --query LocationArn --output text)

echo "🔗 NFS Location ARN: $SRC_LOC"

ROLE_ARN=$(aws iam create-role \
  --role-name DataSyncToS3Role \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"datasync.amazonaws.com"},"Action":"sts:AssumeRole"}]}' \
  --query Role.Arn --output text)
aws iam attach-role-policy --role-name DataSyncToS3Role --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess

DST_LOC=$(aws datasync create-location-s3 \
  --s3-bucket-arn arn:aws:s3:::$BUCKET \
  --s3-config BucketAccessRoleArn=$ROLE_ARN \
  --subdirectory / \
  --query LocationArn --output text)

echo "🎯 S3 Location ARN: $DST_LOC"

TASK_ARN=$(aws datasync create-task \
  --source-location-arn $SRC_LOC \
  --destination-location-arn $DST_LOC \
  --schedule "ScheduleExpression=$SCHEDULE" \
  --name NfsToS3-HybridPipeline \
  --excludes FilterType=SIMPLE_PATTERN,Value=processed/* \
  --query TaskArn --output text)

aws datasync start-task-execution --task-arn $TASK_ARN

echo "✅ Task $TASK_ARN creato e avviato"
