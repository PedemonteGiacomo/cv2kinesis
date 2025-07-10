from __future__ import annotations

import os
from io import BytesIO

from PIL import Image
import boto3

s3 = boto3.client("s3")
DEST_BUCKET = os.environ["DEST_BUCKET"]


def main(event, context):
    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key = record["s3"]["object"]["key"]
        obj = s3.get_object(Bucket=bucket, Key=key)
        img = Image.open(obj["Body"])
        grayscale = img.convert("L")
        buf = BytesIO()
        grayscale.save(buf, format="PNG")
        buf.seek(0)
        out_key = f"processed/{os.path.basename(key)}"
        s3.put_object(
            Bucket=DEST_BUCKET,
            Key=out_key,
            Body=buf.getvalue(),
            ContentType="image/png",
        )
    return {"statusCode": 200}
