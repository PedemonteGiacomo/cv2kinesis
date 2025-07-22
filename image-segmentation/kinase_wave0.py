"""
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
"""

import argparse
from pathlib import Path
from typing import Tuple

import numpy as np
import pydicom
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.transforms.functional as TF
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from tqdm.auto import tqdm


# ──────────────────────────────────────────────────────────────────────────────
# Model – A minimalist 4‑level U‑Net (≈7 M params)
# ──────────────────────────────────────────────────────────────────────────────
class DoubleConv(nn.Module):
    def __init__(self, in_channels, out_channels):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, x):
        return self.conv(x)


class UNet(nn.Module):
    def __init__(self, in_channels=1, n_classes=1, features=(32, 64, 128, 256)):
        super().__init__()
        self.downs = nn.ModuleList()
        self.ups = nn.ModuleList()
        # Down path
        for feat in features:
            self.downs.append(DoubleConv(in_channels, feat))
            in_channels = feat
        # Up path
        for feat in reversed(features):
            self.ups.append(
                nn.ConvTranspose2d(feat * 2, feat, kernel_size=2, stride=2)
            )
            self.ups.append(DoubleConv(feat * 2, feat))
        self.bottleneck = DoubleConv(features[-1], features[-1] * 2)
        self.final_conv = nn.Conv2d(features[0], n_classes, kernel_size=1)

    def forward(self, x):
        skip_connections = []
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
# Dataset loader – Reads DICOM + matching mask PNG
# ──────────────────────────────────────────────────────────────────────────────
class RsnaDicomDataset(Dataset):
    def __init__(self, dcm_dir: Path, mask_dir: Path, transforms=None):
        self.dcm_paths = list(dcm_dir.glob("*.dcm"))
        self.mask_dir = mask_dir
        self.transforms = transforms

    def __len__(self):
        return len(self.dcm_paths)

    def __getitem__(self, idx):
        dcm_path = self.dcm_paths[idx]
        mask_path = self.mask_dir / (dcm_path.stem + ".png")
        ds = pydicom.dcmread(dcm_path)
        img = ds.pixel_array.astype(np.float32)
        # Basic normalization to 0‑1
        img = (img - img.min()) / (img.ptp() + 1e-5)
        mask = np.array(Image.open(mask_path).convert("L")) / 255.0
        if self.transforms:
            augmented = self.transforms(image=img, mask=mask)
            img, mask = augmented["image"], augmented["mask"]
        img = torch.from_numpy(img[None, ...])  # add channel dim
        mask = torch.from_numpy(mask[None, ...])
        return img, mask


# ──────────────────────────────────────────────────────────────────────────────
# Training loop
# ──────────────────────────────────────────────────────────────────────────────

def train(args):
    dset = RsnaDicomDataset(Path(args.data_dir), Path(args.mask_dir))
    loader = DataLoader(dset, batch_size=args.batch_size, shuffle=True, num_workers=4)
    model = UNet()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    opt = torch.optim.Adam(model.parameters(), lr=args.lr)
    criterion = nn.BCELoss()

    for epoch in range(args.epochs):
        model.train()
        running = 0.0
        for imgs, masks in tqdm(loader, desc=f"epoch {epoch+1}/{args.epochs}"):
            imgs, masks = imgs.to(device), masks.to(device)
            preds = model(imgs)
            loss = criterion(preds, masks)
            opt.zero_grad()
            loss.backward()
            opt.step()
            running += loss.item() * imgs.size(0)
        print(f"loss={running/len(dset):.4f}")
    torch.save(model.state_dict(), args.model_out)
    print(f"[+] Saved weights to {args.model_out}")


# ──────────────────────────────────────────────────────────────────────────────
# Inference utilities
# ──────────────────────────────────────────────────────────────────────────────

def overlay_mask_on_image(img: np.ndarray, mask: np.ndarray, alpha: float = 0.4) -> np.ndarray:
    """Blend red mask onto grayscale image and return RGB uint8 array."""
    gray = (img * 255).clip(0, 255).astype(np.uint8)
    rgb = np.stack([gray, gray, gray], axis=-1)
    red = np.zeros_like(rgb)
    red[..., 0] = 255  # red channel
    mask3 = np.repeat(mask[..., None], 3, axis=-1)
    blended = np.where(mask3, (1 - alpha) * rgb + alpha * red, rgb)
    return blended.astype(np.uint8)


def save_secondary_capture(original_ds: pydicom.FileDataset, rgb_img: np.ndarray, out_path: Path):
    ds = pydicom.Dataset()
    ds.update(original_ds)
    # Create new SOP Instance UID
    ds.SOPInstanceUID = pydicom.uid.generate_uid()
    ds.SOPClassUID = pydicom.uid.SecondaryCaptureImageStorage
    ds.file_meta = pydicom.dataset.FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
    ds.Rows, ds.Columns = rgb_img.shape[:2]
    ds.SamplesPerPixel = 3
    ds.PhotometricInterpretation = "RGB"
    ds.PlanarConfiguration = 0
    ds.BitsAllocated = 8
    ds.BitsStored = 8
    ds.HighBit = 7
    ds.PixelRepresentation = 0
    ds.is_little_endian = True
    ds.is_implicit_VR = False
    ds.PixelData = rgb_img.tobytes()
    pydicom.dcmwrite(str(out_path), ds)


def infer(args):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = UNet().to(device)
    model.load_state_dict(torch.load(args.model_path, map_location=device))
    model.eval()

    ds = pydicom.dcmread(args.dcm_path)
    img = ds.pixel_array.astype(np.float32)
    img_norm = (img - img.min()) / (img.ptp() + 1e-5)
    with torch.no_grad():
        inp = torch.from_numpy(img_norm[None, None, ...]).to(device)
        mask = model(inp)[0, 0].cpu().numpy() > 0.5
    overlay = overlay_mask_on_image(img_norm, mask)
    save_secondary_capture(ds, overlay, Path(args.out_dcm))
    print(f"[+] Saved overlay DICOM to {args.out_dcm}")


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def cli():
    p = argparse.ArgumentParser(description="Kinase Wave‑0 DICOM segmentation prototype")
    sub = p.add_subparsers(dest="cmd", required=True)

    train_p = sub.add_parser("train")
    train_p.add_argument("--data-dir", required=True, help="Folder with *.dcm")
    train_p.add_argument("--mask-dir", required=True, help="Folder with PNG masks")
    train_p.add_argument("--epochs", type=int, default=5)
    train_p.add_argument("--batch-size", type=int, default=8)
    train_p.add_argument("--lr", type=float, default=1e-4)
    train_p.add_argument("--model-out", default="model.pth")

    infer_p = sub.add_parser("infer")
    infer_p.add_argument("--dcm-path", required=True)
    infer_p.add_argument("--model-path", default="model.pth")
    infer_p.add_argument("--out-dcm", default="output_overlay.dcm")

    args = p.parse_args()
    if args.cmd == "train":
        train(args)
    else:
        infer(args)

if __name__ == "__main__":
    cli()
