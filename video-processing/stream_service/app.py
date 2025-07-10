import io
import os
import logging
import time
import threading
from typing import Generator
from queue import Queue, Empty

import boto3
import cv2
import numpy as np
from flask import Flask, Response
from ultralytics import YOLO
from botocore.exceptions import ClientError

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

# Global variables
kinesis = None
model = None
frame_queue = Queue(maxsize=10)
latest_frame = None
kinesis_connected = False

def initialize_services():
    """Initialize Kinesis and YOLO model in background"""
    global kinesis, model, kinesis_connected
    try:
        logger.info("Initializing services...")
        
        # Initialize YOLO first (faster and always works)
        model = YOLO(YOLO_MODEL)
        logger.info("YOLO model loaded")
        
        # Initialize Kinesis with timeout protection
        kinesis = boto3.client('kinesis', region_name=AWS_REGION)
        
        # Test Kinesis connection with timeout
        try:
            kinesis.describe_stream(StreamName=KINESIS_STREAM_NAME)
            kinesis_connected = True
            logger.info("Kinesis connection established")
            
            # Start Kinesis reader thread only if connection works
            kinesis_thread = threading.Thread(target=kinesis_reader_worker, daemon=True)
            kinesis_thread.start()
            
        except Exception as kinesis_error:
            logger.warning(f"Kinesis not available: {kinesis_error}")
            kinesis_connected = False
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        kinesis_connected = False


def kinesis_reader_worker():
    """Background worker to read from Kinesis and populate frame queue"""
    global latest_frame
    
    while True:
        try:
            if not kinesis_connected:
                time.sleep(5)
                continue
                
            # Get shard iterator
            response = kinesis.describe_stream(StreamName=KINESIS_STREAM_NAME)
            shard_id = response['StreamDescription']['Shards'][0]['ShardId']
            
            resp = kinesis.get_shard_iterator(
                StreamName=KINESIS_STREAM_NAME,
                ShardId=shard_id,
                ShardIteratorType='LATEST'
            )
            iterator = resp['ShardIterator']
            
            while kinesis_connected:
                try:
                    resp = kinesis.get_records(ShardIterator=iterator, Limit=10)
                    iterator = resp['NextShardIterator']
                    
                    for record in resp['Records']:
                        frame_bytes = record['Data']
                        processed_frame = _detect(frame_bytes)
                        
                        # Update latest frame (non-blocking)
                        latest_frame = processed_frame
                        
                        # Add to queue (non-blocking)
                        try:
                            frame_queue.put_nowait(processed_frame)
                        except:
                            pass  # Queue full, skip frame
                            
                    if not resp['Records']:
                        time.sleep(1)  # No records, wait a bit
                        
                except ClientError as e:
                    error_code = e.response['Error']['Code']
                    if error_code == 'ProvisionedThroughputExceededException':
                        time.sleep(2)
                    elif error_code == 'ExpiredIteratorException':
                        break  # Get new iterator
                    else:
                        logger.error(f"Kinesis error: {e}")
                        time.sleep(5)
                        
        except Exception as e:
            logger.error(f"Error in Kinesis reader: {e}")
            time.sleep(10)


def _get_shard_iterator() -> str:
    global _shard_id
    if not _shard_id:
        desc = kinesis.describe_stream(StreamName=KINESIS_STREAM_NAME)
        _shard_id = desc['StreamDescription']['Shards'][0]['ShardId']
    resp = kinesis.get_shard_iterator(StreamName=KINESIS_STREAM_NAME,
                                      ShardId=_shard_id,
                                      ShardIteratorType='LATEST')
    return resp['ShardIterator']


def _create_placeholder_frame() -> bytes:
    """Create a placeholder frame when no data is available"""
    # Create a simple black frame with text
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(frame, "Waiting for video stream...", (50, 240), 
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    _, jpeg = cv2.imencode('.jpg', frame)
    return jpeg.tobytes()


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
    """Generate frames with error handling and recovery"""
    global latest_frame
    
    while True:
        try:
            # Try to get frame from queue first
            try:
                frame = frame_queue.get_nowait()
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                continue
            except Empty:
                pass
            
            # If no frame in queue, use latest frame or placeholder
            if latest_frame is not None:
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + latest_frame + b'\r\n')
            else:
                placeholder = _create_placeholder_frame()
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + placeholder + b'\r\n')
                
            time.sleep(0.1)  # Small delay to prevent busy loop
            
        except Exception as e:
            logger.error(f"Error in frame generator: {e}")
            placeholder = _create_placeholder_frame()
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + placeholder + b'\r\n')
            time.sleep(1)


@app.route('/')
def stream_video():
    logger.info('Client connected')
    return Response(frame_generator(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/health')
def health_check():
    """Health check endpoint for load balancer - always returns healthy"""
    return "OK", 200


def main():
    # Initialize services in background thread
    init_thread = threading.Thread(target=initialize_services, daemon=True)
    init_thread.start()
    
    # Start Flask immediately (don't wait for Kinesis)
    logger.info("Starting Flask server...")
    app.run(host='0.0.0.0', port=8080, debug=False, threaded=True)


if __name__ == '__main__':
    main()
