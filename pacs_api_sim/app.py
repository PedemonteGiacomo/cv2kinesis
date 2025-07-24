from fastapi import FastAPI
import boto3
import os

app = FastAPI()
s3 = boto3.client("s3")
BUCKET = os.getenv("PACS_BUCKET")


@app.get("/studies/{study_id}/images/{image_id}")
def get_image(study_id: str, image_id: str):
    key = f"{study_id}/{image_id}.dcm"
    url = s3.generate_presigned_url(
        "get_object", Params={"Bucket": BUCKET, "Key": key}, ExpiresIn=900
    )
    return {"url": url}


@app.get("/studies/{study_id}/images")
def list_series(study_id: str, series_id: str | None = None):
    prefix = f"{study_id}/{series_id or ''}"
    resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix)
    return [
        {
            "url": s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": BUCKET, "Key": o["Key"]},
                ExpiresIn=900,
            )
        }
        for o in resp.get("Contents", [])
    ]
