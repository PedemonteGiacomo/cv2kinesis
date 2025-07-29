from __future__ import annotations

import numpy as np
import scipy.ndimage as ndi
from skimage.filters import threshold_otsu
from skimage.segmentation import clear_border
from skimage.morphology import remove_small_objects, binary_closing, disk

from .base import Processor


class OtsuBorder(Processor):
    """Connected component segmentation using Otsu and morphology."""

    ALGO_ID = "processing_3"

    def __init__(
        self, sigma: float = 1.0, min_size_px: int = 200, closing_radius: int = 5
    ) -> None:
        self.sigma = sigma
        self.min_size = min_size_px
        self.radius = closing_radius

    def run(self, img: np.ndarray, meta: dict | None = None) -> dict:
        """Return mask and labels after Otsu and morphological cleanup."""
        if self.sigma > 0:
            img_smooth = ndi.gaussian_filter(img, self.sigma)
        else:
            img_smooth = img

        thr = threshold_otsu(img_smooth)
        mask = img_smooth > thr

        mask = clear_border(mask)
        mask = remove_small_objects(mask, min_size=self.min_size)
        mask = binary_closing(mask, footprint=disk(self.radius))
        from medical_image_processing.utils.liver_select import pick_liver_component
        from medical_image_processing.utils.morpho import postprocess_mask

        mask = postprocess_mask(mask.astype(bool), close_r=3, dims=2)
        lbl, num = ndi.label(mask)
        best = pick_liver_component(lbl, img.shape, min_area=20_000, side="left")
        if best is None:
            return {
                "mask": np.zeros_like(img, np.uint8),
                "labels": lbl.astype(np.int32),
                "meta": {"msg": "liver not found"},
            }
        mask = (lbl == best).astype(np.uint8)
        return {
            "mask": mask,
            "labels": lbl.astype(np.int32),
            "meta": {
                "sigma": self.sigma,
                "otsu_thr": float(thr),
                "min_size": self.min_size,
                "closing_r": self.radius,
                "components": lbl.max(),
            },
        }
