# utils/morpho.py
from scipy.ndimage import binary_fill_holes, binary_closing, generate_binary_structure

def postprocess_mask(mask, close_r=3, dims=2):
    if dims == 3:
        struct = generate_binary_structure(3, 1)
    else:
        struct = generate_binary_structure(2, 1)
    mask = binary_closing(mask, structure=struct, iterations=close_r)
    mask = binary_fill_holes(mask)
    return mask
