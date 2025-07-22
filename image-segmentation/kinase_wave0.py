"""
Kinase Wave‑0 prototype – DICOM lung segmentation (v2)
=====================================================
Adds **validation split, BCE+Dice loss, early‑stopping, best‑model save** and
optional **learning‑curve plots** (loss + Dice) to the original script.

Run modes
---------
* **Training**
  ```bash
  python kinase_wave0.py train \
         --data-dir  data/stage_2_train_images \
         --mask-dir  rsna-masks \
         --epochs    50              # upper bound, early‑stopping will cut at ~12
         --batch-size 4 \
         --lr        1e-4 \
         --val-split 0.2             # 20 % validation
         --patience  3               # stop if no val‑improve 3 epochs
         --plot                      # saves learning_curve_loss.png + dice.png
  ```
* **Inference**
   ```bash
   python kinase_wave0.py infer \
       --dcm-path sample.dcm \
       --model-path model.pth \
       --out-dcm sample_overlay.dcm
   ```

Dependencies (additions)
------------------------
- matplotlib>=3.5  → for plots
- pandas, opencv-python (only for build_masks.py)

Install all:
```bash
pip install torch torchvision pydicom pillow tqdm matplotlib numpy
```

"""

import argparse
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pydicom
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.transforms.functional as TF
from PIL import Image
from torch.utils.data import DataLoader, Dataset, random_split
from tqdm.auto import tqdm

# Optional plotting – imported lazily to keep startup fast
try:
    import matplotlib.pyplot as plt  # noqa: E402
except ImportError:  # plotting is optional
    plt = None

# ──────────────────────────────────────────────────────────────────────────────
# Model – minimal 4‑level U‑Net (≈7 M params)
# ──────────────────────────────────────────────────────────────────────────────

class DoubleConv(nn.Module):
    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, x):  # noqa: D401
        return self.conv(x)


class UNet(nn.Module):
    def __init__(self, in_channels: int = 1, n_classes: int = 1, features: Tuple[int] = (32, 64, 128, 256)):
        super().__init__()
        self.downs, self.ups = nn.ModuleList(), nn.ModuleList()
        # Down path
        for feat in features:
            self.downs.append(DoubleConv(in_channels, feat))
            in_channels = feat
        # Bottleneck
        self.bottleneck = DoubleConv(features[-1], features[-1] * 2)
        # Up path
        for feat in reversed(features):
            self.ups.append(nn.ConvTranspose2d(feat * 2, feat, 2, 2))
            self.ups.append(DoubleConv(feat * 2, feat))
        self.final_conv = nn.Conv2d(features[0], n_classes, 1)

    def forward(self, x):  # noqa: D401
        skip_connections: List[torch.Tensor] = []
        for down in self.downs:
            x = down(x)
            skip_connections.append(x)
            x = F.max_pool2d(x, 2)
        x = self.bottleneck(x)
        skip_connections = skip_connections[::-1]
        for idx in range(0, len(self.ups), 2):
            x = self.ups[idx](x)
            skip = skip_connections[idx // 2]
            if x.shape != skip.shape:
                x = TF.resize(x, size=skip.shape[2:])
            x = torch.cat((skip, x), dim=1)
            x = self.ups[idx + 1](x)
        return torch.sigmoid(self.final_conv(x))


# ──────────────────────────────────────────────────────────────────────────────
# Dataset loader – DICOM + PNG mask
# ──────────────────────────────────────────────────────────────────────────────

class RsnaDicomDataset(Dataset):
    def __init__(self, dcm_dir: Path, mask_dir: Path):
        self.dcm_paths = list(dcm_dir.glob("*.dcm"))
        self.mask_dir = mask_dir

    def __len__(self):
        return len(self.dcm_paths)

    def __getitem__(self, idx):
        dcm_path = self.dcm_paths[idx]
        ds = pydicom.dcmread(dcm_path)
        img = ds.pixel_array.astype(np.float32)
        img = (img - img.min()) / (img.ptp() + 1e-5)  # 0‑1
        mask_path = self.mask_dir / f"{dcm_path.stem}.png"
        mask = np.array(Image.open(mask_path).convert("L"), dtype=np.float32) / 255.0
        img  = torch.from_numpy(img[None]).float()      # (1,H,W) float32
        mask = torch.from_numpy(mask[None]).float()     # idem
        return img, mask


# ──────────────────────────────────────────────────────────────────────────────
# Loss & metrics
# ──────────────────────────────────────────────────────────────────────────────

def dice_coeff(pred: torch.Tensor, target: torch.Tensor, smooth: float = 1.0) -> torch.Tensor:
    pred = pred.contiguous(); target = target.contiguous()
    inter = (pred * target).sum(dim=(2, 3))
    union = pred.sum(dim=(2, 3)) + target.sum(dim=(2, 3))
    dice = (2.0 * inter + smooth) / (union + smooth)
    return dice.mean()


def bce_dice_loss(pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    target = target.type_as(pred)        # assicura stesso dtype
    return 0.5 * nn.functional.binary_cross_entropy(pred, target) + 0.5 * (1 - dice_coeff(pred, target))

# ──────────────────────────────────────────────────────────────────────────────
# Training util – saves best model + early‑stop + plots
# ──────────────────────────────────────────────────────────────────────────────

def train(args):
    # Dataset & split
    full = RsnaDicomDataset(Path(args.data_dir), Path(args.mask_dir))
    val_len = int(len(full) * args.val_split)
    train_len = len(full) - val_len
    train_set, val_set = random_split(full, [train_len, val_len])
    train_loader = DataLoader(train_set, batch_size=args.batch_size, shuffle=True, num_workers=args.workers)
    val_loader = DataLoader(val_set, batch_size=args.batch_size, shuffle=False, num_workers=args.workers)

    # Model & optimizer
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = UNet().to(device)
    opt = torch.optim.Adam(model.parameters(), lr=args.lr)

    history = {k: [] for k in ("loss", "val_loss", "dice", "val_dice")}
    best = float("inf"); bad = 0

    for epoch in range(args.epochs):
        # --- TRAIN ---
        model.train(); epoch_loss = 0; epoch_dice = 0
        for imgs, masks in tqdm(train_loader, desc=f"Train {epoch+1}/{args.epochs}"):
            imgs, masks = imgs.to(device), masks.to(device)
            preds = model(imgs)
            loss = bce_dice_loss(preds, masks)
            opt.zero_grad(); loss.backward(); opt.step()
            epoch_loss += loss.item() * imgs.size(0)
            epoch_dice += dice_coeff(preds > 0.5, masks).item() * imgs.size(0)
        epoch_loss /= train_len; epoch_dice /= train_len

        # --- VAL ---
        model.eval(); v_loss = 0; v_dice = 0
        with torch.no_grad():
            for imgs, masks in val_loader:
                imgs, masks = imgs.to(device), masks.to(device)
                preds = model(imgs)
                loss = bce_dice_loss(preds, masks)
                v_loss += loss.item() * imgs.size(0)
                v_dice += dice_coeff(preds > 0.5, masks).item() * imgs.size(0)
        v_loss /= val_len; v_dice /= val_len

        print(f"Epoch {epoch+1}: loss={epoch_loss:.4f}  val_loss={v_loss:.4f}  dice={epoch_dice:.3f}  val_dice={v_dice:.3f}")

        # save history
        for k, v in zip(history.keys(), (epoch_loss, v_loss, epoch_dice, v_dice)):
            history[k].append(v)

        # early‑stop
        if v_loss < best:
            best, bad = v_loss, 0
            torch.save(model.state_dict(), args.model_out)
        else:
            bad += 1
            if bad >= args.patience:
                print("Early‑stopping triggered."); break

    print(f"[+] Best val_loss={best:.4f}  model saved to {args.model_out}")

    # optional plots
    if args.plot and plt is not None:
        epochs_range = range(1, len(history["loss"]) + 1)
        plt.figure(); plt.plot(epochs_range, history["loss"], label="loss"); plt.plot(epochs_range, history["val_loss"], label="val_loss"); plt.legend(); plt.title("Learning curve – loss"); plt.xlabel("Epoch"); plt.ylabel("loss"); plt.savefig("learning_curve_loss.png")
        plt.figure(); plt.plot(epochs_range, history["dice"], label="dice"); plt.plot(epochs_range, history["val_dice"], label="val_dice"); plt.legend(); plt.title("Dice coefficient"); plt.xlabel("Epoch"); plt.ylabel("dice"); plt.savefig("learning_curve_dice.png")
        print("[+] Saved learning_curve_loss.png & learning_curve_dice.png")


# ──────────────────────────────────────────────────────────────────────────────
# Inference (unchanged core)
# ──────────────────────────────────────────────────────────────────────────────

def overlay_mask_on_image(img: np.ndarray, mask: np.ndarray, alpha: float = 0.4) -> np.ndarray:
    gray = (img * 255).clip(0, 255).astype(np.uint8)
    rgb = np.stack([gray, gray, gray], axis=-1)
    red = np.zeros_like(rgb); red[..., 0] = 255
    mask3 = np.repeat(mask[..., None], 3, axis=-1)
    return np.where(mask3, (1 - alpha) * rgb + alpha * red, rgb).astype(np.uint8)


def save_secondary_capture(original_ds: pydicom.FileDataset, rgb_img: np.ndarray, out_path: Path):
    ds = pydicom.Dataset(); ds.update(original_ds)
    ds.SOPInstanceUID = pydicom.uid.generate_uid()
    ds.SOPClassUID = pydicom.uid.SecondaryCaptureImageStorage
    ds.file_meta = pydicom.dataset.FileMetaDataset(); ds.file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
    ds.Rows, ds.Columns = rgb_img.shape[:2]
    ds.SamplesPerPixel, ds.PhotometricInterpretation, ds.PlanarConfiguration = 3, "RGB", 0
    ds.BitsAllocated = ds.BitsStored = 8; ds.HighBit = 7; ds.PixelRepresentation = 0
    ds.is_little_endian, ds.is_implicit_VR = True, False
    ds.PixelData = rgb_img.tobytes(); pydicom.dcmwrite(str(out_path), ds)


def infer(args):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = UNet().to(device)
    model.load_state_dict(torch.load(args.model_path, map_location=device))
    model.eval()
    ds = pydicom.dcmread(args.dcm_path)
    img = ds.pixel_array.astype(np.float32)
    img_norm = (img - img.min()) / (img.ptp() + 1e-5)
    with torch.no_grad():
        mask = model(torch.from_numpy(img_norm[None, None]).to(device))[0, 0].cpu().numpy() > 0.5
    overlay = overlay_mask_on_image(img_norm, mask)
    save_secondary_capture(ds, overlay, Path(args.out_dcm))
    print(f"[+] Saved overlay DICOM to {args.out_dcm}")


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def cli():
    p = argparse.ArgumentParser(description="Kinase Wave‑0 DICOM segmentation – enhanced")
    sub = p.add_subparsers(dest="cmd", required=True)

    tr = sub.add_parser("train")
    tr.add_argument("--data-dir", required=True)
    tr.add_argument("--mask-dir", required=True)
    tr.add_argument("--epochs", type=int, default=50)
    tr.add_argument("--batch-size", type=int, default=8)
    tr.add_argument("--lr", type=float, default=1e-4)
    tr.add_argument("--model-out", default="model.pth")
    tr.add_argument("--val-split", type=float, default=0.2)
    tr.add_argument("--patience", type=int, default=3)
    tr.add_argument("--workers", type=int, default=0)
    tr.add_argument("--plot", action="store_true", help="Save learning curve PNGs")

    inf = sub.add_parser("infer")
    inf.add_argument("--dcm-path", required=True)
    inf.add_argument("--model-path", default="model.pth")
    inf.add_argument("--out-dcm", default="output_overlay.dcm")

    args = p.parse_args()
    if args.cmd == "train":
        train(args)
    else:
        infer(args)


if __name__ == "__main__":
    cli()
