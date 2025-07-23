# processing/liver_cc_simple.py          ALGO_ID = "processing_6"
from __future__ import annotations
import numpy as np, cv2, scipy.ndimage as ndi
from skimage.morphology import binary_closing, disk
from scipy.ndimage import (
    binary_fill_holes,
    binary_opening,
    generate_binary_structure,
)

from .base import Processor


class LiverCCSimple(Processor):
    """
    Segmentazione 2‑D del fegato (approccio rapido “notebook‑style”)
    ---------------------------------------------------------------
      1) Median filter (rumore)
      2) Threshold HU > thr (parenchima)
      3) Closing     (chiude fessure)
      4) Fill‑holes  (tappa cavità interne)
      5) Opening     (rimuove isole spurie piccole)
      6) Connected components + heuristica di posizione
    """

    ALGO_ID = "processing_6"

    def __init__(
        self,
        thr: int = 110,          # soglia HU
        median_k: int = 9,       # kernel mediana (px)
        close_k: int = 7,        # raggio closing
        min_area_px: int = 20_000,
        side: str = "left",      # 'left' (radiological) o 'right'
    ):
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

        # 3) binary closing (chiude solchi vascolari/bordo)
        mask = binary_closing(mask, footprint=disk(self.close_k))

        # 4) fill‑holes (tappa cavità interne)
        mask = binary_fill_holes(mask)

        # 5) tiny opening per togliere granuli isolati
        struc = generate_binary_structure(2, 1)
        mask = binary_opening(mask, structure=struc, iterations=1)

        # 6) Connected‑components
        lbl, num = ndi.label(mask)
        if num == 0:
            return {
                "mask": np.zeros_like(img, np.uint8),
                "labels": np.zeros_like(img, int),
                "meta": {"msg": "no components"},
            }

        # 7) scegli la componente “feasible” (posizione + area)
        h, w = img.shape
        best_lab, best_area = None, 0
        for lab in range(1, num + 1):
            area = (lbl == lab).sum()
            if area < self.min_area:
                continue

            ys, xs = np.where(lbl == lab)
            cx, cy = xs.mean() / w, ys.mean() / h

            # heuristics: esclude milza / parete / intestino
            if self.side == "left" and cx > 0.55:
                continue
            if self.side == "right" and cx < 0.45:
                continue
            if cy > 0.70:
                continue

            if area > best_area:
                best_lab, best_area = lab, area

        if best_lab is None:
            return {
                "mask": np.zeros_like(img, np.uint8),
                "labels": np.zeros_like(img, int),
                "meta": {"msg": "liver not found"},
            }

        liver_mask = (lbl == best_lab).astype(np.uint8)

        return {
            "mask": liver_mask,
            "labels": lbl.astype(np.int32),
            "meta": {
                "thr": self.thr,
                "area_px": int(best_area),
                "label_id": int(best_lab),
                "components": int(num),
            },
        }
