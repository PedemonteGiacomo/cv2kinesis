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
    args = parse()
    s3 = boto3.client("s3")

    with tempfile.TemporaryDirectory() as tmp:
        pacs_info = json.loads(os.environ["PACS_INFO"])
        files = _get_presigned_from_pacs(pacs_info)
        if len(files) == 1:
            dst = Path(tmp) / Path(urlparse(files[0]["url"]).path).name
            _download(files[0]["url"], dst)
            img, src_ds = load_dicom(dst)
            is_series = False
            base_name = Path(dst).stem
        else:
            series_dir = Path(tmp) / "series"
            series_dir.mkdir()
            for f in files:
                _download(f["url"], series_dir / Path(urlparse(f["url"]).path).name)
            img, src_ds = load_series(series_dir)
            is_series = True
            base_name = pacs_info.get("series_id", str(uuid.uuid4()))

        proc = Processor.factory(args.algo)
        res = proc.run(img)
        mask_u8 = (res["mask"] > 0).astype(np.uint8) * 255

        out_name = f"{base_name}_{args.algo}.dcm"
        out_path = Path(tmp) / out_name
        save_secondary_capture(
            mask_u8, src_ds, out_path, algo_id=args.algo, is_series=is_series
        )

        dest_key = f"{args.job_id}/{out_name}"
        s3.upload_file(str(out_path), args.s3_output, dest_key)

        result_queue = os.getenv("RESULT_QUEUE")
        if result_queue:
            sqs = boto3.client("sqs")
            sqs.send_message(
                QueueUrl=result_queue,
                MessageBody=json.dumps(
                    {
                        "job_id": args.job_id,
                        "bucket": args.s3_output,
                        "key": dest_key,
                    }
                ),
                MessageGroupId="results",
            )


if __name__ == "__main__":
    main()
