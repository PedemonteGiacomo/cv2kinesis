FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        awscli jq && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
COPY src/ src/
RUN pip install --no-cache-dir -r requirements.txt -e ./src

COPY containers/base/worker.sh /app/worker.sh
ENTRYPOINT ["/app/worker.sh"]
