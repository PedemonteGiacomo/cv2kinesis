from __future__ import annotations

from pathlib import Path

import numpy as np
import pydicom


def load_dicom(path: str | Path) -> tuple[np.ndarray, pydicom.Dataset]:
    """Load a DICOM file and return the pixel data in HU and the full DICOM dataset."""
    ds = pydicom.dcmread(str(path))
    img = ds.pixel_array.astype(np.int16)

    slope = getattr(ds, "RescaleSlope", 1.0)
    intercept = getattr(ds, "RescaleIntercept", 0.0)
    img = img * slope + intercept

    return img, ds
