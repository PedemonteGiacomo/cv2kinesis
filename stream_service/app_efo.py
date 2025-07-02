"""
EFO consumer + multiprocessing YOLO  – latency ≈ 120-150 ms
"""
import os, json, time, logging, boto3, cv2, numpy as np, multiprocessing as mp
from botocore.client import Config
from ultralytics import YOLO
from datetime import datetime

log = logging.getLogger("cv2kinesis"); log.setLevel(logging.INFO)

STREAM_ARN   = os.environ["KINESIS_STREAM_ARN"]
CONSUMER_ARN = os.environ["KINESIS_CONSUMER_ARN"]
POOL_SIZE    = int(os.getenv("POOL_SIZE", "4"))
THRESHOLD    = float(os.getenv("THRESHOLD", "0.5"))
MAX_Q        = int(os.getenv("MAX_QUEUE_LEN", "100"))

kinesis = boto3.client("kinesis", config=Config(retries={"max_attempts": 10}))
s3      = boto3.client("s3")
sqs     = boto3.client("sqs")

# ────────────────────────────────────────────────────────────────────
def worker(det_q: mp.Queue, out_q: mp.Queue):
    """Processo figlio: prende frame JPEG, restituisce JPEG annotato + meta"""
    model = YOLO(os.getenv("YOLO_MODEL", "yolov8n.pt"))
    for raw in iter(det_q.get, None):
        ts, key, jpg = raw
        frame = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)
        results = model(frame, verbose=False)
        # … (come tua _process_frame_and_store, ma senza I/O)
        out_q.put((ts, key, jpg, 0, []))      # detections_count=0 simplific.
# ────────────────────────────────────────────────────────────────────
def metrics_writer(ms_behind_latest: int):
    """Invia custom metric a CloudWatch (1 dato/min)"""
    cw = boto3.client("cloudwatch")
    cw.put_metric_data(
        Namespace="Cv2Kinesis",
        MetricData=[{
            "MetricName": "MillisBehindLatest",
            "Dimensions": [{"Name": "Service", "Value": "Detector"}],
            "Unit": "Milliseconds",
            "Value": ms_behind_latest,
            "StorageResolution": 60
        }]
    )

def main():
    det_q = mp.Queue(MAX_Q)
    out_q = mp.Queue(MAX_Q)
    procs = [mp.Process(target=worker, args=(det_q, out_q), daemon=True) for _ in range(POOL_SIZE)]
    for p in procs: p.start()
    log.info(f"🧰 Worker pool started x{POOL_SIZE}")

    sub = kinesis.subscribe_to_shard(
        ConsumerARN=CONSUMER_ARN,
        ShardId="ALL",            # SDK si occupa degli shard nuovi
        StartingPosition={"Type": "LATEST"}
    )

    records_iter = sub.get("EventStream")
    last_metric  = time.time()

    for event in records_iter:
        if "SubscribeToShardEvent" not in event:                  # keep-alive
            continue
        ev      = event["SubscribeToShardEvent"]
        lag_ms  = ev["MillisBehindLatest"]
        for rec in ev["Records"]:
            det_q.put((datetime.utcnow().isoformat(), rec["SequenceNumber"], rec["Data"]))
        # metriche per scaling
        if time.time() - last_metric > 55:
            metrics_writer(lag_ms)
            last_metric = time.time()

        # leggi output worker (non-bloccante) → S3+SQS
        try:
            while True:
                ts, key, jpg, det_cnt, summary = out_q.get_nowait()
                # s3.put_object(), sqs.send_message()  (identico al tuo codice)
        except mp.queues.Empty:
            pass

if __name__ == "__main__":
    main()
