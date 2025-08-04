#!/usr/bin/env python3
"""
Adapter minimale per algoritmi OpenMP/nativi
Esempio di come integrare un eseguibile compilato nell'architettura MIP
"""
import os, json, time, subprocess, shutil, tempfile
import boto3, requests
from urllib.parse import urlparse
from pathlib import Path

def _recv(queue_url):
    """Riceve un messaggio dalla coda SQS"""
    sqs = boto3.client("sqs")
    r = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=1, WaitTimeSeconds=20)
    msgs = r.get("Messages", [])
    if not msgs: return None
    m = msgs[0]
    return m["ReceiptHandle"], json.loads(m["Body"])

def _del(queue_url, rh):
    """Elimina il messaggio dalla coda dopo l'elaborazione"""
    boto3.client("sqs").delete_message(QueueUrl=queue_url, ReceiptHandle=rh)

def _download(url, dst: Path):
    """Scarica un file da URL"""
    r = requests.get(url, stream=True, timeout=20); r.raise_for_status()
    with open(dst, "wb") as f: shutil.copyfileobj(r.raw, f)

def main():
    """Loop principale per processare i job"""
    # Variabili d'ambiente (standard per tutti i container)
    qurl = os.environ["QUEUE_URL"]
    out_bucket = os.environ["OUTPUT_BUCKET"]
    pacs_base = os.environ.get("PACS_API_BASE","")
    pacs_key = os.environ.get("PACS_API_KEY","")
    result_q = os.environ["RESULT_QUEUE"]
    algo_id = os.environ["ALGO_ID"]
    
    # Client AWS
    s3 = boto3.client("s3")
    sqs = boto3.client("sqs")

    print(f"[adapter] Starting {algo_id} worker")
    print(f"[adapter] Queue: {qurl}")
    print(f"[adapter] Output bucket: {out_bucket}")

    while True:
        # 1. Ricevi messaggio dalla coda
        got = _recv(qurl)
        if not got: 
            continue
            
        rh, body = got
        client_id = body["client_id"]
        job_id = body.get("job_id", "unknown")
        pacs = body["pacs"]
        
        print(f"[adapter] Processing job {job_id} for client {client_id}")

        try:
            with tempfile.TemporaryDirectory() as tmp:
                # 2. Scarica input dal PACS
                if pacs.get("scope", "image") == "image":
                    ep = f"{pacs_base}/studies/{pacs['study_id']}/images/{pacs['series_id']}/{pacs['image_id']}"
                    r = requests.get(ep, headers={"x-api-key": pacs_key}, timeout=20)
                    r.raise_for_status()
                    url = r.json()["url"]
                    src = Path(tmp) / Path(urlparse(url).path).name
                    _download(url, src)
                    print(f"[adapter] Downloaded input: {src}")
                else:
                    # Per scope=series potresti scaricare più file
                    raise ValueError("Solo scope=image supportato in questo esempio")

                # 3. Esegui l'algoritmo nativo
                # Supponiamo che il tuo eseguibile OpenMP sia in /app/bin/my_openmp
                output_path = Path(tmp) / f"{Path(src).stem}_{algo_id}.dcm"
                
                # Esempio di comando (adatta ai tuoi parametri)
                cmd = [
                    "/app/bin/my_openmp",  # percorso al tuo eseguibile
                    "-i", str(src),        # input file
                    "-o", str(output_path),# output file
                    "-t", os.environ.get("OMP_NUM_THREADS", "2")  # thread OpenMP
                ]
                
                print(f"[adapter] Executing: {' '.join(cmd)}")
                result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                print(f"[adapter] Command output: {result.stdout}")
                
                if not output_path.exists():
                    raise FileNotFoundError(f"Output file not created: {output_path}")

                # 4. Upload risultato su S3
                dest_key = f"{pacs['study_id']}/{pacs['series_id']}/{Path(output_path).name}"
                s3.upload_file(str(output_path), out_bucket, dest_key)
                print(f"[adapter] Uploaded to S3: s3://{out_bucket}/{dest_key}")

                # 5. Genera presigned URL
                presigned = s3.generate_presigned_url(
                    "get_object", 
                    Params={"Bucket": out_bucket, "Key": dest_key}, 
                    ExpiresIn=86400
                )

                # 6. Invia risultato sulla coda dei risultati
                msg = {
                    "job_id": job_id,
                    "algo_id": algo_id,
                    "client_id": client_id,
                    "dicom": {
                        "bucket": out_bucket,
                        "key": dest_key,
                        "url": presigned
                    }
                }
                
                sqs.send_message(
                    QueueUrl=result_q,
                    MessageBody=json.dumps(msg),
                    MessageGroupId=job_id or "default"
                )
                
                print(f"[adapter] Job {job_id} completed successfully")

        except Exception as e:
            print(f"[adapter] Error processing job {job_id}: {e}")
            # Potresti inviare un messaggio di errore sulla coda risultati
            error_msg = {
                "job_id": job_id,
                "algo_id": algo_id,
                "client_id": client_id,
                "error": str(e)
            }
            try:
                sqs.send_message(
                    QueueUrl=result_q,
                    MessageBody=json.dumps(error_msg),
                    MessageGroupId=job_id or "default"
                )
            except:
                pass
        finally:
            # 7. Elimina il messaggio dalla coda
            _del(qurl, rh)

if __name__ == "__main__":
    main()
