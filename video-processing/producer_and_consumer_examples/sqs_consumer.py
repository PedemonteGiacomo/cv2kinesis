#!/usr/bin/env python3
"""
Consumer AWS: Legge messaggi da SQS queue e può scaricare immagini da S3
Simula il comportamento del frontend che riceverà i risultati del processing
usato in DEPLOY_AND_TEST per testare il pipeline.
Simula il comportamento del frontend che riceverà i risultati del processing.
Mostra log dettagliati delle detection trovate.
"""
import boto3
import json
import time
import logging
from typing import Dict, Any

logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(message)s',
    level=logging.INFO,
    datefmt='%d/%m/%Y %X'
)
logger = logging.getLogger(__name__)

class ProcessingResultsConsumer:
    def __init__(self, queue_url: str, region: str = 'eu-central-1'):
        self.queue_url = queue_url
        self.region = region
        self.sqs = boto3.client('sqs', region_name=region)
        self.s3 = boto3.client('s3', region_name=region)
        
    def poll_messages(self, max_messages: int = 10, wait_time: int = 20):
        """Poll SQS for messages"""
        logger.info(f"📡 Polling SQS queue: {self.queue_url}")
        logger.info(f"⏱️ Long polling: {wait_time}s, Max messages: {max_messages}")
        
        while True:
            try:
                response = self.sqs.receive_message(
                    QueueUrl=self.queue_url,
                    MaxNumberOfMessages=max_messages,
                    WaitTimeSeconds=wait_time,
                    MessageAttributeNames=['All']
                )
                
                messages = response.get('Messages', [])
                
                if not messages:
                    logger.info("🔄 No messages received, continuing to poll...")
                    continue
                
                logger.info(f"📨 Received {len(messages)} message(s)")
                
                for message in messages:
                    self.process_message(message)
                    
            except Exception as e:
                logger.error(f"❌ Error polling SQS: {e}")
                time.sleep(5)
    
    def process_message(self, message: Dict[str, Any]):
        """Process a single SQS message"""
        try:
            body = json.loads(message['Body'])
            receipt_handle = message['ReceiptHandle']
            
            logger.info("\n" + "="*80)
            logger.info("📨 PROCESSING RESULT RECEIVED")
            logger.info("="*80)
            
            # Log message details
            logger.info(f"🎯 Detections: {body.get('detections_count', 0)}")
            logger.info(f"📸 Frame: {body.get('frame_index', 'N/A')}")
            logger.info(f"⏰ Timestamp: {body.get('timestamp', 'N/A')}")
            logger.info(f"🎥 Stream: {body.get('stream_name', 'N/A')}")
            logger.info(f"📦 S3 Location: s3://{body.get('bucket', 'N/A')}/{body.get('key', 'N/A')}")
            
            # Log detections
            summary = body.get('summary', [])
            if summary:
                logger.info(f"🔍 Detected objects:")
                for i, detection in enumerate(summary, 1):
                    bbox = detection.get('bbox', [])
                    logger.info(f"   {i}. {detection.get('class', 'unknown')} "
                              f"(confidence: {detection.get('conf', 0):.2f}, "
                              f"bbox: {bbox})")
            else:
                logger.info("🔍 No objects detected")
            
            # Optional: Download and save the image
            bucket = body.get('bucket')
            key = body.get('key')
            if bucket and key:
                self.download_processed_frame(bucket, key, body.get('frame_index', 0))
            
            # Delete message from queue
            self.sqs.delete_message(
                QueueUrl=self.queue_url,
                ReceiptHandle=receipt_handle
            )
            
            logger.info("✅ Message processed and deleted from queue")
            logger.info("="*80 + "\n")
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON in message: {e}")
        except Exception as e:
            logger.error(f"❌ Error processing message: {e}")
    
    def download_processed_frame(self, bucket: str, key: str, frame_index: int):
        """Download processed frame from S3 (optional)"""
        try:
            # Create local filename
            local_filename = f"downloaded_frame_{frame_index}.jpg"
            
            # Download from S3
            self.s3.download_file(bucket, key, local_filename)
            logger.info(f"💾 Downloaded frame to: {local_filename}")
            
        except Exception as e:
            logger.warning(f"⚠️ Could not download frame: {e}")

def main():
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python sqs_consumer.py <SQS_QUEUE_URL>")
        print("\nExample:")
        print("python sqs_consumer.py https://sqs.eu-central-1.amazonaws.com/123456789/processing-results")
        sys.exit(1)
    
    queue_url = sys.argv[1]
    
    logger.info("🚀 Starting Processing Results Consumer")
    logger.info(f"📨 SQS Queue: {queue_url}")
    logger.info("🔄 Press Ctrl+C to stop\n")
    
    consumer = ProcessingResultsConsumer(queue_url)
    
    try:
        consumer.poll_messages()
    except KeyboardInterrupt:
        logger.info("\n⏹️ Stopping consumer...")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")

if __name__ == "__main__":
    main()
