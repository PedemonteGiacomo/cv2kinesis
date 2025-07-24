FROM python:3.11-slim
RUN pip install fastapi[all] boto3
ENV PACS_BUCKET=pacs-dicom-dev-544547773663-us-east-1
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
