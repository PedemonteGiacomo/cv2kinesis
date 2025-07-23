# processing/threshold_ccl.py       – ALGO_ID = "processing_1"
from __future__ import annotations
import numpy as np, cv2, scipy.ndimage as ndi
from skimage.morphology import (
    disk, binary_closing, binary_opening, remove_small_holes
)
from scipy.ndimage import binary_fill_holes, generate_binary_structure
from .base import Processor
from utils.liver_select import pick_liver_component


class ThresholdCCL(Processor):
    """
    Segmentazione 2‑D del fegato (variant “simple‑style”)
    ----------------------------------------------------
      1) finestra soft‑tissue 0‑150 HU  → 8‑bit
      2) smoothing gauss
      3) threshold (fixed o Otsu)
      4) closing ↓   opening ↑   fill‑holes
      5) connected‑components + heuristics
    """

    ALGO_ID = "processing_1"

    def __init__(
        self,
        sigma: float = 1.5,
        threshold: int | None = None,      # se None usa Otsu
        min_area_px: int = 20_000,
        side: str   = "left",
        close_k: int = 7,
        open_k : int = 5,                  # raggio opening per rompere ponti
        max_cx: float = 0.55,              # cx max per fegato (radiological LHS)
    ):
        self.sigma      = sigma
        self.threshold  = threshold
        self.min_area   = min_area_px
        self.side       = side
        self.close_k    = close_k
        self.open_k     = open_k
        self.max_cx     = max_cx

    # ----------------------------------------------------
    def run(self, img, meta=None):
        if img.ndim != 2:
            raise ValueError("Serve una slice 2‑D in HU")

        # 1) window → 8‑bit
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

        # 4) morfologia
        mask = binary_closing(mask, disk(self.close_k))
        mask = binary_fill_holes(mask)
        mask = binary_opening(mask, disk(self.open_k))
        mask = remove_small_holes(mask, area_threshold=1_000)

        # 5) CCL + scelta fegato
        lbl, _ = ndi.label(mask)
        best = pick_liver_component(
            lbl, img.shape,
            min_area=self.min_area,
            side=self.side,
            max_cx=self.max_cx,         # nuovo filtro laterale
        )

        if best is None:
            return {"mask": np.zeros_like(img, np.uint8),
                    "labels": lbl.astype(np.int32),
                    "meta": {"msg": "liver not found"}}

        liver_mask = (lbl == best).astype(np.uint8)

        return {
            "mask": liver_mask,
            "labels": lbl.astype(np.int32),
            "meta": {
                "sigma"    : self.sigma,
                "thr"      : self.threshold,
                "area_px"  : int(liver_mask.sum()),
                "label_id" : int(best),
            },
        }
