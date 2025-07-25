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
  TS_START=$(date +%s)
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
  JOBID=$(echo "$BODY" | jq -r .job_id 2>&1)
  if [[ $? -ne 0 ]]; then
    echo "[worker] ERROR: jq failed to parse job_id: $JOBID"
  fi
  JOB_ALGO=$(echo "$BODY" | jq -r .algo_id 2>&1)
  if [[ $? -ne 0 ]]; then
    echo "[worker] ERROR: jq failed to parse algo_id: $JOB_ALGO"
  fi
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
         --visibility-timeout 0 2>&1
    echo "[worker] change-message-visibility exit code: $?"
    continue
  fi
  echo "[worker] message received: $JOB_ALGO / $JOBID"

  # 2. esporta variabili consumate da runner.py



  echo "[worker] parsing PACS_INFO and callback..."
  export PACS_INFO=$(echo "$BODY" | jq -c '.pacs' 2>&1)
  if [[ $? -ne 0 ]]; then
    echo "[worker] ERROR: jq failed to parse pacs: $PACS_INFO"
  fi
  export PACS_API_BASE=${PACS_API_BASE:-}
  export PACS_API_KEY=${PACS_API_KEY:-}
  CB=$(echo "$BODY" | jq -r '.callback.queue_url // empty' 2>&1)
  if [[ $? -ne 0 ]]; then
    echo "[worker] ERROR: jq failed to parse callback.queue_url: $CB"
  fi
  export RESULT_QUEUE=${CB:-$RESULT_QUEUE}
  echo "[worker] PACS_INFO: $PACS_INFO"
  echo "[worker] RESULT_QUEUE: $RESULT_QUEUE"

  # 3. esegui l’algoritmo


  echo "[worker] launching runner: python -m rsna_pipeline.service.runner --s3-output $OUTPUT_BUCKET --algo $ALGO_ID --job-id $JOBID"
  RUNNER_CMD="python -m rsna_pipeline.service.runner --s3-output \"$OUTPUT_BUCKET\" --algo \"$ALGO_ID\" --job-id \"$JOBID\""
  RESPONSE=$(python -m rsna_pipeline.service.runner \
         --s3-output "$OUTPUT_BUCKET" \
         --algo "$ALGO_ID" \
         --job-id "$JOBID" 2>&1)
  RUN_RC=$?
  echo "[worker] runner exit code: $RUN_RC"
  echo "[worker] runner output: $RESPONSE"
  if [[ $RUN_RC -ne 0 ]]; then
    echo "[worker] ERROR: runner failed"
  fi
  echo "[worker] runner finished."

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
  echo "[worker] cycle time: $((TS_END-TS_START)) seconds"
done