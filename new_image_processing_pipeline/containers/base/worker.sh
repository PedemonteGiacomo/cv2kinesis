#!/usr/bin/env bash
set -euo pipefail

# opzionale: se è settata, la passiamo a tutti i comandi `aws`
ENDP_OPT=""
if [[ -n "${AWS_ENDPOINT_URL:-}" ]]; then
  ENDP_OPT="--endpoint-url ${AWS_ENDPOINT_URL}"
fi


echo "[worker] start — queue: $QUEUE_URL  output: s3://$OUTPUT_BUCKET  algo: $ALGO_ID"
echo "[worker] hostname: $(hostname)  date: $(date)"

while true; do
  # 1. ricevi un messaggio (long‑polling 20 s)

  echo "[worker] polling SQS..."
  MSG=$(aws $ENDP_OPT sqs receive-message \
            --queue-url "$QUEUE_URL" \
            --max-number-of-messages 1 \
            --wait-time-seconds 20 \
            --output json)
  echo "[worker] raw MSG: $MSG"

  # nessun messaggio → ricomincia il ciclo

  if [[ -z "$MSG" || "$MSG" == "{}" ]]; then
    echo "[worker] no message received, continue..."
    continue
  fi



  BODY=$(echo "$MSG" | jq -r '.Messages[0].Body')
  RECEIPT=$(echo "$MSG" | jq -r '.Messages[0].ReceiptHandle')
  if [[ -z "$BODY" || "$BODY" == "null" ]]; then
    echo "[worker] ERROR: message received but no Body found! MSG: $MSG"
    continue
  fi
  echo "[worker] message BODY: $BODY"
  JOBID=$(echo "$BODY" | jq -r .job_id 2>/dev/null)
  JOB_ALGO=$(echo "$BODY" | jq -r .algo_id 2>/dev/null)
  if [[ -z "$JOBID" || "$JOBID" == "null" ]]; then
    echo "[worker] WARNING: job_id not found in message body!"
  fi
  if [[ -z "$JOB_ALGO" || "$JOB_ALGO" == "null" ]]; then
    echo "[worker] WARNING: algo_id not found in message body!"
  fi

  # Filtro: solo i messaggi destinati a questo worker
  if [[ "$JOB_ALGO" != "$ALGO_ID" ]]; then
    echo "[worker] message algo_id $JOB_ALGO does not match this worker ($ALGO_ID), releasing message."
    aws $ENDP_OPT sqs change-message-visibility \
         --queue-url "$QUEUE_URL" \
         --receipt-handle "$RECEIPT" \
         --visibility-timeout 0
    continue
  fi
  echo "[worker] message received: $JOB_ALGO / $JOBID"

  # 2. esporta variabili consumate da runner.py


  echo "[worker] parsing PACS_INFO and callback..."
  export PACS_INFO=$(echo "$BODY" | jq -c '.pacs')
  export PACS_API_BASE=${PACS_API_BASE:-}
  export PACS_API_KEY=${PACS_API_KEY:-}
  CB=$(echo "$BODY" | jq -r '.callback.queue_url // empty')
  export RESULT_QUEUE=${CB:-$RESULT_QUEUE}
  echo "[worker] PACS_INFO: $PACS_INFO"
  echo "[worker] RESULT_QUEUE: $RESULT_QUEUE"

  # 3. esegui l’algoritmo

  echo "[worker] launching runner..."
  python -m rsna_pipeline.service.runner \
         --s3-output "$OUTPUT_BUCKET" \
         --algo "$ALGO_ID" \
         --job-id "$(echo "$BODY" | jq -r .job_id)"
  echo "[worker] runner finished."

  # 4. cancella il messaggio dalla coda

  echo "[worker] deleting message from SQS..."
  aws $ENDP_OPT sqs delete-message \
        --queue-url "$QUEUE_URL" \
        --receipt-handle "$RECEIPT"

  echo "[worker] done — deleted SQS message"
done