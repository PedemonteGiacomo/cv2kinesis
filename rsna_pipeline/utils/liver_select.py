# utils/liver_select.py
import numpy as np

def pick_liver_component(
        lbl,
        img_shape,
        min_area: int = 20_000,
        side: str = "left",
        *,
        max_cx: float | None = None,   # nuovo ➜ opzionale
        max_roundness: float | None = None,   # facoltativo
        **kwargs                       # cattura altri parametri futuri
    ):
    """
    Restituisce l’ID della label che più probabilmente è fegato.
    Parametri nuovi (facoltativi):
      • max_cx         – valore max di cx ammesso se side == 'left'
      • max_roundness  – esclude blob troppo “filiformi” (4πA / P² < soglia)
    Gli argomenti extra vengono ignorati = full backward‑compat.
    """
    h, w = img_shape
    best_lab, best_area = None, 0

    for lab in range(1, lbl.max() + 1):
        ys, xs = np.where(lbl == lab)
        area = len(xs)
        if area < min_area:
            continue

        cx, cy = xs.mean() / w, ys.mean() / h
        if side == "left" and max_cx is not None and cx > max_cx:
            continue
        if side == "right" and max_cx is not None and cx < (1 - max_cx):
            continue
        if cy > 0.70:                              # troppo in basso → intestino
            continue

        # rotondità opzionale
        if max_roundness is not None:
            # perimetro stimato con marching‑squares 4‑conn
            perim = np.count_nonzero(np.diff(lbl == lab, axis=0)) \
                    + np.count_nonzero(np.diff(lbl == lab, axis=1))
            roundness = (4 * np.pi * area) / (perim ** 2 + 1e-6)
            if roundness < max_roundness:
                continue

        if area > best_area:
            best_lab, best_area = lab, area

    return best_lab
