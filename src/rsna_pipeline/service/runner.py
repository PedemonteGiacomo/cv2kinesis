from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from urllib.parse import urlparse

import boto3
import numpy as np
import pydicom
import requests


import medical_image_processing.processing  # registra gli algoritmi
from medical_image_processing.processing.base import Processor
from medical_image_processing.utils.dicom_io import load_dicom
from medical_image_processing.utils.dicom_writer import save_secondary_capture
from medical_image_processing.utils.viz import overlay_mask
import cv2


def parse() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--s3-output", required=True)
    ap.add_argument("--algo", required=True)
    ap.add_argument("--job-id", required=True)
    return ap.parse_args()


def load_series(folder: Path):
    files = sorted(
        folder.glob("*.dcm"), key=lambda p: pydicom.dcmread(p).InstanceNumber
    )
    vols = [load_dicom(p)[0] for p in files]
    return np.stack(vols, axis=0), pydicom.dcmread(files[0])


def _get_presigned_from_pacs(pacs: dict[str, str]) -> list[dict]:
    base = os.environ["PACS_API_BASE"]
    
    # Fix: Ensure base URL has a scheme (http:// or https://)
    if not base.startswith(('http://', 'https://')):
        base = f"http://{base}"
        print(f"[runner] Added http scheme to PACS_API_BASE: {base}")
    
    hdrs = {"x-api-key": os.environ["PACS_API_KEY"]}
    scope = pacs.get("scope", "image")
    if scope == "image":
        # Usa lo stesso path della preview React: /studies/{study_id}/images/{series_id}/{image_id}
        ep = f"{base}/studies/{pacs['study_id']}/images/{pacs['series_id']}/{pacs['image_id']}"
        print(f"[runner] Making request to: {ep}")
        r = requests.get(ep, headers=hdrs, timeout=10)
        print(f"[runner] GET {ep} → {r.status_code}")
        r.raise_for_status()
        return [r.json()]
    if scope == "series":
        ep = f"{base}/studies/{pacs['study_id']}/images"
        print(f"[runner] Making request to: {ep}")
        r = requests.get(
            ep, headers=hdrs, timeout=10, params={"series_id": pacs["series_id"]}
        )
        print(f"[runner] GET {ep} → {r.status_code}")
        r.raise_for_status()
        return r.json()
    raise ValueError("scope non valido")


def _download(url: str, dst: Path) -> None:
    r = requests.get(url, stream=True, timeout=15)
    r.raise_for_status()
    with open(dst, "wb") as f:
        shutil.copyfileobj(r.raw, f)


def main() -> None:

    print("[runner] START")
    print(f"[runner] ENVIRONMENT: {dict(os.environ)}")
    try:
        args = parse()
        print(f"[runner] args: {args}")
        print(f"[runner] ENV: PACS_INFO={os.environ.get('PACS_INFO')}, PACS_API_BASE={os.environ.get('PACS_API_BASE')}, PACS_API_KEY={os.environ.get('PACS_API_KEY')}, CLIENT_ID={os.environ.get('CLIENT_ID')}, RESULTS_TOPIC_ARN={os.environ.get('RESULTS_TOPIC_ARN')}")
        s3 = boto3.client("s3")

        with tempfile.TemporaryDirectory() as tmp:
            print(f"[runner] tempdir: {tmp}")
            print(f"[runner] DEBUG: job_id={args.job_id}, algo={args.algo}, s3_output={args.s3_output}")
            try:
                pacs_info_raw = os.environ["PACS_INFO"]
                print(f"[runner] PACS_INFO raw: {pacs_info_raw}")
                pacs_info = json.loads(pacs_info_raw)
                print(f"[runner] PACS_INFO loaded: {pacs_info}")
            except Exception as e:
                print(f"[runner] ERROR loading PACS_INFO: {e}")
                import traceback; traceback.print_exc()
                raise

            try:
                print(f"[runner] DEBUG: calling _get_presigned_from_pacs with pacs_info={pacs_info}")
                files = _get_presigned_from_pacs(pacs_info)
                print(f"[runner] presigned files: {files}")
            except Exception as e:
                print(f"[runner] ERROR during PACS download: {e}")
                import traceback; traceback.print_exc()
                raise

            try:
                print(f"[runner] DEBUG: files to download: {files}")
                if len(files) == 1:
                    dst = Path(tmp) / Path(urlparse(files[0]["url"]).path).name
                    print(f"[runner] downloading image to {dst} from {files[0]['url']}")
                    _download(files[0]["url"], dst)
                    print(f"[runner] downloaded: {dst}")
                    img, src_ds = load_dicom(dst)
                    print(f"[runner] loaded DICOM: img shape={getattr(img, 'shape', None)}, src_ds={src_ds}")
                    is_series = False
                    base_name = Path(dst).stem
                else:
                    series_dir = Path(tmp) / "series"
                    series_dir.mkdir()
                    for f in files:
                        print(f"[runner] downloading series file: {f['url']} to {series_dir / Path(urlparse(f['url']).path).name}")
                        _download(f["url"], series_dir / Path(urlparse(f["url"]).path).name)
                    img, src_ds = load_series(series_dir)
                    print(f"[runner] loaded series: img shape={getattr(img, 'shape', None)}, src_ds={src_ds}")
                    is_series = True
                    base_name = pacs_info.get("series_id", str(uuid.uuid4()))
            except Exception as e:
                print(f"[runner] ERROR during DICOM download/parsing: {e}")
                import traceback; traceback.print_exc()
                raise

            try:
                print(f"[runner] running processor: {args.algo} on img shape={getattr(img, 'shape', None)}")
                proc = Processor.factory(args.algo)
                print(f"[runner] processor instance: {proc}")
                res = proc.run(img)
                print(f"[runner] result: {res}")
                mask = res["mask"]
                overlay = overlay_mask(img, mask)  # shape (H,W,3), dtype=uint8
                print(f"[runner] overlay shape: {getattr(overlay, 'shape', None)}")
            except Exception as e:
                print(f"[runner] ERROR during processing: {e}")
                import traceback; traceback.print_exc()
                raise

            try:
                out_name = f"{base_name}_{args.algo}.dcm"
                out_path = Path(tmp) / out_name
                print(f"[runner] saving DICOM: {out_path} (algo={args.algo}, is_series={is_series})")
                save_secondary_capture(
                    overlay,             # immagine RGB
                    src_ds,
                    out_path,
                    algo_id=args.algo,
                    is_series=is_series
                )
                print(f"[runner] DICOM saved: {out_path}")
            except Exception as e:
                print(f"[runner] ERROR during DICOM save: {e}")
                import traceback; traceback.print_exc()
                raise

            try:
                # Struttura output: study_id/series_id/image_id_processing_1.dcm
                dest_key = f"{pacs_info['study_id']}/{pacs_info['series_id']}/"
                # Sostituisci .dcm con _{args.algo}.dcm
                base_image_name = pacs_info['image_id'].replace('.dcm', f'_{args.algo}.dcm')
                dest_key = f"{dest_key}{base_image_name}"
                print(f"[runner] uploading to S3: bucket={args.s3_output} key={dest_key} file={out_path}")
                s3.upload_file(str(out_path), args.s3_output, dest_key)
                print(f"[runner] S3 upload complete: s3://{args.s3_output}/{dest_key}")
            except Exception as e:
                print(f"[runner] ERROR during S3 upload: {e}")
                import traceback; traceback.print_exc()
                raise

            try:
                presigned = s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": args.s3_output, "Key": dest_key},
                    ExpiresIn=86_400,
                )
                print(f"[runner] presigned result url: {presigned}")
            except Exception as e:
                print(f"[runner] ERROR during presigned url generation: {e}")
                import traceback; traceback.print_exc()
                raise

            try:
                # Invia direttamente in SQS sulla coda callback fornita dal client
                sqs_client = boto3.client("sqs")
                message = {
                    "job_id": args.job_id,
                    "algo_id": args.algo,
                    "dicom": {
                        "bucket": args.s3_output,
                        "key": dest_key,
                        "url": presigned,
                    },
                    "client_id": os.environ.get("CLIENT_ID", "unknown")
                }
                print(f"[runner] sending result to SQS: {os.environ['RESULT_QUEUE']}")
                print(f"[runner] SQS message: {json.dumps(message)}")
                resp = sqs_client.send_message(
                    QueueUrl=os.environ["RESULT_QUEUE"],
                    MessageBody=json.dumps(message),
                    MessageAttributes={
                        "client_id": {
                            "DataType": "String",
                            "StringValue": os.environ.get("CLIENT_ID","unknown")
                        }
                    },
                    MessageGroupId=args.job_id
                )
                print(f"[runner] SQS send_message response: {resp}")
            except Exception as e:
                print(f"[runner] ERROR during SQS send_message: {e}")
                import traceback; traceback.print_exc()
                raise
        print("[runner] END OK")
    except Exception as e:
        print(f"[runner] ERROR: {e}", flush=True)
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
