FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    ALGO_ID=processing_6

WORKDIR /app

RUN apt-get update && apt-get install -y awscli jq && rm -rf /var/lib/apt/lists/*

COPY medical-image-processing/ medical-image-processing/
COPY rsna_pipeline/ rsna_pipeline/
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY containers/common/worker.sh /app/worker.sh
ENTRYPOINT ["/app/worker.sh"]
