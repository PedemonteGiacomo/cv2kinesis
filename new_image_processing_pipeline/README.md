# Image Processing Pipeline

This package contains containers and infrastructure for event-driven image processing.

## Build images

```bash
make build-base
make build-algos
```

## Run PACS simulator

```bash
docker build -t pacs-sim pacs_api_sim
docker run -p 8000:8000 -e AWS_ACCESS_KEY_ID=... -e AWS_SECRET_ACCESS_KEY=... pacs-sim
```

## Send a test job

```bash
python simulate_request.py
```

Message format:

```jsonc
{
  "job_id": "uuid4",
  "algo_id": "processing_6",
  "pacs": {"study_id": "1.2.3", "series_id": "4.5.6", "image_id": "7.8.9", "scope": "image"},
  "callback": {"queue_url": "https://sqs.eu-central-1.amazonaws.com/123456/ImageResults.fifo"}
}
```
