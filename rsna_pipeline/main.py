"""Command line interface and queue consumer for the RSNA pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
from tqdm import tqdm

import processing  # noqa: F401 - ensure algorithms are registered
from processing.base import Processor
from utils.dicom_io import load_dicom
from utils.viz import overlay_mask


def process_single(dicom_path: Path, algo_id: str, out_dir: Path) -> None:
    """Process a single DICOM file and save overlay and metadata."""
    img, meta = load_dicom(dicom_path)
    processor = Processor.factory(algo_id)
    result = processor.run(img, meta)
    mask = result["mask"]
    out_dir.mkdir(parents=True, exist_ok=True)
    overlay = overlay_mask(img, mask)
    cv2.imwrite(str(out_dir / f"{dicom_path.stem}_overlay.png"), overlay)
    with open(out_dir / f"{dicom_path.stem}_meta.json", "w") as f:
        json.dump(result["meta"], f, indent=2)


def main() -> None:
    """CLI entry point."""
    ap = argparse.ArgumentParser()
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--dicom")
    group.add_argument("--folder")
    ap.add_argument(
        "--algo",
        default="processing_1",
        help="processing_1 | processing_2 | processing_3",
    )
    ap.add_argument("--out", default="output")
    args = ap.parse_args()

    out_dir = Path(args.out)
    if args.dicom:
        process_single(Path(args.dicom), args.algo, out_dir)
    else:
        dicoms = list(Path(args.folder).rglob("*.dcm"))
        for dcm in tqdm(dicoms, desc="Processing"):
            process_single(dcm, args.algo, out_dir)


if __name__ == "__main__":
    main()
