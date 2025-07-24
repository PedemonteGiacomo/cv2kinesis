from __future__ import annotations

import cv2
import matplotlib.pyplot as plt
import numpy as np


def overlay_mask(
    img: np.ndarray,
    mask: np.ndarray,
    alpha: float = 0.4,
    color: tuple[int, int, int] = (255, 0, 255),
) -> np.ndarray:
    """Overlay a binary mask on an 8-bit image."""
    if img.dtype != np.uint8:
        img8 = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    else:
        img8 = img.copy()

    if len(img8.shape) == 2:
        img_rgb = cv2.cvtColor(img8, cv2.COLOR_GRAY2BGR)
    else:
        img_rgb = img8

    overlay = img_rgb.copy()
    overlay[mask > 0] = color
    out = cv2.addWeighted(overlay, alpha, img_rgb, 1 - alpha, 0)
    return out


def show_overlay(img: np.ndarray, mask: np.ndarray, title: str = "Overlay") -> None:
    """Display the mask overlay using matplotlib."""
    plt.imshow(overlay_mask(img, mask[..., 0] if mask.ndim == 3 else mask))
    plt.title(title)
    plt.axis("off")
    plt.show()
