Kinase Wave‑0 prototype – DICOM lung segmentation (v2)
=====================================================
Adds **validation split, BCE+Dice loss, early‑stopping, best‑model save** and
optional **learning‑curve plots** (loss + Dice) to the original script.

Run modes
---------
* **Training**
  ```bash
  python kinase_wave0.py train --data-dir data/stage_2_train_images --mask-dir rsna-masks --epochs 50 --batch-size 4 --lr 1e-4 --val-split 0.2 --patience 3 --plot
  ```
* **Inference**
   ```bash
    $sample = (Get-ChildItem data\stage_2_train_images | Select-Object -First 1).Name
    python kinase_wave0.py infer `
        --dcm-path data\stage_2_train_images\$sample `
        --model-path model.pth `
        --out-dcm demo_overlay.dcm
   ```

Dependencies (additions)
------------------------
- matplotlib>=3.5  → for plots
- pandas, opencv-python (only for build_masks.py)

Install all:
```bash
pip install -m requirements.txt
```