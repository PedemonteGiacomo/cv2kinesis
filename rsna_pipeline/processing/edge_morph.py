from __future__ import annotations

import numpy as np
import cv2

from .base import Processor


class EdgeMorph(Processor):
    """Windowing, CLAHE, Canny and morphology pipeline for chest X-rays."""

    ALGO_ID = "processing_2"

    def __init__(
        self,
        window_center: int = -600,
        window_width: int = 1500,
        clip_limit: float = 2.0,
        canny_low: int = 30,
        canny_high: int = 80,
        kernel_size: int = 5,
    ):
        self.wc, self.ww = window_center, window_width
        self.clip_limit = clip_limit
        self.canny_low, self.canny_high = canny_low, canny_high
        self.k = kernel_size

    def _lung_window(self, img: np.ndarray) -> np.ndarray:
        lo = self.wc - self.ww // 2
        hi = self.wc + self.ww // 2
        w = np.clip(img, lo, hi)
        w = ((w - lo) / self.ww * 255).astype(np.uint8)
        return w

    def run(self, img: np.ndarray, meta: dict | None = None) -> dict:
        """Return mask and connected components using edge-based approach."""
        if img.dtype != np.uint8:
            img8 = self._lung_window(img)
        else:
            img8 = img.copy()

        clahe = cv2.createCLAHE(self.clip_limit, tileGridSize=(8, 8))
        eq = clahe.apply(img8)

        _, th = cv2.threshold(eq, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (self.k, self.k))
        mask = cv2.morphologyEx(th, cv2.MORPH_OPEN, kernel, iterations=2)
        mask = cv2.dilate(mask, kernel, iterations=2)

        num_labels, labels = cv2.connectedComponents(mask)

        return {
            "mask": (labels > 0).astype(np.uint8),
            "labels": labels.astype(np.int32),
            "meta": {"num_components": num_labels - 1},
        }
