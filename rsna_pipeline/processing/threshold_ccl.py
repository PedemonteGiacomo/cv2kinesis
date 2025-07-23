from __future__ import annotations

import numpy as np
import cv2
import scipy.ndimage as ndi

from .base import Processor


class ThresholdCCL(Processor):
    """Medium style threshold and connected-component labeling pipeline."""

    ALGO_ID = "processing_1"

    def __init__(
        self, sigma: float = 2.0, threshold: int | None = None, min_area_px: int = 500
    ):
        self.sigma = sigma
        self.threshold = threshold
        self.min_area = min_area_px

    def run(self, img: np.ndarray, meta: dict | None = None) -> dict:
        """Return mask and labels of connected components."""

        img_win = np.clip(img, 0, 150)     # window fegato
        img8    = ((img_win - 0) / 150 * 255).astype(np.uint8)
        smoothed = ndi.gaussian_filter(img8, 1.5)

        if self.threshold is None:
            _, mask = cv2.threshold(
                smoothed.astype(np.uint8), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
            )
        else:
            mask = (smoothed > self.threshold).astype(np.uint8) * 255

        labels, num = ndi.label(mask, structure=np.ones((3, 3)))
        for lab in range(1, num + 1):
            if np.sum(labels == lab) < self.min_area:
                labels[labels == lab] = 0
        labels, _ = ndi.label(labels > 0, structure=np.ones((3, 3)))

        return {
            "mask": (labels > 0).astype(np.uint8),
            "labels": labels.astype(np.int32),
            "meta": {
                "sigma": self.sigma,
                "thr": self.threshold,
                "components": labels.max(),
            },
        }
