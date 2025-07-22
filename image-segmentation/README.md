Kinase Wave‑0 prototype – DICOM lung segmentation
-------------------------------------------------
Run this single script in two modes:

1. **Training**
   ```bash
   python kinase_wave0.py train \
       --data-dir ./rsna-dicom \
       --mask-dir ./rsna-masks \
       --epochs 10 \
       --lr 1e-4 \
       --batch-size 4 \
       --model-out model.pth
   ```
   *Assumes you have extracted the RSNA Pneumonia Challenge dataset and
   generated corresponding binary lung‑mask PNGs (1 for foreground, 0 for
   background) in `--mask-dir` with the **same file name** as the source
   DICOM but `.png` extension.*

2. **Inference**
   ```bash
   python kinase_wave0.py infer \
       --dcm-path sample.dcm \
       --model-path model.pth \
       --out-dcm sample_overlay.dcm
   ```

The script reads a DICOM, produces a segmentation mask with a lightweight
U‑Net, blends it onto the original image (red overlay), and writes a new
**Secondary Capture RGB DICOM** retaining all key metadata.

Dependencies
------------
- torch
- torchvision
- pydicom
- numpy, pillow, tqdm
Install with `pip install torch torchvision pydicom pillow tqdm`.