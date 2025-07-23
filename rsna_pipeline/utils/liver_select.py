# utils/liver_select.py
import numpy as np
import scipy.ndimage as ndi

def pick_liver_component(lbl, img_shape, min_area=20_000, side="left"):
    """
    Ritorna l'ID della label che più probabilmente è fegato.
    - lbl        : array int   (output di ndi.label)
    - img_shape  : (H,W)
    - side       : 'left'  = lato sinistro radiologico
                   'right' = lato destro (per TC con orientamenti diversi)
    """
    h, w = img_shape
    best_lab, best_area = None, 0

    for lab in range(1, lbl.max() + 1):
        area = (lbl == lab).sum()
        if area < min_area:
            continue

        ys, xs = np.where(lbl == lab)
        cx, cy = xs.mean() / w, ys.mean() / h

        # heuristics: mantiene solo il quadrante corretto
        if side == "left"  and cx > 0.55: continue   # troppo a dx → milza
        if side == "right" and cx < 0.45: continue
        if cy > 0.70:                       continue  # troppo in basso → intestino

        if area > best_area:
            best_lab, best_area = lab, area

    return best_lab
