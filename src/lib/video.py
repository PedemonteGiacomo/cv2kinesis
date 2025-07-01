import cv2 as cv
import logging
import numpy as np
from ultralytics import YOLO

from lib.aws import aws_get_service
from settings import YOLO_MODEL, THRESHOLD, YOLO_CLASSES_TO_DETECT

logger = logging.getLogger(__name__)


def kinesis_consumer(kinesis_stream_name):
    logger.info(f"start reading kinesis stream from={kinesis_stream_name}")
    kinesis = aws_get_service('kinesis')
    model = YOLO(YOLO_MODEL)
    response = kinesis.describe_stream(StreamName=kinesis_stream_name)
    shard_id = response['StreamDescription']['Shards'][0]['ShardId']
    while True:
        shard_iterator_response = kinesis.get_shard_iterator(
            StreamName=kinesis_stream_name,
            ShardId=shard_id,
            ShardIteratorType='LATEST'
        )
        shard_iterator = shard_iterator_response['ShardIterator']
        response = kinesis.get_records(
            ShardIterator=shard_iterator,
            Limit=10
        )

        for record in response['Records']:
            image_data = record['Data']
            frame = cv.imdecode(np.frombuffer(image_data, np.uint8), cv.IMREAD_COLOR)
            results = model.predict(frame)
            if detect_id_in_results(results):
                logger.info('Detected')


def detect_id_in_results(results):
    status = False
    for result in results:
        for box in result.boxes:
            class_id = result.names[box.cls[0].item()]
            probability = round(box.conf[0].item(), 2)
            if probability > THRESHOLD and class_id in YOLO_CLASSES_TO_DETECT:
                status = True
    return status


def kinesis_producer(kinesis_stream_name, cam_uri, width):
    logger.info(f"start emitting stream from cam={cam_uri} to kinesis")
    kinesis = aws_get_service('kinesis')
    cap = cv.VideoCapture(cam_uri)
    
    if not cap.isOpened():
        logger.error(f"Cannot open camera {cam_uri}")
        return
    
    logger.info("Camera opened successfully. Press 'q' to quit.")
    frame_count = 0
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                logger.error("Failed to capture frame")
                break
                
            # Calculate new dimensions
            scale = width / frame.shape[1]
            height = int(frame.shape[0] * scale)
            scaled_frame = cv.resize(frame, (width, height))
            
            # Show preview (optional - comment out if running headless)
            cv.imshow('Producer - Sending to Kinesis (Press q to quit)', scaled_frame)
            if cv.waitKey(1) & 0xFF == ord('q'):
                logger.info("Quit requested by user")
                break
            
            # Encode and send to Kinesis
            try:
                _, img_encoded = cv.imencode('.jpg', scaled_frame)
                kinesis.put_record(
                    StreamName=kinesis_stream_name,
                    Data=img_encoded.tobytes(),
                    PartitionKey='1'
                )
                frame_count += 1
                if frame_count % 30 == 0:  # Log every 30 frames
                    logger.info(f"Sent {frame_count} frames to Kinesis")
                    
            except Exception as e:
                logger.error(f"Failed to send frame to Kinesis: {e}")

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        cap.release()
        cv.destroyAllWindows()
        logger.info(f"Producer stopped. Total frames sent: {frame_count}")
