#!/usr/bin/env python3
"""
Adapter per algoritmo grayscale OpenMP
Versione adattata del servizio grayscale per l'architettura MIP AWS
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
    r = requests.get(url, stream=True, timeout=30)
    r.raise_for_status()
    with open(dst, "wb") as f: 
        shutil.copyfileobj(r.raw, f)

def _is_dicom_file(file_path: Path) -> bool:
    """Controlla se il file è un DICOM"""
    try:
        with open(file_path, 'rb') as f:
            # DICOM files iniziano con un preamble di 128 bytes + "DICM"
            f.seek(128)
            return f.read(4) == b'DICM'
    except:
        return False

def _convert_dicom_to_png(dicom_path: Path, png_path: Path):
    """Converte DICOM in PNG usando pydicom"""
    try:
        import pydicom
        from PIL import Image
        import numpy as np
        
        # Leggi DICOM
        dicom = pydicom.dcmread(str(dicom_path))
        
        # Estrai pixel array
        pixel_array = dicom.pixel_array
        
        # Normalize to 0-255
        if pixel_array.max() > 255:
            pixel_array = ((pixel_array - pixel_array.min()) / 
                          (pixel_array.max() - pixel_array.min()) * 255).astype(np.uint8)
        
        # Se grayscale, converte a RGB per compatibilità
        if len(pixel_array.shape) == 2:
            pixel_array = np.stack([pixel_array] * 3, axis=-1)
        
        # Salva come PNG
        Image.fromarray(pixel_array).save(str(png_path))
        return True
    except Exception as e:
        print(f"[grayscale] Error converting DICOM: {e}")
        return False

def _convert_png_to_dicom(png_path: Path, original_dicom: Path, output_dicom: Path):
    """Converte PNG processato di nuovo in DICOM"""
    try:
        import pydicom
        from PIL import Image
        import numpy as np
        
        # Leggi DICOM originale per metadati
        original = pydicom.dcmread(str(original_dicom))
        
        # Leggi PNG processato
        processed_img = Image.open(str(png_path))
        processed_array = np.array(processed_img)
        
        # Se RGB, prendi solo un canale (dovrebbe essere grayscale)
        if len(processed_array.shape) == 3:
            processed_array = processed_array[:, :, 0]
        
        # Aggiorna pixel array nel DICOM
        original.PixelData = processed_array.tobytes()
        original.Rows, original.Columns = processed_array.shape
        
        # Aggiorna metadati per indicare elaborazione
        original.ImageComments = f"Processed with grayscale algorithm - {time.strftime('%Y%m%d_%H%M%S')}"
        if hasattr(original, 'SeriesDescription'):
            original.SeriesDescription = f"GRAYSCALE_{original.SeriesDescription}"
        
        # Salva nuovo DICOM
        original.save_as(str(output_dicom))
        return True
    except Exception as e:
        print(f"[grayscale] Error creating output DICOM: {e}")
        return False

def main():
    """Loop principale per processare i job grayscale"""
    # Variabili d'ambiente standard
    qurl = os.environ["QUEUE_URL"]
    out_bucket = os.environ["OUTPUT_BUCKET"]
    pacs_base = os.environ.get("PACS_API_BASE", "")
    pacs_key = os.environ.get("PACS_API_KEY", "")
    result_q = os.environ["RESULT_QUEUE"]
    algo_id = os.environ["ALGO_ID"]
    
    # Parametri algoritmo grayscale
    binary_path = "/app/bin/grayscale"
    default_threads = int(os.environ.get("OMP_NUM_THREADS", "2"))
    default_passes = int(os.environ.get("GRAYSCALE_PASSES", "1"))
    
    # Client AWS
    s3 = boto3.client("s3")
    sqs = boto3.client("sqs")

    print(f"[grayscale] Starting {algo_id} worker")
    print(f"[grayscale] Queue: {qurl}")
    print(f"[grayscale] Output bucket: {out_bucket}")
    print(f"[grayscale] Binary: {binary_path}")
    print(f"[grayscale] Default threads: {default_threads}")

    # Verifica che il binario esista
    if not os.path.exists(binary_path):
        raise FileNotFoundError(f"Grayscale binary not found: {binary_path}")

    while True:
        # 1. Ricevi messaggio dalla coda
        got = _recv(qurl)
        if not got: 
            continue
            
        rh, body = got
        client_id = body["client_id"]
        job_id = body.get("job_id", "unknown")
        pacs = body["pacs"]
        
        # Parametri specifici del job (opzionali)
        job_threads = body.get("threads", default_threads)
        job_passes = body.get("passes", default_passes)
        
        print(f"[grayscale] Processing job {job_id} for client {client_id}")
        print(f"[grayscale] Threads: {job_threads}, Passes: {job_passes}")

        try:
            with tempfile.TemporaryDirectory() as tmp:
                # 2. Scarica input dal PACS
                if pacs.get("scope", "image") == "image":
                    ep = f"{pacs_base}/studies/{pacs['study_id']}/images/{pacs['series_id']}/{pacs['image_id']}"
                    r = requests.get(ep, headers={"x-api-key": pacs_key}, timeout=30)
                    r.raise_for_status()
                    url = r.json()["url"]
                    src = Path(tmp) / Path(urlparse(url).path).name
                    _download(url, src)
                    print(f"[grayscale] Downloaded input: {src}")
                else:
                    raise ValueError("Solo scope=image supportato per grayscale")

                # 3. Conversione DICOM -> PNG se necessario
                input_png = src
                original_dicom = None
                
                if _is_dicom_file(src):
                    print(f"[grayscale] Converting DICOM to PNG for processing")
                    original_dicom = src
                    input_png = Path(tmp) / f"{src.stem}_input.png"
                    if not _convert_dicom_to_png(src, input_png):
                        raise RuntimeError("Failed to convert DICOM to PNG")

                # 4. Esegui algoritmo grayscale OpenMP
                output_png = Path(tmp) / f"{input_png.stem}_grayscale.png"
                
                # Imposta threads OpenMP
                env = os.environ.copy()
                env['OMP_NUM_THREADS'] = str(job_threads)
                
                cmd = [binary_path, str(input_png), str(output_png)]
                if job_passes > 1:
                    cmd.append(str(job_passes))
                
                print(f"[grayscale] Executing: {' '.join(cmd)}")
                start_time = time.time()
                
                result = subprocess.run(cmd, check=True, capture_output=True, text=True, env=env)
                
                processing_time = time.time() - start_time
                print(f"[grayscale] Processing completed in {processing_time:.4f}s")
                print(f"[grayscale] Command output: {result.stdout.strip()}")
                
                if not output_png.exists():
                    raise FileNotFoundError(f"Output PNG not created: {output_png}")

                # 5. Conversione PNG -> DICOM se input era DICOM
                final_output = output_png
                if original_dicom:
                    print(f"[grayscale] Converting result back to DICOM")
                    final_output = Path(tmp) / f"{original_dicom.stem}_grayscale.dcm"
                    if not _convert_png_to_dicom(output_png, original_dicom, final_output):
                        # Fallback: usa PNG se conversione DICOM fallisce
                        print(f"[grayscale] DICOM conversion failed, using PNG output")
                        final_output = output_png

                # 6. Upload risultato su S3
                dest_key = f"{pacs['study_id']}/{pacs['series_id']}/{final_output.name}"
                s3.upload_file(str(final_output), out_bucket, dest_key)
                print(f"[grayscale] Uploaded to S3: s3://{out_bucket}/{dest_key}")

                # 7. Genera presigned URL
                presigned = s3.generate_presigned_url(
                    "get_object", 
                    Params={"Bucket": out_bucket, "Key": dest_key}, 
                    ExpiresIn=86400
                )

                # 8. Invia risultato sulla coda dei risultati
                msg = {
                    "job_id": job_id,
                    "algo_id": algo_id,
                    "client_id": client_id,
                    "dicom": {
                        "bucket": out_bucket,
                        "key": dest_key,
                        "url": presigned
                    },
                    "processing_stats": {
                        "threads": job_threads,
                        "passes": job_passes,
                        "processing_time": processing_time,
                        "input_type": "dicom" if original_dicom else "image",
                        "output_format": final_output.suffix
                    }
                }
                
                sqs.send_message(
                    QueueUrl=result_q,
                    MessageBody=json.dumps(msg),
                    MessageGroupId=job_id or "default"
                )
                
                print(f"[grayscale] Job {job_id} completed successfully")

        except Exception as e:
            print(f"[grayscale] Error processing job {job_id}: {e}")
            import traceback
            traceback.print_exc()
            
            # Invia messaggio di errore
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
            # 9. Elimina il messaggio dalla coda
            _del(qurl, rh)

if __name__ == "__main__":
    main()
