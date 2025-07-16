#!/usr/bin/env python3
"""
Test end-to-end per il flusso IMAGE PIPELINE:
- Carica un'immagine su S3
- Attende l'elaborazione
- Verifica l'output su S3
- Verifica il messaggio su SQS
"""
import boto3
import time
import os
import json

def upload_image(bucket_name, file_path, key):
    s3 = boto3.client('s3')
    s3.upload_file(file_path, bucket_name, key)
    print(f"✅ Immagine caricata su S3: {bucket_name}/{key}")

def check_output(bucket_name, key):
    s3 = boto3.client('s3', aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
                     aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
                     region_name=os.environ.get('AWS_REGION', 'eu-central-1'))
    try:
        s3.head_object(Bucket=bucket_name, Key=key)
        print(f"✅ Output trovato su S3: {bucket_name}/{key}")
    except Exception:
        print(f"❌ Output non trovato su S3: {bucket_name}/{key}")

def check_sqs(queue_url):
    sqs = boto3.client('sqs', 
        aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
        region_name=os.environ.get('AWS_REGION', 'eu-central-1')
    )
    def is_valid_message(body, expected_image_key, start_ts):
        try:
            payload = json.loads(body)
            image_key = payload.get('image_key')
            processed_key = payload.get('processed_key')
            timestamp = payload.get('timestamp', 0)
            # Verifica che sia il messaggio giusto e timestamp > start_ts
            return (
                image_key == expected_image_key and
                processed_key and
                timestamp > start_ts
            ), processed_key
        except Exception:
            return (False, None)

    while True:
        # Per SQS FIFO la ricezione è identica, ma si può aggiungere ReceiveRequestAttemptId per deduplica
        messages = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=5,
            ReceiveRequestAttemptId=str(int(time.time()))
        )
        if 'Messages' in messages:
            body = messages['Messages'][0]['Body']
            print("✅ Messaggio trovato su SQS FIFO:", body)
            valid, processed_key = is_valid_message(body, check_sqs.expected_image_key, check_sqs.start_ts)
            if valid:
                return processed_key
            else:
                print("⏭️ Messaggio SQS non valido, attendo quello giusto...")
        else:
            print("⏳ In attesa del messaggio su SQS FIFO...")
        time.sleep(2)

if __name__ == "__main__":
    # Parametri: puoi modificarli o renderli input interattivi
    print("\n=== TEST AUTOMATICO IMAGE PIPELINE ===")
    print("Questo test carica un'immagine su S3, attende l'elaborazione e verifica l'output su S3.")
    print("La verifica su SQS è opzionale: viene eseguita solo se la variabile IMAGE_PROCESSING_QUEUE_URL è valorizzata.\n")

    input_bucket = os.environ.get("IMAGE_INPUT_BUCKET") or "images-input-544547773663-eu-central-1"
    output_bucket = os.environ.get("IMAGE_OUTPUT_BUCKET") or "images-output-544547773663-eu-central-1"
    queue_url = os.environ.get("IMAGE_PROCESSING_QUEUE_URL") or "https://sqs.eu-central-1.amazonaws.com/544547773663/image-processing-results-544547773663.fifo"
    test_image = os.environ.get("TEST_IMAGE_PATH") or input("Percorso file immagine da caricare: ")
    output_key = os.path.basename(test_image)

    print(f"Carico l'immagine '{test_image}' su S3 bucket '{input_bucket}'...")
    upload_image(input_bucket, test_image, output_key)
    start_ts = time.time()
    if queue_url:
        print(f"⏳ Attendo il messaggio su SQS: {queue_url}")
        check_sqs.expected_image_key = output_key
        check_sqs.start_ts = start_ts
        processed_key = check_sqs(queue_url)
        if processed_key:
            print(f"Verifico l'output su S3 bucket '{output_bucket}' con key '{processed_key}'...")
            check_output(output_bucket, processed_key)
        else:
            print("❌ Messaggio SQS non valido o processed_key mancante.")
    else:
        print("[INFO] Nessuna verifica SQS: variabile IMAGE_PROCESSING_QUEUE_URL non valorizzata.")
