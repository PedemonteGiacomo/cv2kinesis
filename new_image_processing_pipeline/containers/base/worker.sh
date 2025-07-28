#!/usr/bin/env bash
set -euo pipefail

# opzionale: se è settata, la passiamo a tutti i comandi `aws`
ENDP_OPT=""
if [[ -n "${AWS_ENDPOINT_URL:-}" ]]; then
  ENDP_OPT="--endpoint-url ${AWS_ENDPOINT_URL}"
fi



echo "[worker] START — queue: $QUEUE_URL  output: s3://$OUTPUT_BUCKET  algo: $ALGO_ID"
echo "[worker] hostname: $(hostname)  date: $(date)"
env | grep -E 'QUEUE|BUCKET|ALGO' || true


while true; do
  TS_START=$(date +%s)
  echo "[worker] --- cycle START --- $(date) ---"
  echo "[worker] ENVIRONMENT VARS:"
  env | grep -E 'QUEUE|BUCKET|ALGO|PACS' || true
  echo "[worker] polling SQS..."
  MSG=$(aws $ENDP_OPT sqs receive-message \
            --queue-url "$QUEUE_URL" \
            --max-number-of-messages 1 \
            --wait-time-seconds 20 \
            --output json 2>&1)
  AWS_RC=$?
  echo "[worker] receive-message exit code: $AWS_RC"
  if [[ $AWS_RC -ne 0 ]]; then
    echo "[worker] ERROR: receive-message failed: $MSG"
    sleep 2
    continue
  fi
  echo "[worker] raw MSG: $MSG"
  if [[ -z "$MSG" || "$MSG" == "{}" ]]; then
    echo "[worker] no message received, continue..."
    sleep 2
    continue
  fi




  BODY=$(echo "$MSG" | jq -r '.Messages[0].Body' 2>&1)
  JQ_RC=$?
  if [[ $JQ_RC -ne 0 ]]; then
    echo "[worker] ERROR: jq failed to parse Body: $BODY"
    continue
  fi
  RECEIPT=$(echo "$MSG" | jq -r '.Messages[0].ReceiptHandle' 2>&1)
  if [[ $? -ne 0 ]]; then
    echo "[worker] ERROR: jq failed to parse ReceiptHandle: $RECEIPT"
    continue
  fi
  if [[ -z "$BODY" || "$BODY" == "null" ]]; then
    echo "[worker] ERROR: message received but no Body found! MSG: $MSG"
    continue
  fi
  echo "[worker] message BODY: $BODY"
  # Debug: mostra variabili ambiente usate dal runner
  echo "[worker] PACS_INFO: $(echo "$BODY" | jq -c '.pacs')"
  echo "[worker] PACS_API_BASE: $PACS_API_BASE"
  echo "[worker] PACS_API_KEY: $PACS_API_KEY"
  echo "[worker] CLIENT_ID: $CLIENT_ID"
  echo "[worker] RESULT_QUEUE: $RESULT_QUEUE"
  JOBID=$(echo "$BODY" | jq -r .job_id 2>&1)
  if [[ $? -ne 0 ]]; then
    echo "[worker] ERROR: jq failed to parse job_id: $JOBID"
  fi
  if [[ -z "$JOBID" || "$JOBID" == "null" ]]; then
    echo "[worker] WARNING: job_id not found in message body!"
  fi
  echo "[worker] message received: $JOBID"

  # 2. esporta variabili consumate da runner.py



  echo "[worker] parsing PACS_INFO and callback..."
  export PACS_INFO=$(echo "$BODY" | jq -c '.pacs' 2>&1)
  if [[ $? -ne 0 ]]; then
    echo "[worker] ERROR: jq failed to parse pacs: $PACS_INFO"
  fi
  export CLIENT_ID=$(echo "$BODY" | jq -r '.callback.client_id // "unknown"' 2>&1)
  if [[ $? -ne 0 ]]; then
    echo "[worker] ERROR: jq failed to parse callback.client_id: $CLIENT_ID"
  fi
  export PACS_API_BASE=${PACS_API_BASE:-}
  export PACS_API_KEY=${PACS_API_KEY:-}
  CB=$(echo "$BODY" | jq -r '.callback.queue_url // empty' 2>&1)
  if [[ $? -ne 0 ]]; then
    echo "[worker] ERROR: jq failed to parse callback.queue_url: $CB"
  fi
  export RESULT_QUEUE=${CB:-$RESULT_QUEUE}
  echo "[worker] PACS_INFO: $PACS_INFO"
  echo "[worker] CLIENT_ID: $CLIENT_ID"
  echo "[worker] RESULT_QUEUE: $RESULT_QUEUE"

  # 3. esegui l’algoritmo


  echo "[worker] >>> launching runner (streaming logs)…"
  set -x
  python -m rsna_pipeline.service.runner \
         --s3-output "$OUTPUT_BUCKET" \
         --algo "$ALGO_ID" \
         --job-id "$JOBID"
  RC=$?
  set +x
  echo "[worker] <<< runner finished with exit code $RC"
  if [[ $RC -ne 0 ]]; then
    echo "[worker] ERROR: runner failed, check above logs for stack trace"
    echo "[worker] DEBUG: PACS_INFO=$PACS_INFO, PACS_API_BASE=$PACS_API_BASE, PACS_API_KEY=$PACS_API_KEY, CLIENT_ID=$CLIENT_ID, RESULT_QUEUE=$RESULT_QUEUE, OUTPUT_BUCKET=$OUTPUT_BUCKET, ALGO_ID=$ALGO_ID, JOBID=$JOBID"
    sleep 10
    continue
  fi

  # 4. cancella il messaggio dalla coda

  echo "[worker] deleting message from SQS..."
  aws $ENDP_OPT sqs delete-message \
        --queue-url "$QUEUE_URL" \
        --receipt-handle "$RECEIPT" 2>&1
  DEL_RC=$?
  echo "[worker] delete-message exit code: $DEL_RC"
  if [[ $DEL_RC -eq 0 ]]; then
    echo "[worker] done — deleted SQS message"
  else
    echo "[worker] ERROR: failed to delete message from SQS"
  fi
  TS_END=$(date +%s)
  echo "[worker] --- cycle END --- $(date) --- duration: $((TS_END-TS_START)) seconds"
done