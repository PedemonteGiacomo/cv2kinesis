"""
build_masks.py – RSNA Pneumonia Challenge ➜ PNG mask generator
--------------------------------------------------------------
Given the official `stage_2_train_labels.csv` and the extracted
`stage_2_train_images/*.dcm`, this script produces **binary PNG masks**
(one per DICOM) that match exactly the file‑name (Patient ID).

The mask is **white (255)** where any pneumonia bounding‑box exists and
black (0) elsewhere.  Negative studies still get a mask (all black) so
that the count of PNGs equals the count of DICOMs – important for
balanced training.

Usage (from the project root):

```powershell
python build_masks.py --csv data/stage_2_train_labels.csv --dcm-dir data/stage_2_train_images --out-dir rsna-masks
```

Dependencies: pandas, pydicom, opencv‑python, tqdm (all small; install
with `pip install pandas pydicom opencv-python tqdm`).  cv2 is used for
fast rectangle fill.
"""

import argparse
from pathlib import Path
import os

import cv2
import numpy as np
import pandas as pd
import pydicom
from tqdm.auto import tqdm


def build_masks(csv_path: Path, dcm_dir: Path, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(csv_path)

    # Group all rows by patientId for speed
    for pid, rows in tqdm(df.groupby("patientId"), total=df.patientId.nunique()):
        dcm_path = dcm_dir / f"{pid}.dcm"
        if not dcm_path.exists():
            continue  # skip if DICOM not in local subset
        ds = pydicom.dcmread(dcm_path)
        mask = np.zeros(ds.pixel_array.shape, np.uint8)
        # Draw rectangles for all positive boxes
        for _, r in rows.iterrows():
            if r["Target"] == 1:
                x, y, w, h = map(int, [r.x, r.y, r.width, r.height])
                cv2.rectangle(mask, (x, y), (x + w, y + h), 255, -1)
        cv2.imwrite(str(out_dir / f"{pid}.png"), mask)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Build binary PNG masks for RSNA DICOMs")
    p.add_argument("--csv", type=Path, required=True, help="stage_2_train_labels.csv path")
    p.add_argument("--dcm-dir", type=Path, required=True, help="Folder with *.dcm")
    p.add_argument("--out-dir", type=Path, default=Path("rsna-masks"), help="Output folder for PNG masks")
    args = p.parse_args()
    build_masks(args.csv, args.dcm_dir, args.out_dir)
    print(f"\n✓ Masks written to {args.out_dir}\n")