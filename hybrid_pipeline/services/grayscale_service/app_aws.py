
import os
import sys
import json
import subprocess
import tempfile
import time
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Carica variabili d'ambiente dal file .env
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

# Configurazione AWS
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.environ.get('AWS_REGION', 'eu-central-1')

# AWS services
s3 = boto3.client('s3',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)
sqs = boto3.client('sqs',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)

# Environment variables
INPUT_BUCKET = os.environ.get('INPUT_BUCKET', f'images-input-544547773663-eu-central-1')
OUTPUT_BUCKET = os.environ.get('OUTPUT_BUCKET', f'images-output-544547773663-eu-central-1')
# SQS FIFO queue
QUEUE_URL = os.environ.get('QUEUE_URL', f'https://sqs.eu-central-1.amazonaws.com/544547773663/HybridPipelineStack-ImageProcessingQueue93F2F958-47vWZN1lKvCb')
BINARY_PATH = os.path.join(os.path.dirname(__file__), 'bin', 'grayscale')

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
            s3.download_file(bucket, image_key, in_path)
        except ClientError as e:
            print(f"Error downloading {bucket}/{image_key}: {e}")
            raise
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
        with open(out_path, 'rb') as outf:
            data = outf.read()
        processed_key = f"processed/{os.path.basename(image_key)}"
        try:
            s3.put_object(
                Bucket=OUTPUT_BUCKET,
                Key=processed_key,
                Body=data,
                ContentType='image/png',
            )
            print(f"Image uploaded to S3: {OUTPUT_BUCKET}/{processed_key}")
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
                sqs.send_message(
                    QueueUrl=QUEUE_URL,
                    MessageBody=json.dumps(payload)
                )
                print(f"Result sent to SQS: {processed_key}")
            except ClientError as e:
                print(f"Error sending message to SQS: {e}")
                # Don't raise here - the processing was successful even if notification failed

def process_message(message_body):
    try:
        # S3 event notification format
        if 'Records' in message_body:
            for record in message_body['Records']:
                if record.get('eventSource') == 'aws:s3':
                    bucket = record['s3']['bucket']['name']
                    key = record['s3']['object']['key']
                    process_image(bucket, key)
        else:
            # Direct processing request format
            image_key = message_body.get('image_key')
            bucket = message_body.get('bucket', INPUT_BUCKET)
            threads = message_body.get('threads', [1])
            passes = message_body.get('passes')
            repeats = int(message_body.get('repeat', 1))
            process_image(bucket, image_key, threads, passes, repeats)
    except Exception as e:
        print(f"Error processing message: {e}")
        raise

def main():
    print("Grayscale service started - AWS version")
    print(f"Input bucket: {INPUT_BUCKET}")
    print(f"Output bucket: {OUTPUT_BUCKET}")
    print(f"Queue URL: {QUEUE_URL}")
    # Modalità event-driven: processa solo input diretto (file o stdin)
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'r') as f:
            message_body = json.load(f)
    else:
        try:
            message_body = json.load(sys.stdin)
        except Exception:
            print("No valid JSON input provided. Exiting.")
            return
    process_message(message_body)

if __name__ == "__main__":
    main()
