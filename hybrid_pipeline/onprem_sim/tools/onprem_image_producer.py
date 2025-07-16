"""Simple image producer writing JPEG files to an NFS share."""

import argparse
import itertools
import random
import time
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw


parser = argparse.ArgumentParser()
parser.add_argument("--root", default="/mnt/z", help="NFS root path")
args = parser.parse_args()

root = Path(args.root)
root.mkdir(exist_ok=True)


def new_image(i: int):
    img = Image.new("RGB", (640, 480), (random.randint(0, 255),) * 3)
    d = ImageDraw.Draw(img)
    d.text((40, 40), f"IMG {i:05d}\n{datetime.utcnow()}", fill=(255, 255, 255))
    return img


for i in itertools.count():
    f = root / f"img_{i:05d}.jpg"
    new_image(i).save(f, "JPEG", quality=85)
    print(f"[producer] scritto {f}")
    time.sleep(5)
