# processing/threshold_ccl.py           ALGO_ID = "processing_1"
from __future__ import annotations
import numpy as np, cv2, scipy.ndimage as ndi
from skimage.morphology import disk, binary_closing
from scipy.ndimage import (
    binary_fill_holes,
    binary_opening,
    generate_binary_structure,
)

from .base import Processor
from utils.liver_select import pick_liver_component          # <‑‑ heuristics
from utils.morpho       import postprocess_mask              # closing + fill holes

class ThresholdCCL(Processor):
    """
    Segmentazione 2‑D del fegato con:
      1) Finestra [0‑150] HU  →  8‑bit
      2) Smoothing Gauss (σ)
      3) Threshold (fixed o Otsu)         → maschera “soft‑tissue”
      4) Closing + fill‑holes + opening   → pulizia
      5) Connected‑components + heuristica di posizione
    """

    ALGO_ID = "processing_1"

    def __init__(
        self,
        sigma: float = 1.5,
        threshold: int | None = None,     # HU di taglio (se None usa Otsu)
        min_area_px: int = 20_000,
        side: str = "left",               # 'left' radiological (default)
    ):
        self.sigma      = sigma
        self.threshold  = threshold
        self.min_area   = min_area_px
        self.side       = side

    # ------------------------------------------------------------
    def run(self, img: np.ndarray, meta: dict | None = None) -> dict:
        if img.ndim != 2:
            raise ValueError("Gestisce una singola slice 2‑D in HU.")

        # 1) window soft‑tissue [0,150] HU  → 8‑bit
        img_win = np.clip(img, 0, 150).astype(np.float32)
        img8    = ((img_win - 0) / 150 * 255).astype(np.uint8)

        # 2) smoothing
        if self.sigma > 0:
            img8 = ndi.gaussian_filter(img8, self.sigma)

        # 3) threshold
        if self.threshold is None:
            _, mask = cv2.threshold(img8, 0, 255,
                                    cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        else:
            mask = (img8 > self.threshold).astype(np.uint8) * 255

        mask = mask.astype(bool)

        # 4) morfologia “notebook‑style”
        mask = binary_closing(mask, footprint=disk(7))
        mask = binary_fill_holes(mask)
        mask = binary_opening(mask,
                              structure=generate_binary_structure(2, 1),
                              iterations=1)

        # 5) CCL + scelta fegato
        lbl, num = ndi.label(mask)
        best = pick_liver_component(lbl, img.shape,
                                    min_area=self.min_area,
                                    side=self.side)

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
                "sigma"     : self.sigma,
                "thr"       : self.threshold,
                "label_id"  : int(best),
                "area_px"   : int((lbl == best).sum()),
                "components": int(num),
            },
        }
