#!/usr/bin/env bash
set -euo pipefail

while true; do
  MSG=$(aws sqs receive-message --queue-url "$QUEUE_URL" \
        --max-number-of-messages 1 --wait-time-seconds 20)
  [[ -z "$MSG" ]] && continue
  BODY=$(echo "$MSG" | jq -r '.Messages[0].Body')
  RECEIPT=$(echo "$MSG" | jq -r '.Messages[0].ReceiptHandle')
  python /app/rsna_pipeline/service/runner.py \
        --s3-input "$(echo "$BODY" | jq -r .bucket)" \
        --s3-output "$OUTPUT_BUCKET" \
        --key "$(echo "$BODY" | jq -r .key)" \
        --algo "$ALGO_ID" \
        --job-id "$(echo "$BODY" | jq -r .job_id)"
  aws sqs delete-message --queue-url "$QUEUE_URL" --receipt-handle "$RECEIPT"
done
