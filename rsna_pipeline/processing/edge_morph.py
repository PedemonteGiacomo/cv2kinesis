# processing/edge_morph.py  ―  ALGO_ID = "processing_2"
from __future__ import annotations

import numpy as np
import cv2
import scipy.ndimage as ndi
from skimage.filters import threshold_otsu

from .base import Processor


class EdgeMorph(Processor):
    """Segmentazione adattativa dei polmoni su CXR."""

    ALGO_ID = "processing_2"

    def __init__(
        self,
        window_center: int = -600,
        window_width: int = 1500,
        clip_limit: float = 2.0,
        min_blob_px: int = 30_000,      # ≈ 3% di CXR 1024²
        closing_kernel: int = 7,
        max_iters: int = 5,             # quante volte abbassare la soglia
        thr_step: int = 15,             # quanto abbassarla ogni iterazione
    ):
        self.wc, self.ww = window_center, window_width
        self.clip_limit = clip_limit
        self.min_blob = min_blob_px
        self.close_k = closing_kernel
        self.max_iters = max_iters
        self.thr_step = thr_step

    # ---------- utility --------------------------------------------------

    def _to_8bit(self, img16: np.ndarray) -> np.ndarray:
        lo = self.wc - self.ww // 2
        hi = self.wc + self.ww // 2
        w = np.clip(img16, lo, hi)
        return ((w - lo) / self.ww * 255).astype(np.uint8)

    def _largest_blobs(self, lbl: np.ndarray, stats, keep=2) -> np.ndarray:
        areas = stats[1:, cv2.CC_STAT_AREA]
        keep_ids = (areas.argsort()[-keep:] + 1)
        return np.isin(lbl, keep_ids).astype(np.uint8)

    # ---------- main -----------------------------------------------------

    def run(self, img: np.ndarray, meta: dict | None = None) -> dict:
        # 1. HU → 8‑bit lung window
        img8 = self._to_8bit(img) if img.dtype != np.uint8 else img.copy()

        # 2. CLAHE
        eq = cv2.createCLAHE(self.clip_limit, (8, 8)).apply(img8)

        # 3. invertiamo per far risaltare l’aria
        inv = cv2.bitwise_not(eq)

        # 4. soglia adattativa
        thr = threshold_otsu(inv)
        success = False
        for i in range(self.max_iters + 1):
            _, th = cv2.threshold(inv, thr, 255, cv2.THRESH_BINARY)
            num, lbl, stats, _ = cv2.connectedComponentsWithStats(th)
            # blob abbastanza grandi?
            good = [s for s in stats[1:, cv2.CC_STAT_AREA] if s >= self.min_blob]
            if len(good) >= 2:
                success = True
                break
            thr = max(thr - self.thr_step, 0)  # abbassa la soglia e ritenta

        if not success:
            # fall‑back: restituisco maschera vuota
            return {"mask": np.zeros_like(img8, dtype=np.uint8),
                    "labels": np.zeros_like(img8, dtype=np.int32),
                    "meta": {"msg": "lung mask not found"}}

        # 5. tengo i due blob maggiori
        mask = self._largest_blobs(lbl, stats, keep=2)

        # 6. closing per riempire buchi tra coste
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                      (self.close_k, self.close_k))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k, iterations=2)

        # 7. etichette finali
        labels, n = ndi.label(mask)

        return {
            "mask": mask.astype(np.uint8),
            "labels": labels.astype(np.int32),
            "meta": {
                "otsu_thr_start": int(threshold_otsu(inv)),
                "thr_final": int(thr),
                "iterations": i,
                "num_components": int(n),
            },
        }
