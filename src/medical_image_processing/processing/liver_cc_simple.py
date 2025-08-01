# processing/liver_cc_simple.py          ALGO_ID = "processing_6"
from __future__ import annotations

import numpy as np
import scipy.ndimage as ndi
from scipy.ndimage import binary_closing
from skimage.morphology import disk
from scipy.ndimage import binary_fill_holes, binary_opening, generate_binary_structure

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
        thr: int = 120,  # soglia HU più alta
        median_k: int = 11,  # kernel mediana più grande
        close_k: int = 9,  # raggio closing più grande
        min_area_px: int = 25_000,
        side: str = "left",  # 'left' (radiological) o 'right'
    ):
        self.thr = thr
        self.med_k = median_k
        self.close_k = close_k
        self.min_area = min_area_px
        self.side = side

    # -------------- main --------------
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
                "labels": None,
                "meta": {"series": slice_meta, "algo": self.ALGO_ID},
            }
        else:
            raise ValueError("Input deve essere 2‑D (H,W) o 3‑D (Z,H,W).")

    # ---------- logica originale (leggermente refactor) ----------
    def _run_2d(self, img2d: np.ndarray, meta: dict | None = None) -> dict:
        img = img2d

        # 1) median filter
        smooth = ndi.median_filter(img, size=self.med_k)

        # 2) threshold
        mask = smooth > self.thr

        # 3) binary closing (chiude solchi vascolari/bordo)
        footprint = disk(self.close_k)
        mask = binary_closing(mask, structure=footprint, iterations=2)

        # 4) fill‑holes (tappa cavità interne)
        mask = binary_fill_holes(mask)

        # 5) tiny opening per togliere granuli isolati
        struc = generate_binary_structure(2, 1)
        mask = binary_opening(mask, structure=struc, iterations=2)

        from medical_image_processing.utils.liver_select import pick_liver_component
        from medical_image_processing.utils.morpho import postprocess_mask

        mask = postprocess_mask(mask.astype(bool), close_r=self.close_k, dims=2)
        lbl, num = ndi.label(mask)
        best = pick_liver_component(
            lbl, img.shape, min_area=self.min_area, side=self.side
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
                "thr": self.thr,
                "area_px": int((lbl == best).sum()),
                "label_id": int(best),
                "components": lbl.max(),
            },
        }
