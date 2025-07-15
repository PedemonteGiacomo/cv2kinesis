import io
import json
import os
import subprocess
import tempfile
import time
import boto3
from botocore.exceptions import ClientError

# AWS services
s3_client = boto3.client('s3')
sqs_client = boto3.client('sqs')

# Environment variables
INPUT_BUCKET = os.environ.get('INPUT_BUCKET')
OUTPUT_BUCKET = os.environ.get('OUTPUT_BUCKET')
QUEUE_URL = os.environ.get('QUEUE_URL')
BINARY_PATH = os.path.join(os.path.dirname(__file__), 'bin', 'grayscale')

def process_message(message_body):
    """Process a single SQS message containing image processing request"""
    try:
        # Parse the message (could be S3 event or direct processing request)
        if 'Records' in message_body:
            # S3 event notification format
            for record in message_body['Records']:
                if record.get('eventSource') == 'aws:s3':
                    bucket = record['s3']['bucket']['name']
                    key = record['s3']['object']['key']
                    process_image(bucket, key)
        else:
            # Direct processing request format
            image_key = message_body['image_key']
            bucket = message_body.get('bucket', INPUT_BUCKET)
            threads = message_body.get('threads', [1])
            passes = message_body.get('passes')
            repeats = int(message_body.get('repeat', 1))
            
            process_image(bucket, image_key, threads, passes, repeats)
            
    except Exception as e:
        print(f"Error processing message: {e}")
        raise

def process_image(bucket, image_key, threads=[1], passes=None, repeats=1):
    """Process a single image with the grayscale algorithm"""
    print(f"Processing image: {bucket}/{image_key}")
    
    if isinstance(threads, int):
        threads = [threads]
    
    # Download image from S3
    with tempfile.TemporaryDirectory() as tmpdir:
        in_path = os.path.join(tmpdir, os.path.basename(image_key))
        out_path = os.path.join(tmpdir, 'out.png')
        
        try:
            s3_client.download_file(bucket, image_key, in_path)
        except ClientError as e:
            print(f"Error downloading {bucket}/{image_key}: {e}")
            raise
        
        # Process with different thread counts
        times = {}
        for t in threads:
            env = os.environ.copy()
            env['OMP_NUM_THREADS'] = str(t)
            single = []
            
            for _ in range(repeats):
                cmd = [BINARY_PATH, in_path, out_path]
                if passes:
                    cmd.append(str(passes))
                
                start = time.time()
                try:
                    subprocess.run(cmd, check=True, env=env)
                    single.append(time.time() - start)
                except subprocess.CalledProcessError as e:
                    print(f"Error running grayscale binary: {e}")
                    raise
            
            times[str(t)] = sum(single) / len(single) if single else 0
        
        # Upload processed image to S3
        processed_key = f"processed/{os.path.basename(image_key)}"
        try:
            s3_client.upload_file(
                out_path, 
                OUTPUT_BUCKET, 
                processed_key,
                ExtraArgs={'ContentType': 'image/png'}
            )
        except ClientError as e:
            print(f"Error uploading {OUTPUT_BUCKET}/{processed_key}: {e}")
            raise
    
    # Send result to SQS queue (if queue URL is provided)
    if QUEUE_URL:
        payload = {
            'image_key': image_key,
            'processed_key': processed_key,
            'times': times,
            'passes': passes,
            'timestamp': time.time()
        }
        
        try:
            sqs_client.send_message(
                QueueUrl=QUEUE_URL,
                MessageBody=json.dumps(payload)
            )
            print(f"Result sent to SQS: {processed_key}")
        except ClientError as e:
            print(f"Error sending message to SQS: {e}")
            # Don't raise here - the processing was successful even if notification failed

def main():
    """Main function for container execution"""
    print("Grayscale service started - AWS version")
    print(f"Input bucket: {INPUT_BUCKET}")
    print(f"Output bucket: {OUTPUT_BUCKET}")
    print(f"Queue URL: {QUEUE_URL}")
    
    # For ECS Fargate, we can either:
    # 1. Poll SQS for messages (if running as a service)
    # 2. Process a single image (if triggered by Step Functions)
    
    # Check if we have specific image to process (Step Functions mode)
    image_key = os.environ.get('IMAGE_KEY')
    source_bucket = os.environ.get('SOURCE_BUCKET', INPUT_BUCKET)
    
    if image_key and source_bucket:
        # Single image processing mode (triggered by Step Functions)
        print(f"Processing single image: {source_bucket}/{image_key}")
        process_image(source_bucket, image_key)
        print("Processing completed")
    else:
        # Polling mode (for continuous processing)
        print("Starting SQS polling mode...")
        while True:
            try:
                # Poll SQS for messages
                response = sqs_client.receive_message(
                    QueueUrl=QUEUE_URL,
                    MaxNumberOfMessages=1,
                    WaitTimeSeconds=20  # Long polling
                )
                
                messages = response.get('Messages', [])
                for message in messages:
                    try:
                        message_body = json.loads(message['Body'])
                        process_message(message_body)
                        
                        # Delete processed message
                        sqs_client.delete_message(
                            QueueUrl=QUEUE_URL,
                            ReceiptHandle=message['ReceiptHandle']
                        )
                        print("Message processed and deleted")
                        
                    except Exception as e:
                        print(f"Error processing message: {e}")
                        # Message will remain in queue for retry
                        
            except KeyboardInterrupt:
                print("Shutting down...")
                break
            except Exception as e:
                print(f"Error polling SQS: {e}")
                time.sleep(5)  # Wait before retrying

if __name__ == "__main__":
    main()
