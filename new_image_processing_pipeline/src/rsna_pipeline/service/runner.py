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
    hdrs = {"x-api-key": os.environ["PACS_API_KEY"]}
    scope = pacs.get("scope", "image")
    if scope == "image":
        ep = f"{base}/studies/{pacs['study_id']}/images/{pacs['image_id']}"
        return [requests.get(ep, headers=hdrs, timeout=10).json()]
    if scope == "series":
        ep = f"{base}/studies/{pacs['study_id']}/images"
        return requests.get(
            ep, headers=hdrs, timeout=10, params={"series_id": pacs["series_id"]}
        ).json()
    raise ValueError("scope non valido")


def _download(url: str, dst: Path) -> None:
    r = requests.get(url, stream=True, timeout=15)
    r.raise_for_status()
    with open(dst, "wb") as f:
        shutil.copyfileobj(r.raw, f)


def main() -> None:

    print("[runner] START")
    try:
        args = parse()
        print(f"[runner] args: {args}")
        s3 = boto3.client("s3")

        with tempfile.TemporaryDirectory() as tmp:
            print(f"[runner] tempdir: {tmp}")
            pacs_info = json.loads(os.environ["PACS_INFO"])
            print(f"[runner] PACS_INFO: {pacs_info}")
            files = _get_presigned_from_pacs(pacs_info)
            print(f"[runner] presigned files: {files}")
            if len(files) == 1:
                dst = Path(tmp) / Path(urlparse(files[0]["url"]).path).name
                print(f"[runner] downloading image to {dst}")
                _download(files[0]["url"], dst)
                print(f"[runner] downloaded: {dst}")
                img, src_ds = load_dicom(dst)
                is_series = False
                base_name = Path(dst).stem
            else:
                series_dir = Path(tmp) / "series"
                series_dir.mkdir()
                for f in files:
                    print(f"[runner] downloading series file: {f['url']}")
                    _download(f["url"], series_dir / Path(urlparse(f["url"]).path).name)
                img, src_ds = load_series(series_dir)
                is_series = True
                base_name = pacs_info.get("series_id", str(uuid.uuid4()))

            print(f"[runner] running processor: {args.algo}")
            proc = Processor.factory(args.algo)
            print(f"[runner] processor instance: {proc}")
            res = proc.run(img)
            print(f"[runner] result: {res}")
            mask_u8 = (res["mask"] > 0).astype(np.uint8) * 255

            out_name = f"{base_name}_{args.algo}.dcm"
            out_path = Path(tmp) / out_name
            print(f"[runner] saving DICOM: {out_path}")
            save_secondary_capture(
                mask_u8, src_ds, out_path, algo_id=args.algo, is_series=is_series
            )

            dest_key = f"{args.job_id}/{out_name}"
            print(f"[runner] uploading to S3: bucket={args.s3_output} key={dest_key}")
            s3.upload_file(str(out_path), args.s3_output, dest_key)

            presigned = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": args.s3_output, "Key": dest_key},
                ExpiresIn=86_400,
            )
            print(f"[runner] presigned result url: {presigned}")

            if (result_q := os.getenv("RESULT_QUEUE")):
                print(f"[runner] sending result to SQS: {result_q}")
                sqs = boto3.client("sqs")
                sqs.send_message(
                    QueueUrl=result_q,
                    MessageBody=json.dumps(
                        {
                            "job_id": args.job_id,
                            "algo_id": args.algo,
                            "dicom": {
                                "bucket": args.s3_output,
                                "key": dest_key,
                                "url": presigned,
                            },
                        }
                    ),
                    MessageGroupId=args.job_id,   # FIFO ordering per job
                )
        print("[runner] END OK")
    except Exception as e:
        print(f"[runner] ERROR: {e}", flush=True)
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
