# processing/liver_cc_simple.py          ALGO_ID = "processing_6"
from __future__ import annotations
import numpy as np, cv2, scipy.ndimage as ndi
from skimage.morphology import binary_closing, disk
from .base import Processor


class LiverCCSimple(Processor):
    """
    Segmentazione 2‑D del fegato in stile notebook:
      1) Median filter
      2) Threshold HU > thr
      3) Binary closing
      4) Connected components
      5) Scelta componente più grande con heuristica di posizione
    """

    ALGO_ID = "processing_6"

    def __init__(self,
                 thr: int = 110,          # threshold HU
                 median_k: int = 9,       # kernel mediana (pixel)
                 close_k: int = 7,        # raggio closing
                 min_area_px: int = 20_000,
                 side: str = "left"):     # 'left' (radiological) o 'right'
        self.thr = thr
        self.med_k = median_k
        self.close_k = close_k
        self.min_area = min_area_px
        self.side = side

    # -------------- main --------------
    def run(self, img: np.ndarray, meta: dict | None = None) -> dict:
        if img.ndim != 2:
            raise ValueError("Questa versione semplice gestisce solo slice 2‑D.")

        # 1) median filter
        smooth = ndi.median_filter(img, size=self.med_k)

        # 2) threshold
        mask = smooth > self.thr

        # 3) binary closing
        mask = binary_closing(mask, footprint=disk(self.close_k))

        # 4) CCL
        lbl, num = ndi.label(mask)
        if num == 0:
            return {"mask": np.zeros_like(img, np.uint8),
                    "labels": np.zeros_like(img, int),
                    "meta": {"msg": "no components"}}

        # 5) scegli la componente “feasible”
        h, w = img.shape
        best_lab, best_area = None, 0
        for lab in range(1, num + 1):
            area = (lbl == lab).sum()
            if area < self.min_area:
                continue
            # baricentro per evitare milza
            ys, xs = np.where(lbl == lab)
            cx, cy = xs.mean() / w, ys.mean() / h
            if self.side == "left" and cx > 0.55:
                continue
            if self.side == "right" and cx < 0.45:
                continue
            if cy > 0.70:    # troppo in basso -> intestino
                continue
            if area > best_area:
                best_lab, best_area = lab, area

        if best_lab is None:
            return {"mask": np.zeros_like(img, np.uint8),
                    "labels": np.zeros_like(img, int),
                    "meta": {"msg": "liver not found"}}

        liver_mask = (lbl == best_lab).astype(np.uint8)

        return {
            "mask": liver_mask,
            "labels": lbl.astype(np.int32),
            "meta": {
                "thr": self.thr,
                "area_px": int(best_area),
                "label_id": int(best_lab),
                "components": int(num)
            }
        }
