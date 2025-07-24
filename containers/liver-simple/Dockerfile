FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    ALGO_ID=processing_6

WORKDIR /app

COPY medical-image-processing/ medical-image-processing/
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY containers/common/entrypoint.py /app/entrypoint.py
ENTRYPOINT ["python", "/app/entrypoint.py"]
