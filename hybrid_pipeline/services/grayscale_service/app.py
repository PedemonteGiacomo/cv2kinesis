import io
import json
import os
import subprocess
import tempfile
import time
import boto3

# Configurazione AWS
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.environ.get('AWS_DEFAULT_REGION', 'eu-central-1')

# S3 buckets
INPUT_BUCKET = os.environ.get('INPUT_BUCKET', f'images-input-544547773663-eu-central-1')
OUTPUT_BUCKET = os.environ.get('OUTPUT_BUCKET', f'images-output-544547773663-eu-central-1')

# SQS FIFO queue
QUEUE_URL = os.environ.get('QUEUE_URL', f'https://sqs.eu-central-1.amazonaws.com/544547773663/image-processing-results-544547773663.fifo')

BINARY_PATH = os.path.join(os.path.dirname(__file__), 'bin', 'grayscale')

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

def process_message(msg):
    image_key = msg['image_key']
    threads = msg.get('threads') or [1]
    if isinstance(threads, int):
        threads = [threads]
    passes = msg.get('passes')
    repeats = int(msg.get('repeat', 1))

    # Scarica immagine da S3 input
    with tempfile.TemporaryDirectory() as tmpdir:
        in_path = os.path.join(tmpdir, os.path.basename(image_key))
        s3.download_file(INPUT_BUCKET, image_key, in_path)
        out_path = os.path.join(tmpdir, 'out.png')
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
                subprocess.run(cmd, check=True, env=env)
                single.append(time.time() - start)
            times[str(t)] = sum(single) / len(single)

        with open(out_path, 'rb') as outf:
            data = outf.read()

    # Carica immagine processata su S3 output
    processed_key = f"processed/{os.path.basename(image_key)}"
    s3.put_object(
        Bucket=OUTPUT_BUCKET,
        Key=processed_key,
        Body=data,
        ContentType='image/png',
    )

    # Invia messaggio su SQS FIFO
    payload = {
        'image_key': image_key,
        'processed_key': processed_key,
        'times': times,
        'passes': passes,
    }
    sqs.send_message(
        QueueUrl=QUEUE_URL,
        MessageBody=json.dumps(payload),
        MessageGroupId='grayscale',
        MessageDeduplicationId=str(time.time())
    )

def poll_sqs():
    print(' [*] Waiting for messages on SQS FIFO queue. To exit press CTRL+C')
    while True:
        resp = sqs.receive_message(
            QueueUrl=QUEUE_URL,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=20
        )
        messages = resp.get('Messages', [])
        for m in messages:
            try:
                msg = json.loads(m['Body']) if isinstance(m['Body'], str) else m['Body']
                process_message(msg)
                sqs.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=m['ReceiptHandle'])
            except Exception as e:
                print(f'Errore nel processare il messaggio: {e}')

if __name__ == '__main__':
    poll_sqs()
