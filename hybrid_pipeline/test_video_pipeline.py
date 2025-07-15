#!/usr/bin/env python3
"""
Test end-to-end per il flusso VIDEO PIPELINE:
- Carica un video su S3
- Attende l'elaborazione
- Verifica l'output frame su S3
- Verifica il messaggio su SQS
"""
import boto3
import time
import os

def upload_video(bucket_name, file_path, key):
    s3 = boto3.client('s3')
    s3.upload_file(file_path, bucket_name, key)
    print(f"✅ Video caricato su S3: {bucket_name}/{key}")

def check_output(bucket_name, key):
    s3 = boto3.client('s3')
    try:
        s3.head_object(Bucket=bucket_name, Key=key)
        print(f"✅ Output trovato su S3: {bucket_name}/{key}")
    except Exception:
        print(f"❌ Output non trovato su S3: {bucket_name}/{key}")

def check_sqs(queue_url):
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    AWS_REGION = os.environ.get('AWS_DEFAULT_REGION', 'eu-central-1')
    print(f"[DEBUG] SQS config: access_key={AWS_ACCESS_KEY_ID}, region={AWS_REGION}")
    sqs = boto3.client('sqs',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION
    )
    try:
        messages = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=1, WaitTimeSeconds=5)
        if 'Messages' in messages:
            print("✅ Messaggio trovato su SQS:", messages['Messages'][0]['Body'])
        else:
            print("❌ Nessun messaggio trovato su SQS")
    except Exception as e:
        print(f"❌ Errore SQS: {e}")

if __name__ == "__main__":
    # Parametri: puoi modificarli o renderli input interattivi
    print("\n=== TEST AUTOMATICO VIDEO PIPELINE ===")
    print("Questo test carica un video su S3, attende l'elaborazione e verifica l'output frame su S3 e il messaggio su SQS.\n")

    input_bucket = os.environ.get("VIDEO_INPUT_BUCKET") or "videos-input-544547773663-eu-central-1"
    frames_bucket = os.environ.get("VIDEO_FRAMES_BUCKET") or "video-frames-544547773663-eu-central-1"
    queue_url = os.environ.get("VIDEO_PROCESSING_QUEUE_URL") or input("SQS Queue URL (video): ")
    test_video = os.environ.get("TEST_VIDEO_PATH") or input("Percorso file video da caricare: ")
    output_key = os.environ.get("TEST_FRAME_KEY")

    print(f"Carico il video '{test_video}' su S3 bucket '{input_bucket}'...")
    upload_video(input_bucket, test_video, os.path.basename(test_video))
    print("⏳ Attendo elaborazione (60s)...")
    time.sleep(60)

    if not output_key:
        print(f"[INFO] Nessun frame di output specificato. Cerco il primo frame generato nel bucket '{frames_bucket}'...")
        s3 = boto3.client('s3')
        try:
            response = s3.list_objects_v2(Bucket=frames_bucket, Prefix="frame_")
            frames = [obj['Key'] for obj in response.get('Contents', []) if obj['Key'].endswith('.jpg')]
            if frames:
                output_key = frames[0]
                print(f"[INFO] Verifico il frame: {output_key}")
            else:
                print("❌ Nessun frame trovato nel bucket.")
                output_key = None
        except Exception as e:
            print(f"❌ Errore nella ricerca frame: {e}")

    if output_key:
        print(f"Verifico l'output frame '{output_key}' su S3 bucket '{frames_bucket}'...")
        check_output(frames_bucket, output_key)
    else:
        print("❌ Frame di output non specificato e non trovato.")

    print(f"Verifico la presenza di messaggi su SQS: {queue_url}")
    check_sqs(queue_url)
