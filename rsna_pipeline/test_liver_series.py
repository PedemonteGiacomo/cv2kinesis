from pathlib import Path
import numpy as np, cv2, pydicom, tqdm
from processing.liver_segment import LiverSegment
from utils.viz import overlay_mask
from utils.dicom_io import load_dicom

series_dir = Path(r"data/liver/abdomen-lesion-dataset-phantomx/phantomx_abdomen_lesion_dataset/D53-03/40/6_120_40_BODY-SHARP_AICE_170641.498")  # cambia path
dcm_files = sorted(series_dir.glob("*.dcm"))
vol = []
for fp in tqdm.tqdm(dcm_files, desc="Load"):
    vol.append(load_dicom(fp)[0])
vol = np.stack(vol)      # shape (Z,H,W)

proc = LiverSegment(
        wl=60, ww=500,      # finestra leggermente più ampia
        erode_iter=2,       # stacca bene il fegato
        min_vol_px=50000,   # ignora blob piccoli
        se2d=7)             # closing più forte
res = proc.run(vol)
print("META:", res["meta"])
mask3d = res["mask"]

# mostra solo le slice dove la mask ha pixel > 0
idx_with_mask = np.where(mask3d.any(axis=(1,2)))[0]
print(f"Slice con maschera: {idx_with_mask[:10]} ...")

for idx in idx_with_mask:
    ov = overlay_mask(vol[idx], mask3d[idx])
    cv2.imshow(f"slice {idx}", ov)
    if cv2.waitKey(0) == 27:   # ESC per uscire
        break
cv2.destroyAllWindows()

print("meta:", res["meta"])
