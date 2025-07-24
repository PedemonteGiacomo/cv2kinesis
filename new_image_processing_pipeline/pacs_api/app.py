from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
import boto3, os, re, datetime as dt
from urllib.parse import quote_plus

BUCKET = os.environ["PACS_BUCKET"]
s3 = boto3.client("s3")

app = FastAPI(title="PACS-API", version="0.1")

@app.get("/")
def root():
    return {"status": "ok"}

regex_uid = re.compile(r"^[A-Za-z0-9.\-]+$")  # include lettere & '-'

def _signed(key: str, exp: int = 900):
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET, "Key": key},
        ExpiresIn=exp,
    )


@app.get("/studies")
def list_studies(limit: int = 20):
    resp = s3.list_objects_v2(Bucket=BUCKET, Delimiter="/", MaxKeys=limit)
    # i "prefix" di primo livello sono gli StudyInstanceUID
    studies = [p["Prefix"].strip("/") for p in resp.get("CommonPrefixes", [])]
    return studies


@app.get("/studies/{study_id}/images")
def list_images(study_id: str, series_id: str = Query(None)):
    if not regex_uid.match(study_id):
        raise HTTPException(400, "bad UID")
    prefix = f"{study_id}/"
    if series_id:
        prefix += f"{series_id}/"
    keys = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".dcm"):
                keys.append(obj["Key"])
    return keys


@app.get("/studies/{study_id}/images/{image_id}")
def get_image(study_id: str, image_id: str):
    key = quote_plus(f"{study_id}/{image_id}")  # evita // negli UID "strani"
    url = _signed(key)
    return JSONResponse({"url": url, "expires": (dt.datetime.utcnow() + dt.timedelta(seconds=900)).isoformat()+"Z"})
