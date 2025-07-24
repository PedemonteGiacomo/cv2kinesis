# processing/threshold_ccl.py       – ALGO_ID = "processing_1"
from __future__ import annotations

import cv2
import numpy as np
import scipy.ndimage as ndi
from skimage.morphology import (
    binary_closing,
    binary_opening,
    disk,
    remove_small_holes,
)
from scipy.ndimage import binary_fill_holes
from .base import Processor
from medical_image_processing.utils.liver_select import pick_liver_component


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
        threshold: int | None = None,  # se None usa Otsu
        min_area_px: int = 20_000,
        side: str = "left",
        close_k: int = 7,
        open_k: int = 5,  # raggio opening per rompere ponti
        max_cx: float = 0.55,  # cx max per fegato (radiological LHS)
    ):
        self.sigma = sigma
        self.threshold = threshold
        self.min_area = min_area_px
        self.side = side
        self.close_k = close_k
        self.open_k = open_k
        self.max_cx = max_cx

    # ----------------------------------------------------
    def run(self, img: np.ndarray, meta: dict | None = None) -> dict:
        if img.ndim == 2:  # --- slice 2‑D ---
            return self._run_2d(img, meta)
        elif img.ndim == 3:  # --- serie 3‑D ---
            masks, slice_meta = [], []
            for z in range(img.shape[0]):
                r = self._run_2d(img[z])
                masks.append(r["mask"])
                slice_meta.append(r["meta"])
            return {
                "mask": np.stack(masks, axis=0),
                "labels": None,  # non servono per ogni slice
                "meta": {
                    "series": slice_meta,
                    "algo": self.ALGO_ID,
                },
            }
        else:
            raise ValueError("Input deve essere 2‑D (H,W) o 3‑D (Z,H,W).")

    # ---------- logica originale (leggermente refactor) ----------
    def _run_2d(self, img2d: np.ndarray, meta: dict | None = None) -> dict:
        img = img2d
        # 1) window → 8‑bit
        img_win = np.clip(img, 0, 150).astype(np.float32)
        img8 = ((img_win - 0) / 150 * 255).astype(np.uint8)

        # 2) smoothing
        if self.sigma > 0:
            img8 = ndi.gaussian_filter(img8, self.sigma)

        # 3) threshold
        if self.threshold is None:
            _, mask = cv2.threshold(img8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
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
            lbl,
            img.shape,
            min_area=self.min_area,
            side=self.side,
            max_cx=self.max_cx,  # nuovo filtro laterale
        )

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
                "sigma": self.sigma,
                "thr": self.threshold,
                "area_px": int(liver_mask.sum()),
                "label_id": int(best),
            },
        }
