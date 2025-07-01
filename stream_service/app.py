import io
import os
import logging
from typing import Generator

import boto3
import cv2
import numpy as np
from flask import Flask, Response
from ultralytics import YOLO

logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(message)s',
    level=logging.INFO,
    datefmt='%d/%m/%Y %X')
logger = logging.getLogger(__name__)

KINESIS_STREAM_NAME = os.environ.get('KINESIS_STREAM_NAME', 'cv2kinesis')
AWS_REGION = os.environ.get('AWS_REGION', 'eu-central-1')
YOLO_MODEL = os.environ.get('YOLO_MODEL', 'yolov8n.pt')
THRESHOLD = float(os.environ.get('THRESHOLD', '0.5'))

app = Flask(__name__)

kinesis = boto3.client('kinesis', region_name=AWS_REGION)
model = YOLO(YOLO_MODEL)

_shard_id = None

def _get_shard_iterator() -> str:
    global _shard_id
    if not _shard_id:
        desc = kinesis.describe_stream(StreamName=KINESIS_STREAM_NAME)
        _shard_id = desc['StreamDescription']['Shards'][0]['ShardId']
    resp = kinesis.get_shard_iterator(StreamName=KINESIS_STREAM_NAME,
                                      ShardId=_shard_id,
                                      ShardIteratorType='LATEST')
    return resp['ShardIterator']

def _read_frames() -> Generator[bytes, None, None]:
    iterator = _get_shard_iterator()
    while True:
        resp = kinesis.get_records(ShardIterator=iterator, Limit=10)
        iterator = resp['NextShardIterator']
        for record in resp['Records']:
            yield record['Data']


def _detect(frame_bytes: bytes) -> bytes:
    frame = cv2.imdecode(np.frombuffer(frame_bytes, np.uint8), cv2.IMREAD_COLOR)
    results = model.predict(frame)
    for result in results:
        for box in result.boxes:
            class_id = result.names[box.cls[0].item()]
            probability = round(box.conf[0].item(), 2)
            if probability < THRESHOLD:
                continue
            x1, y1, x2, y2 = [int(x) for x in box.xyxy[0].tolist()]
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(
                frame,
                f"{class_id} {probability:.2f}",
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                1,
            )
    _, jpeg = cv2.imencode('.jpg', frame)
    return jpeg.tobytes()


def frame_generator() -> Generator[bytes, None, None]:
    for frame_bytes in _read_frames():
        annotated = _detect(frame_bytes)
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + annotated + b'\r\n')


@app.route('/')
def stream_video():
    logger.info('Client connected')
    return Response(frame_generator(), mimetype='multipart/x-mixed-replace; boundary=frame')


def main():
    app.run(host='0.0.0.0', port=8080)


if __name__ == '__main__':
    main()
