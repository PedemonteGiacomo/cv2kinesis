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

def upload_image(bucket_name, file_path, key):
    s3 = boto3.client('s3')
    s3.upload_file(file_path, bucket_name, key)
    print(f"✅ Immagine caricata su S3: {bucket_name}/{key}")

def check_output(bucket_name, key):
    s3 = boto3.client('s3')
    try:
        s3.head_object(Bucket=bucket_name, Key=key)
        print(f"✅ Output trovato su S3: {bucket_name}/{key}")
    except Exception:
        print(f"❌ Output non trovato su S3: {bucket_name}/{key}")

def check_sqs(queue_url):
    sqs = boto3.client('sqs')
    messages = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=1, WaitTimeSeconds=5)
    if 'Messages' in messages:
        print("✅ Messaggio trovato su SQS:", messages['Messages'][0]['Body'])
    else:
        print("❌ Nessun messaggio trovato su SQS")

if __name__ == "__main__":
    # Parametri: puoi modificarli o renderli input interattivi
    print("\n=== TEST AUTOMATICO IMAGE PIPELINE ===")
    print("Questo test carica un'immagine su S3, attende l'elaborazione e verifica l'output su S3.")
    print("La verifica su SQS è opzionale: viene eseguita solo se la variabile IMAGE_PROCESSING_QUEUE_URL è valorizzata.\n")

    input_bucket = os.environ.get("IMAGE_INPUT_BUCKET") or "images-input-544547773663-eu-central-1"
    output_bucket = os.environ.get("IMAGE_OUTPUT_BUCKET") or "images-output-544547773663-eu-central-1"
    queue_url = os.environ.get("IMAGE_PROCESSING_QUEUE_URL")
    test_image = os.environ.get("TEST_IMAGE_PATH") or input("Percorso file immagine da caricare: ")
    output_key = os.path.basename(test_image)

    print(f"Carico l'immagine '{test_image}' su S3 bucket '{input_bucket}'...")
    upload_image(input_bucket, test_image, output_key)
    print("⏳ Attendo elaborazione (30s)...")
    time.sleep(30)
    print(f"Verifico l'output su S3 bucket '{output_bucket}'...")
    check_output(output_bucket, output_key)
    if queue_url:
        print(f"Verifico la presenza di messaggi su SQS: {queue_url}")
        check_sqs(queue_url)
    else:
        print("[INFO] Nessuna verifica SQS: variabile IMAGE_PROCESSING_QUEUE_URL non valorizzata.")
