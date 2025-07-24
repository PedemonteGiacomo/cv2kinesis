from __future__ import annotations

import argparse
import tempfile
from pathlib import Path
import zipfile
import os

import boto3
import numpy as np
import pydicom

from medical_image_processing import processing  # noqa: F401
from medical_image_processing.processing.base import Processor
from medical_image_processing.utils.dicom_io import load_dicom
from medical_image_processing.utils.dicom_writer import save_secondary_capture


def parse() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--s3-input", required=True)
    ap.add_argument("--s3-output", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--algo", required=True)
    ap.add_argument("--job-id", required=True)
    return ap.parse_args()


def load_series(folder: Path):
    files = sorted(
        folder.glob("*.dcm"), key=lambda p: pydicom.dcmread(p).InstanceNumber
    )
    vols = [load_dicom(p)[0] for p in files]
    return np.stack(vols, axis=0), pydicom.dcmread(files[0])


def main() -> None:
    args = parse()
    endpoint = os.getenv("AWS_ENDPOINT_URL")
    s3 = boto3.client("s3", endpoint_url=endpoint)
    sqs = boto3.client("sqs", endpoint_url=endpoint)

    with tempfile.TemporaryDirectory() as tmp:
        local = Path(tmp) / Path(args.key).name
        s3.download_file(args.s3_input, args.key, str(local))

        if local.suffix.lower() == ".zip":
            unzip_dir = Path(tmp) / "series"
            unzip_dir.mkdir()
            with zipfile.ZipFile(local, "r") as zf:
                zf.extractall(unzip_dir)
            img, src_ds = load_series(unzip_dir)
            is_series = True
        else:
            img, src_ds = load_dicom(local)
            is_series = False

        proc = Processor.factory(args.algo)
        res = proc.run(img)
        mask_u8 = (res["mask"] > 0).astype(np.uint8) * 255

        out_name = f"{Path(args.key).stem}_{args.algo}.dcm"
        out_path = Path(tmp) / out_name
        save_secondary_capture(
            mask_u8, src_ds, out_path, algo_id=args.algo, is_series=is_series
        )

        dest_key = f"{args.job_id}/{out_name}"
        s3.upload_file(str(out_path), args.s3_output, dest_key)


if __name__ == "__main__":
    main()
