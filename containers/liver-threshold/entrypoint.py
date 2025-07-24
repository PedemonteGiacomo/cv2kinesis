import argparse
import numpy as np
import os
from pathlib import Path

import pydicom
import processing  # noqa: F401
from processing.base import Processor
from utils.dicom_io import load_dicom
from utils.dicom_writer import save_secondary_capture


def parse():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--algo", required=False, default=os.getenv("ALGO_ID", "processing_1")
    )
    ap.add_argument(
        "--input", required=True, help="file.dcm  o  cartella con .dcm (serie)"
    )
    ap.add_argument("--output", required=True, help="output folder")
    return ap.parse_args()


def load_series(folder: Path):
    ds_list = sorted(
        folder.glob("*.dcm"),
        key=lambda p: pydicom.dcmread(p).InstanceNumber,
    )
    vols = [load_dicom(p)[0] for p in ds_list]
    return np.stack(vols, axis=0), pydicom.dcmread(ds_list[0])


def main():
    args = parse()
    in_path = Path(args.input)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    if in_path.is_dir():
        img, src_ds = load_series(in_path)
        is_series = True
    else:
        img, src_ds = load_dicom(in_path)
        is_series = False

    proc = Processor.factory(args.algo)
    res = proc.run(img)

    mask_u8 = (res["mask"] > 0).astype(np.uint8) * 255
    save_secondary_capture(
        mask_u8,
        src_ds,
        out_dir / f"{in_path.stem if not is_series else in_path.name}_{args.algo}.dcm",
        algo_id=args.algo,
        is_series=is_series,
    )
    print("Done.")


if __name__ == "__main__":
    main()
