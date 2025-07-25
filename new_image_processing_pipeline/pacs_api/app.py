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


from fastapi import Path
from typing import Optional

@app.get("/studies/{study_id:path}/images")
def list_images(study_id: str = Path(..., description="Path completo fino allo study, es: liver1/phantomx_abdomen_pelvis_dataset/D55-01"), series_id: Optional[str] = Query(None)):
    prefix = f"{study_id}/"
    if series_id:
        prefix += f"{series_id}/"
    out = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".dcm"):
                url = _signed(obj["Key"])
                out.append({"url": url, "key": obj["Key"]})
    return out



# Supporta path multipli dopo study_id (es: /studies/liver1/phantomx_abdomen_pelvis_dataset/D55-01/images/300/AiCE_BODY-SHARP_300_172938.900/IM-0135-0001.dcm)
@app.get("/studies/{study_id:path}/images/{image_path:path}")
def get_image(
    study_id: str = Path(..., description="Path completo fino allo study, es: liver1/phantomx_abdomen_pelvis_dataset/D55-01"),
    image_path: str = Path(..., description="Path relativo all'immagine dopo lo study_id, es: 300/AiCE_BODY-SHARP_300_172938.900/IM-0135-0001.dcm")
):
    key = f"{study_id}/{image_path}"
    url = _signed(key)
    return JSONResponse({"url": url, "expires": (dt.datetime.utcnow() + dt.timedelta(seconds=900)).isoformat()+"Z"})
