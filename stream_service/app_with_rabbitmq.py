import io
import os
import logging
import time
import threading
import json
from typing import Generator
from queue import Queue, Empty
from datetime import datetime

import boto3
import cv2
import numpy as np
from flask import Flask, Response
from ultralytics import YOLO
from botocore.exceptions import ClientError
import pika

logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(message)s',
    level=logging.INFO,
    datefmt='%d/%m/%Y %X')
logger = logging.getLogger(__name__)

KINESIS_STREAM_NAME = os.environ.get('KINESIS_STREAM_NAME', 'cv2kinesis')
AWS_REGION = os.environ.get('AWS_REGION', 'eu-central-1')
YOLO_MODEL = os.environ.get('YOLO_MODEL', 'yolov8n.pt')
THRESHOLD = float(os.environ.get('THRESHOLD', '0.5'))

# RabbitMQ configuration
RABBITMQ_HOST = os.environ.get('RABBITMQ_HOST', 'localhost')
RABBITMQ_PORT = int(os.environ.get('RABBITMQ_PORT', '5672'))
RABBITMQ_USER = os.environ.get('RABBITMQ_USER', 'admin')
RABBITMQ_PASS = os.environ.get('RABBITMQ_PASS', 'admin123')
RABBITMQ_QUEUE = os.environ.get('RABBITMQ_QUEUE', 'processing_results')

app = Flask(__name__)

# Global variables
kinesis = None
model = None
frame_queue = Queue(maxsize=10)
latest_frame = None
kinesis_connected = False
rabbitmq_channel = None
frame_counter = 0

def connect_rabbitmq():
    """Connessione a RabbitMQ con retry"""
    global rabbitmq_channel
    max_retries = 10
    
    for i in range(max_retries):
        try:
            credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(RABBITMQ_HOST, RABBITMQ_PORT, '/', credentials)
            )
            rabbitmq_channel = connection.channel()
            
            # Dichiara la queue
            rabbitmq_channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)
            
            logger.info(f"✅ Connesso a RabbitMQ: {RABBITMQ_HOST}:{RABBITMQ_PORT}")
            return True
        except Exception as e:
            logger.warning(f"🔄 Tentativo {i+1}/{max_retries} - RabbitMQ connection failed: {e}")
            time.sleep(2)
    
    logger.error("❌ Impossibile connettersi a RabbitMQ")
    return False

def send_to_rabbitmq(message_data):
    """Invia messaggio a RabbitMQ"""
    global rabbitmq_channel
    
    try:
        if rabbitmq_channel is None:
            if not connect_rabbitmq():
                return False
        
        message = json.dumps(message_data)
        rabbitmq_channel.basic_publish(
            exchange='',
            routing_key=RABBITMQ_QUEUE,
            body=message,
            properties=pika.BasicProperties(delivery_mode=2)  # Make message persistent
        )
        logger.info(f"📨 Messaggio inviato a RabbitMQ: {message_data['detections_count']} detections")
        return True
        
    except Exception as e:
        logger.error(f"❌ Errore invio RabbitMQ: {e}")
        rabbitmq_channel = None  # Reset connection
        return False

def initialize_services():
    """Initialize Kinesis, YOLO and RabbitMQ in background"""
    global kinesis, model, kinesis_connected
    try:
        logger.info("Initializing services...")
        kinesis = boto3.client('kinesis', region_name=AWS_REGION)
        model = YOLO(YOLO_MODEL)
        kinesis_connected = True
        logger.info("Kinesis and YOLO initialized successfully")
        
        # Initialize RabbitMQ connection
        connect_rabbitmq()
        
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
                        processed_frame = _detect_and_notify(frame_bytes)
                        
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

def _create_placeholder_frame() -> bytes:
    """Create a placeholder frame when no data is available"""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(frame, "Waiting for video stream...", (50, 240), 
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    _, jpeg = cv2.imencode('.jpg', frame)
    return jpeg.tobytes()

def _detect_and_notify(frame_bytes: bytes) -> bytes:
    """Run YOLO detection and send results to RabbitMQ"""
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
            
            # Add to detections list
            detections.append({
                "class": class_id,
                "conf": probability,
                "bbox": [
                    round(x1 / frame.shape[1], 3),  # Normalize to 0-1
                    round(y1 / frame.shape[0], 3),
                    round((x2-x1) / frame.shape[1], 3),
                    round((y2-y1) / frame.shape[0], 3)
                ]
            })
    
    # Create message for RabbitMQ
    message_data = {
        "frame_index": frame_counter,
        "detections_count": detection_count,
        "summary": detections,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "stream_name": KINESIS_STREAM_NAME
    }
    
    # Send to RabbitMQ
    send_to_rabbitmq(message_data)
    
    frame_counter += 1
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
    return {'status': 'healthy'}, 200

def main():
    # Initialize services in background thread
    init_thread = threading.Thread(target=initialize_services, daemon=True)
    init_thread.start()
    
    # Start Flask immediately (don't wait for Kinesis)
    logger.info("Starting Flask server...")
    app.run(host='0.0.0.0', port=8080, debug=False, threaded=True)

if __name__ == '__main__':
    main()
