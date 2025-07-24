# test_liver_series.py
from pathlib import Path
import numpy as np
import cv2
import tqdm
from processing.liver_parenchyma import LiverParenchyma
from medical_image_processing.utils.dicom_io import load_dicom
from medical_image_processing.utils.viz import overlay_mask

series_dir = Path(
    r"data/liver/abdomen-lesion-dataset-phantomx/phantomx_abdomen_lesion_dataset/D53-03/40/6_120_40_BODY-SHARP_AICE_170641.498"
)

dcm_files = sorted(series_dir.glob("*.dcm"))
vol = np.stack([load_dicom(fp)[0] for fp in tqdm.tqdm(dcm_files, "Load")])

proc = LiverParenchyma(grow_tol=30)  # prova a 20‑30 se troppo “magro/grasso”
res = proc.run(vol)
mask = res["mask"]
print("META:", res["meta"])

# viewer basico: frecce ←/→ per scorrere
idx = np.where(mask.any(axis=(1, 2)))[0]
if len(idx) == 0:
    print("Nessuna slice con fegato!")
    quit()

cur = 0
while True:
    z = idx[cur]
    ov = overlay_mask(vol[z], mask[z])
    cv2.imshow("Liver overlay (← / → / ESC)", ov)
    k = cv2.waitKey(0)
    if k in (27, ord("q")):  # ESC
        break
    elif k == 81 and cur > 0:  # ←
        cur -= 1
    elif k == 83 and cur < len(idx) - 1:  # →
        cur += 1
cv2.destroyAllWindows()
