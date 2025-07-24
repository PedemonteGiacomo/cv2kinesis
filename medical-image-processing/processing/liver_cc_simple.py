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

        from utils.liver_select import pick_liver_component
        from utils.morpho import postprocess_mask

        mask = postprocess_mask(mask.astype(bool), close_r=self.close_k, dims=2)
        lbl, num = ndi.label(mask)
        best = pick_liver_component(lbl, img.shape, min_area=self.min_area, side=self.side)
        if best is None:
            return {
                "mask": np.zeros_like(img, np.uint8),
                "labels": lbl.astype(np.int32),
                "meta": {"msg": "liver not found"},
            }
        liver_mask = (lbl == best).astype(np.uint8)
        return {
            "mask": liver_mask,
            "labels": lbl.astype(np.int32),
            "meta": {
                "thr": self.thr,
                "area_px": int((lbl == best).sum()),
                "label_id": int(best),
                "components": lbl.max(),
            },
        }
