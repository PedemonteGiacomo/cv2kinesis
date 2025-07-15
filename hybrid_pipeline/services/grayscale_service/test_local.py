import os
import json
import subprocess

# Parametri di test (adatta i valori alle tue risorse)
message = {
    "image_key": "test.jpg",  # Sostituisci con una chiave reale su S3
    "bucket": "images-input-544547773663-eu-central-1",
    "threads": [1],
    "passes": None,
    "repeat": 1
}

# Scrivi il messaggio in un file temporaneo
with open("test_message.json", "w") as f:
    json.dump(message, f)

# Comando docker per avviare il servizio grayscale
cmd = [
    "docker", "run", "--rm", "-it",
    "-e", "INPUT_BUCKET=images-input-544547773663-eu-central-1",
    "-e", "OUTPUT_BUCKET=images-output-544547773663-eu-central-1",
    "-e", "QUEUE_URL=https://sqs.eu-central-1.amazonaws.com/544547773663/HybridPipelineStack-ImageProcessingQueue93F2F958-47vWZN1lKvCb",
    "-e", "AWS_REGION=eu-central-1",
    "-e", "AWS_DEFAULT_REGION=eu-central-1",
    "-v", f"{os.getcwd()}:/app",
    "grayscale_test:latest", "python", "app.py", "test_message.json"
]

print("Eseguo il test locale del servizio grayscale...")
subprocess.run(cmd)
