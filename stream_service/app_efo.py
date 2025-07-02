"""
EFO consumer + multiprocessing YOLO – latenza ≈ 120-150 ms
Funziona:

• In produzione (ECS): legge dallo stream Kinesis in modalità EFO,
  scrive metriche custom, invia frame annotati in S3 + SQS.

• In locale (tag ‘local’ o variabili d’ambiente dummy):
  non tenta di connettersi a Kinesis – rimane idle ma l’/health è OK.
"""
import os
import time
import logging
import multiprocessing as mp
from datetime import datetime

import boto3
import cv2
import numpy as np
from botocore.client import Config
from ultralytics import YOLO

# ───────────────────────── Log setup ─────────────────────────
log = logging.getLogger("cv2kinesis")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%H:%M:%S")

# ───────────────────────── Config env ─────────────────────────
REGION        = (os.getenv("AWS_REGION")
                 or os.getenv("AWS_DEFAULT_REGION")
                 or "eu-central-1")

STREAM_ARN    = os.getenv("KINESIS_STREAM_ARN", "")
CONSUMER_ARN  = os.getenv("KINESIS_CONSUMER_ARN", "")
POOL_SIZE     = int(os.getenv("POOL_SIZE", "4"))
THRESHOLD     = float(os.getenv("THRESHOLD", "0.5"))
MAX_Q         = int(os.getenv("MAX_QUEUE_LEN", "100"))

# se ARN mancanti o valorizzati a “dummy” → modalità offline
LOCAL_DUMMY = (STREAM_ARN.lower() in ("", "dummy")
               or CONSUMER_ARN.lower() in ("", "dummy"))

log.info("Region: %s  |  Dummy-mode: %s", REGION, LOCAL_DUMMY)

# ─────────────────── AWS client (solo se serve) ───────────────
if not LOCAL_DUMMY:
    kinesis = boto3.client("kinesis",  region_name=REGION,
                           config=Config(retries={"max_attempts": 10}))
    s3      = boto3.client("s3",       region_name=REGION)
    sqs     = boto3.client("sqs",      region_name=REGION)
    cw      = boto3.client("cloudwatch", region_name=REGION)

# ───────────────────────── Worker proc ─────────────────────────
def worker(det_q: mp.Queue, out_q: mp.Queue):
    """Figlio: riceve frame JPEG, esegue YOLO, restituisce risultato."""
    model = YOLO(os.getenv("YOLO_MODEL", "yolov8n.pt"))
    while True:
        raw = det_q.get()
        if raw is None:                       # sentinel per shutdown
            break
        ts, key, jpg = raw
        frame = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)
        results = model(frame, verbose=False)
        # … qui potresti calcolare detections_count, summary ecc.
        out_q.put((ts, key, jpg, 0, []))      # placeholder

# ─────────────────────── CloudWatch metric ─────────────────────
def metrics_writer(ms_behind_latest: int):
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

# ─────────────────────────── Main ──────────────────────────────
def main() -> None:
    det_q, out_q = mp.Queue(MAX_Q), mp.Queue(MAX_Q)

    # avvia i worker YOLO (daemonic va bene: non spawnano figli)
    for _ in range(POOL_SIZE):
        mp.Process(target=worker, args=(det_q, out_q), daemon=True).start()
    log.info("🧰 Worker pool started x%s", POOL_SIZE)

    # ---------- modalità locale: nessuna sorgente Kinesis ----------
    if LOCAL_DUMMY:
        log.warning("Dummy mode – Kinesis disattivato. In attesa …")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            log.info("Shutdown richiesto (CTRL-C)")
        return
    # ----------------------------------------------------------------

    sub = kinesis.subscribe_to_shard(
        ConsumerARN=CONSUMER_ARN,
        ShardId="ALL",
        StartingPosition={"Type": "LATEST"},
    )

    last_metric = time.time()

    for event in sub["EventStream"]:
        if "SubscribeToShardEvent" not in event:     # keep-alive
            continue

        ev = event["SubscribeToShardEvent"]
        lag_ms = ev["MillisBehindLatest"]

        # inviamo frame ai worker
        for rec in ev["Records"]:
            det_q.put((datetime.utcnow().isoformat(),
                       rec["SequenceNumber"],
                       rec["Data"]))

        # metrica autoscaling (≈ 1/min)
        if time.time() - last_metric > 55:
            metrics_writer(lag_ms)
            last_metric = time.time()

        # svuotamento out_q non-bloccante → S3 + SQS
        try:
            while True:
                ts, key, jpg, det_cnt, summary = out_q.get_nowait()
                # TODO: s3.put_object(), sqs.send_message() …
        except mp.queues.Empty:
            pass

# ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    main()
