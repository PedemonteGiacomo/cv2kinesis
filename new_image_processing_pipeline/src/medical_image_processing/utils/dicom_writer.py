from __future__ import annotations

import numpy as np
import pydicom
from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import (
    SecondaryCaptureImageStorage,
    generate_uid,
    ExplicitVRLittleEndian,
    PYDICOM_IMPLEMENTATION_UID,
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
    """Save a mask or RGB overlay as a Secondary Capture DICOM."""
    now = datetime.utcnow()
    ds = FileDataset(out_path, {}, file_meta=Dataset(), preamble=b"\0" * 128)
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.file_meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
    ds.file_meta.MediaStorageSOPInstanceUID = generate_uid()
    ds.file_meta.ImplementationClassUID = PYDICOM_IMPLEMENTATION_UID

    # Copia i tag necessari del paziente/studio
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

    # Pixel data: support mono o RGB
    if img.ndim == 2:
        # maschera monocromatica
        ds.SamplesPerPixel = 1
        ds.PhotometricInterpretation = "MONOCHROME2"
        ds.Rows, ds.Columns = img.shape
        pixel_bytes = img.astype(np.uint8).tobytes()
    elif img.ndim == 3 and img.shape[2] == 3:
        # overlay RGB
        ds.SamplesPerPixel = 3
        ds.PhotometricInterpretation = "RGB"
        ds.Rows, ds.Columns, _ = img.shape
        # il DICOM RGB richiede interleaving R0,G0,B0, R1,G1,B1, …
        pixel_bytes = img.astype(np.uint8).tobytes()
    else:
        raise ValueError("save_secondary_capture: img deve essere 2D o RGB 3D")

    ds.BitsAllocated = 8
    ds.BitsStored = 8
    ds.HighBit = 7
    ds.PixelRepresentation = 0
    ds.PlanarConfiguration = 0  # RGB interleaved
    ds.PixelData = pixel_bytes

    # Provenienza
    ds.add_new(0x00181030, "LO", f"Post-processed with {algo_id}")

    ds.save_as(out_path, write_like_original=False)
