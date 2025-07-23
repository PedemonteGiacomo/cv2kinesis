"""
Algoritmo classico (no‑AI) per la segmentazione grossolana del fegato
in CT addome.  Funziona su singole slice 2‑D *oppure* sull’intero volume
3‑D (consigliato: passare uno stack numpy shape (Z,H,W)).
Steps:
    1) Soft‑tissue window  (WL 50, WW 400)  → 8‑bit
    2) Multi‑Otsu 3 classi:   [air | soft | bone]
    3) Maschera tessuti molli  →   erode(1)  → CCL
    4) Scarta componenti che toccano bordo.   Prendi la più grande
       con centroid_x > 0.55*W   &   centroid_y < 0.6*H   (= fegato)
    5) Dilata(1) + closing per ricostruire il bordo.
"""

from __future__ import annotations
import numpy as np, cv2, scipy.ndimage as ndi
from skimage.filters import threshold_multiotsu
from skimage.segmentation import clear_border
from skimage.morphology import binary_closing, ball, disk
from .base import Processor


class LiverSegment(Processor):
    ALGO_ID = "processing_5"

    def __init__(self,
                 wl: int = 50, ww: int = 400,
                 erode_iter: int = 1,
                 min_vol_px: int = 40_000,        # min area/vol to keep
                 se2d: int = 5):                  # disk radius for closing
        self.wl, self.ww = wl, ww
        self.erode_iter = erode_iter
        self.min_vol_px = min_vol_px
        self.se2d = se2d

    # -------------- helpers ---------------------------------------------
    def _window(self, img: np.ndarray) -> np.ndarray:
        lo, hi = self.wl - self.ww // 2, self.wl + self.ww // 2
        img = np.clip(img, lo, hi)
        return ((img - lo) / self.ww * 255).astype(np.uint8)

    def _largest_internal(self, lbl, stats, h, w):
        cand = []
        for i, s in enumerate(stats[1:], start=1):
            area = s[cv2.CC_STAT_AREA]
            if area < self.min_vol_px:
                continue
            cx = (s[cv2.CC_STAT_LEFT] + s[cv2.CC_STAT_WIDTH] / 2) / w
            cy = (s[cv2.CC_STAT_TOP]  + s[cv2.CC_STAT_HEIGHT] / 2) / h
            # lato sinistro nell'immagine (radiological view) → cx < 0.45
            if cx > 0.45 or cy > 0.6:
                continue

            cand.append((i, area))
        if not cand:
            print("DEBUG componenti trovate:", [(i, s[cv2.CC_STAT_AREA]) for i,s in enumerate(stats[1:],1)])
            return None
        cand.sort(key=lambda x: x[1], reverse=True)
        return cand[0][0]

    # -------------- main -------------------------------------------------
    def run(self, img: np.ndarray, meta: dict | None = None) -> dict:
        vol = img.copy()
        is_3d = vol.ndim == 3
        # A) window & multi‑Otsu
        vol8 = self._window(vol)
        thr1, thr2 = threshold_multiotsu(vol8, classes=3)
        print("DEBUG thr1,thr2:", thr1, thr2)
        soft = (vol8 >= thr1) & (vol8 < thr2)      # tessuti molli

        # B) morfologia / erosione
        se = ball(1) if is_3d else disk(1)
        mask = ndi.binary_erosion(soft, structure=se, iterations=self.erode_iter)

        # C) CCL
        structure = np.ones((3, 3, 3)) if is_3d else np.ones((3, 3))
        lbl, n = ndi.label(mask, structure=structure)
        # clear border in 2‑D slice‑wise OR full volume
        if is_3d:
            # rimuove voxel che toccano bordo volume
            edge = np.zeros_like(lbl, bool)
            edge[[0, -1], :, :] = True
            edge[:, [0, -1], :] = True
            edge[:, :, [0, -1]] = True
            border_ids = np.unique(lbl[edge])
            for bid in border_ids:
                lbl[lbl == bid] = 0
        else:
            lbl = clear_border(lbl)

        # D) pick liver component
        h, w = vol.shape[-2:]
        stats = cv2.connectedComponentsWithStats(
            lbl.astype(np.uint8) if not is_3d else
            lbl.max(axis=0).astype(np.uint8))[2]  # 2‑D stats proxy
        lid = self._largest_internal(lbl, stats, h, w)
        if lid is None:
            return {"mask": np.zeros_like(vol, bool),
                    "labels": np.zeros_like(vol, int),
                    "meta": {"msg": "liver not found"}}

        mask = (lbl == lid)

        # E) dilata + closing
        se_close = ball(self.se2d) if is_3d else disk(self.se2d)
        mask = ndi.binary_dilation(mask, structure=se_close, iterations=self.erode_iter)
        mask = binary_closing(mask, footprint=se_close)

        labels, num = ndi.label(mask, structure=structure)
        return {"mask": mask.astype(np.uint8),
                "labels": labels.astype(np.int32),
                "meta": {"thr1": int(thr1), "thr2": int(thr2),
                         "erosion": self.erode_iter,
                         "components": int(num)}}
