#!/usr/bin/env bash
set -euo pipefail

# opzionale: se è settata, la passiamo a tutti i comandi `aws`
ENDP_OPT=""
if [[ -n "${AWS_ENDPOINT_URL:-}" ]]; then
  ENDP_OPT="--endpoint-url ${AWS_ENDPOINT_URL}"
fi

echo "[worker] start — queue: $QUEUE_URL  output: s3://$OUTPUT_BUCKET  algo: $ALGO_ID"

while true; do
  # 1. ricevi un messaggio (long‑polling 20 s)
  MSG=$(aws $ENDP_OPT sqs receive-message \
            --queue-url "$QUEUE_URL" \
            --max-number-of-messages 1 \
            --wait-time-seconds 20 \
            --output json)

  # nessun messaggio → ricomincia il ciclo
  if [[ -z "$MSG" || "$MSG" == "{}" ]]; then
    continue
  fi

  BODY=$(echo "$MSG" | jq -r '.Messages[0].Body')
  RECEIPT=$(echo "$MSG" | jq -r '.Messages[0].ReceiptHandle')
  echo "[worker] message received: $(echo "$BODY" | jq -r .job_id)"

  # 2. esporta variabili consumate da runner.py
  export PACS_INFO=$(echo "$BODY" | jq -c '.pacs')
  export PACS_API_BASE=${PACS_API_BASE:-}
  export PACS_API_KEY=${PACS_API_KEY:-}

  # 3. esegui l’algoritmo
  python /app/rsna_pipeline/service/runner.py \
         --s3-output "$OUTPUT_BUCKET" \
         --algo "$ALGO_ID" \
         --job-id "$(echo "$BODY" | jq -r .job_id)"

  # 4. cancella il messaggio dalla coda
  aws $ENDP_OPT sqs delete-message \
        --queue-url "$QUEUE_URL" \
        --receipt-handle "$RECEIPT"

  echo "[worker] done — deleted SQS message"
done