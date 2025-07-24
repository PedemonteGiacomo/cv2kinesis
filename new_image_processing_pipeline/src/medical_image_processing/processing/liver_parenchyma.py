# processing/liver_parenchyma.py  – ALGO_ID = "processing_5"
from __future__ import annotations
import numpy as np
import scipy.ndimage as ndi
from skimage.morphology import ball
from .base import Processor


class LiverParenchyma(Processor):
    """
    Segmentazione 3‑D del fegato in TC addome (approccio classico, no‑AI).
    """

    ALGO_ID = "processing_5"

    def __init__(
        self,
        hu_min: int = 30,
        hu_max: int = 120,  # range parenchima
        body_thr: int = -200,  # separa aria
        grow_tol: int = 25,  # ±HU dal seed
        min_liver_px: int = 35_000,  # area minima accettata
        close_r: int = 3,
    ):  # raggio closing
        self.hu_min, self.hu_max = hu_min, hu_max
        self.body_thr = body_thr
        self.grow_tol = grow_tol
        self.min_liver_px = min_liver_px
        self.close_r = close_r

    # ---------------- helpers ----------------
    def _body_mask(self, vol: np.ndarray) -> np.ndarray:
        """Maschera grossolana del corpo (tessuti > body_thr)."""
        body = vol > self.body_thr
        body = ndi.binary_closing(body, structure=ball(2))
        body = ndi.binary_fill_holes(body)
        return body

    def _seed_voxel(self, vol: np.ndarray, body: np.ndarray):
        """
        Restituisce il voxel HU‑max dentro la ROI (quadrante dx‑sup).
        Ritorna None se la ROI è vuota.
        """
        z, y, x = vol.shape
        roi_mask = np.zeros_like(body, bool)
        roi_mask[:, : y // 2, x // 2 :] = body[:, : y // 2, x // 2 :]

        if not roi_mask.any():
            return None

        masked_vol = np.where(roi_mask, vol, vol.min())
        idx = np.unravel_index(np.argmax(masked_vol), vol.shape)  # (z,y,x)
        return idx

    # ---------------- main -------------------
    def run(self, img: np.ndarray, meta: dict | None = None) -> dict:
        if img.ndim != 3:
            raise ValueError("Passa l'intero volume come array (Z,H,W).")

        vol = img.copy()
        body = self._body_mask(vol)

        # 1) candidate parenchyma (range HU)
        cand = (vol >= self.hu_min) & (vol <= self.hu_max) & body

        # 2) seed automatico
        seed_idx = self._seed_voxel(vol, cand)
        if seed_idx is None:
            return {
                "mask": np.zeros_like(vol, np.uint8),
                "labels": np.zeros_like(vol, int),
                "meta": {"msg": "seed not found"},
            }

        # 3) region‑growing (binary_propagation senza arg. 'start')
        seed_vol = np.zeros_like(body, dtype=bool)
        seed_vol[seed_idx] = True

        liver_mask = ndi.binary_propagation(
            seed_vol, structure=np.ones((3, 3, 3)), mask=body
        )

        # scarta se troppo piccolo o troppo grande (flood fallito)
        vox = liver_mask.sum()
        if vox < self.min_liver_px or liver_mask.mean() > 0.50:
            return {
                "mask": np.zeros_like(vol, np.uint8),
                "labels": np.zeros_like(vol, int),
                "meta": {"msg": "liver not found"},
            }

        # 4) post‑processing morfologico
        from medical_image_processing.utils.liver_select import pick_liver_component
        from medical_image_processing.utils.morpho import postprocess_mask

        liver_mask = postprocess_mask(
            liver_mask.astype(bool), close_r=self.close_r, dims=3
        )
        lbl, num = ndi.label(liver_mask)
        best = pick_liver_component(
            lbl, vol.shape[1:], min_area=self.min_liver_px, side="left"
        )
        if best is None:
            return {
                "mask": np.zeros_like(vol, np.uint8),
                "labels": lbl.astype(np.int32),
                "meta": {"msg": "liver not found"},
            }
        liver_mask = (lbl == best).astype(np.uint8)
        return {
            "mask": liver_mask,
            "labels": lbl.astype(np.int32),
            "meta": {
                "seed": tuple(int(i) for i in seed_idx),
                "grow_tol": self.grow_tol,
                "components": lbl.max(),
            },
        }
