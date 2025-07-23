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

proc = LiverSegment(wl=50, ww=400, erode_iter=1, min_vol_px=20000)    # tweak params here
res = proc.run(vol)
print("META:", res["meta"])
mask3d = res["mask"]

# salviamo overlay su 5 slice centrali
mid = len(vol)//2
for i, idx in enumerate(range(mid-2, mid+3)):
    ov = overlay_mask(vol[idx], mask3d[idx])
    cv2.imshow(f"slice {idx}", ov)
    cv2.waitKey(0)   # premi un tasto per passare al successivo
cv2.destroyAllWindows()
print("meta:", res["meta"])
