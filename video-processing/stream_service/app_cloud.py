import io
import os
import logging
import time
import threading
import json
from typing import Generator
from queue import Queue, Empty
from datetime import datetime

# Fix per PyTorch weights_only issue
import torch
original_load = torch.load
def patched_load(f, map_location=None, pickle_module=None, weights_only=None, **kwargs):
    return original_load(f, map_location=map_location, pickle_module=pickle_module, weights_only=False, **kwargs)
torch.load = patched_load

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
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', 'processedframes-default')
SQS_QUEUE_URL = os.environ.get('SQS_QUEUE_URL', '')
AWS_REGION = os.environ.get('AWS_REGION', 'eu-central-1')
YOLO_MODEL = os.environ.get('YOLO_MODEL', 'yolov8n.pt')
THRESHOLD = float(os.environ.get('THRESHOLD', '0.5'))

app = Flask(__name__)

# Global variables
kinesis = None
s3_client = None
sqs_client = None
model = None
frame_queue = Queue(maxsize=10)
latest_frame = None
kinesis_connected = False
frame_counter = 0

def initialize_services():
    """Initialize AWS services and YOLO model"""
    global kinesis, s3_client, sqs_client, model, kinesis_connected
    try:
        logger.info("Initializing services...")
        
        # Initialize AWS clients
        kinesis = boto3.client('kinesis', region_name=AWS_REGION)
        s3_client = boto3.client('s3', region_name=AWS_REGION)
        sqs_client = boto3.client('sqs', region_name=AWS_REGION)
        
        # Initialize YOLO model with explicit configuration
        logger.info(f"Loading YOLO model: {YOLO_MODEL}")
        model = YOLO(YOLO_MODEL)
        
        # Warm up the model with a dummy prediction
        dummy_frame = np.zeros((640, 640, 3), dtype=np.uint8)
        _ = model.predict(dummy_frame, verbose=False)
        logger.info("✅ YOLO model warmed up successfully")
        
        # Log YOLO model info
        logger.info(f"🎯 YOLO classes available: {len(model.names)} classes")
        logger.info(f"🔍 Detection threshold: {THRESHOLD}")
        
        kinesis_connected = True
        logger.info("✅ All services initialized successfully")
        
        # Start Kinesis reader thread
        kinesis_thread = threading.Thread(target=kinesis_reader_worker, daemon=True)
        kinesis_thread.start()
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        kinesis_connected = False

def kinesis_reader_worker():
    """Background worker to read from Kinesis and process frames"""
    global latest_frame, frame_counter
    
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
                        processed_frame = _process_frame_and_store(frame_bytes)
                        
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

def _process_frame_and_store(frame_bytes: bytes) -> bytes:
    """Process frame with YOLO, save to S3, and send SQS message"""
    global frame_counter
    
    frame = cv2.imdecode(np.frombuffer(frame_bytes, np.uint8), cv2.IMREAD_COLOR)
    results = model.predict(frame)
    
    detections = []
    detection_count = 0
    
    for result in results:
        for box in result.boxes:
            class_id = result.names[box.cls[0].item()]
            probability = round(box.conf[0].item(), 2)
            if probability < THRESHOLD:
                continue
                
            detection_count += 1
            x1, y1, x2, y2 = [int(x) for x in box.xyxy[0].tolist()]
            
            # Draw on frame
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
            
            # Add to detections list (normalized coordinates)
            detections.append({
                "class": class_id,
                "conf": probability,
                "bbox": [
                    round(x1 / frame.shape[1], 3),  # x
                    round(y1 / frame.shape[0], 3),  # y  
                    round((x2-x1) / frame.shape[1], 3),  # width
                    round((y2-y1) / frame.shape[0], 3)   # height
                ]
            })
    
    # Encode frame as JPEG
    _, jpeg_buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    
    # Save to S3
    timestamp = datetime.utcnow()
    timestamp_str = timestamp.strftime("%Y-%m-%d/%H-%M-%S")
    frame_key = f"{timestamp_str}/frame_{frame_counter}_{int(timestamp.timestamp())}.jpg"
    
    try:
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=frame_key,
            Body=jpeg_buffer.tobytes(),
            ContentType='image/jpeg'
        )
        logger.info(f"📦 Frame saved to S3: s3://{S3_BUCKET_NAME}/{frame_key}")
        
        # Create SQS message
        message_data = {
            "bucket": S3_BUCKET_NAME,
            "key": frame_key,
            "frame_index": frame_counter,
            "detections_count": detection_count,
            "summary": detections,
            "timestamp": timestamp.isoformat() + "Z",
            "stream_name": KINESIS_STREAM_NAME
        }
        
        # Send to SQS - FIFO VERSION
        if SQS_QUEUE_URL:
            sqs_client.send_message(
                QueueUrl=SQS_QUEUE_URL,
                MessageBody=json.dumps(message_data),
                MessageGroupId="video-stream",  # 🎯 REQUIRED per FIFO
                MessageDeduplicationId=f"frame_{frame_counter}_{int(timestamp.timestamp())}"  # 🔧 Deduplicazione
            )
            logger.info(f"📨 Message sent to SQS FIFO: {detection_count} detections")
        
    except Exception as e:
        logger.error(f"❌ Error saving to S3/SQS: {e}")
    
    frame_counter += 1
    return jpeg_buffer.tobytes()

def _create_placeholder_frame() -> bytes:
    """Create a placeholder frame when no data is available"""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(frame, "Waiting for video stream...", (50, 240), 
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
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
    logger.info('Client connected to video stream')
    return Response(frame_generator(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/health')
def health_check():
    """Health check endpoint for load balancer"""
    return {'status': 'healthy'}, 200

@app.route('/status')
def status():
    """Status endpoint for debugging"""
    return {
        'status': 'running',
        'kinesis_connected': kinesis_connected,
        'model_loaded': model is not None,
        'frame_counter': frame_counter,
        'kinesis_stream': KINESIS_STREAM_NAME,
        's3_bucket': S3_BUCKET_NAME,
        'sqs_queue': SQS_QUEUE_URL
    }

def main():
    # Initialize services in background thread
    init_thread = threading.Thread(target=initialize_services, daemon=True)
    init_thread.start()
    
    # Start Flask immediately (don't wait for services)
    logger.info("Starting Flask server...")
    logger.info(f"🎥 Kinesis stream: {KINESIS_STREAM_NAME}")
    logger.info(f"📦 S3 bucket: {S3_BUCKET_NAME}")
    logger.info(f"📨 SQS queue: {SQS_QUEUE_URL}")
    app.run(host='0.0.0.0', port=8080, debug=False, threaded=True)

if __name__ == '__main__':
    main()
