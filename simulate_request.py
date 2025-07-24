import json
import uuid
import boto3

sqs = boto3.client("sqs")
REQ_Q = "https://sqs.eu-central-1.amazonaws.com/123456/ImageRequests.fifo"

msg = {
    "job_id": str(uuid.uuid4()),
    "algo_id": "processing_6",
    "pacs": {
        "study_id": "liver1/phantomx_abdomen_pelvis_dataset/D55-01/300",
        "image_id": "IM-0135-0001",
        "scope": "image",
    },
    "callback": {
        "queue_url": "https://sqs.eu-central-1.amazonaws.com/123456/ImageResults.fifo"
    },
}

sqs.send_message(QueueUrl=REQ_Q, MessageBody=json.dumps(msg), MessageGroupId="demo")
print("Job sent:", msg["job_id"])
