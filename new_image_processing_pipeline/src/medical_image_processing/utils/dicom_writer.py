from __future__ import annotations

import numpy as np
import pydicom
from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import (
    SecondaryCaptureImageStorage,
    generate_uid,
    ExplicitVRLittleEndian,
)
from datetime import datetime


def save_secondary_capture(
    img: np.ndarray,
    src_ds: pydicom.Dataset,
    out_path,
    algo_id: str,
    *,
    is_series: bool = False,
):
    """Save a mask or image as a Secondary Capture DICOM."""
    now = datetime.utcnow()
    ds = FileDataset(out_path, {}, file_meta=Dataset(), preamble=b"\0" * 128)
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.file_meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
    ds.file_meta.MediaStorageSOPInstanceUID = generate_uid()

    # ---------------- Required patient/study/serie -----------------
    for tag in (
        "PatientID",
        "PatientName",
        "StudyInstanceUID",
        "StudyDate",
        "StudyTime",
        "AccessionNumber",
    ):
        if tag in src_ds:
            ds[tag] = src_ds.data_element(tag)

    ds.SeriesInstanceUID = generate_uid()
    ds.SeriesNumber = 999
    ds.SeriesDescription = f"{algo_id} Derived"
    ds.Modality = "OT"
    ds.ImageType = r"DERIVED\\PRIMARY"
    ds.ContentDate = now.strftime("%Y%m%d")
    ds.ContentTime = now.strftime("%H%M%S.%f")

    # ---------------- Pixel data ----------------
    if img.ndim == 2:
        ds.Rows, ds.Columns = img.shape
    else:
        ds.NumberOfFrames, ds.Rows, ds.Columns = img.shape
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = ds.BitsStored = 8
    ds.HighBit = 7
    ds.PixelRepresentation = 0
    ds.PixelData = img.tobytes()

    # ---------------- Algo provenance ----------
    ds.add_new(0x00181030, "LO", f"Post-processed with {algo_id}")

    ds.save_as(out_path)
