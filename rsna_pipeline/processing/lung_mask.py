from __future__ import annotations

import numpy as np
import cv2
from scipy import ndimage as ndi

from .base import Processor

class LungMask(Processor):
    ALGO_ID = "processing_4"

    def __init__(self, air_thr: int = 200,
                 keep_n: int = 2, close_k: int = 7):
        self.air_thr, self.keep_n, self.close_k = air_thr, keep_n, close_k

    def run(self, img, meta=None):
        # 1. portiamo a 8‑bit e invertiamo
        img8  = cv2.equalizeHist(
                (cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX)
                 .astype(np.uint8)))
        inv   = cv2.bitwise_not(img8)

        # 2. threshold sull’aria
        mask  = (inv > self.air_thr).astype(np.uint8)

        # 3. CCL e prendiamo le 2 aree maggiori
        lbl, num, stats, cent = cv2.connectedComponentsWithStats(mask)
        big = np.argsort(stats[1:, cv2.CC_STAT_AREA])[-self.keep_n:] + 1
        mask = np.isin(lbl, big).astype(np.uint8)

        # 4. closing per riempire
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                      (self.close_k, self.close_k))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k, iterations=2)

        # Ensure mask shape matches img shape
        if mask.shape != img.shape:
            mask = cv2.resize(mask, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_NEAREST)

        lbl, _ = ndi.label(mask)
        return {"mask": mask, "labels": lbl.astype(np.int32),
                "meta": {"air_thr": self.air_thr,
                         "components": int(lbl.max())}}
