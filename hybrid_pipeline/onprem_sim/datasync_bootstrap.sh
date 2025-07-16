#!/usr/bin/env bash
set -euo pipefail
usage(){ echo "Usage: $0 <agent_arn> [nfs_server] [schedule|none]" >&2; }

AGENT_ARN=${1-}; NFS_SERVER=${2-$(ip route | awk '$1=="default"{print $3}')}
SCHEDULE=${3-'rate(1 hour)'}          # <— nuovo default
ROLE_NAME="DataSyncToS3Role"; TASK_NAME="NfsToS3-HybridPipeline"
[[ -z "$AGENT_ARN" ]] && usage && exit 1

BUCKET=$(aws s3api list-buckets --query \
  "Buckets[?contains(Name,'images-input')].Name" --output text)
[[ -z "$BUCKET" ]] && { echo "Bucket images-input‑… non trovato." >&2; exit 1; }
echo "🏷️  Bucket S3 di destinazione: $BUCKET"

# 1 Location NFS
SRC_LOC=$(aws datasync create-location-nfs \
  --server-hostname "$NFS_SERVER" --subdirectory /data \
  --on-prem-config AgentArns=[$AGENT_ARN] \
  --mount-options Version=NFS4_1 --query LocationArn --output text)
echo "🔗 NFS Location ARN: $SRC_LOC"

# 2 Role (riuso se esiste)
if aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
  ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query Role.Arn --output text)
  echo "ℹ️  Ruolo IAM riutilizzato: $ROLE_ARN"
else
  ROLE_ARN=$(aws iam create-role --role-name "$ROLE_NAME" \
    --assume-role-policy-document \
    '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"datasync.amazonaws.com"},"Action":"sts:AssumeRole"}]}' \
    --query Role.Arn --output text)
  aws iam attach-role-policy --role-name "$ROLE_NAME" \
    --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
  echo "⏳ Propagazione IAM (20 s)…"; sleep 20
fi

# 3 Location S3
DST_LOC=$(aws datasync create-location-s3 \
  --s3-bucket-arn arn:aws:s3:::$BUCKET \
  --s3-config BucketAccessRoleArn=$ROLE_ARN \
  --subdirectory / --query LocationArn --output text)
echo "🎯 S3 Location ARN: $DST_LOC"

# 4 Task (riuso se esiste)
TASK_ARN=$(aws datasync list-tasks \
  --query "Tasks[?Name=='$TASK_NAME'].TaskArn" --output text)

if [[ -z "$TASK_ARN" ]]; then
  echo "🆕  Creo task $TASK_NAME"
  ARGS=(--source-location-arn "$SRC_LOC" --destination-location-arn "$DST_LOC" \
        --name "$TASK_NAME" \
        --excludes FilterType=SIMPLE_PATTERN,Value=/processed/*)
  [[ "$SCHEDULE" != "none" ]] && ARGS+=(--schedule "ScheduleExpression=$SCHEDULE")
  TASK_ARN=$(aws datasync create-task "${ARGS[@]}" --query TaskArn --output text)
else
  echo "ℹ️  Task già presente: $TASK_ARN"
fi

# 5 Avvia una esecuzione subito
aws datasync start-task-execution --task-arn "$TASK_ARN"
echo "✅ Task $TASK_ARN avviato"
