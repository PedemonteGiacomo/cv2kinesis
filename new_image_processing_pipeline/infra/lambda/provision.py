import boto3
import json
import uuid
sqs = boto3.client("sqs")
sns = boto3.client("sns")

sqs = boto3.client("sqs")

def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body","{}"))
        client_id = body.get("client_id") or str(uuid.uuid4())
        name = f"ClientResults-{client_id}.fifo"
        q = sqs.create_queue(QueueName=name, Attributes={
            "FifoQueue":"true","ContentBasedDeduplication":"true"
        })
        url = q["QueueUrl"]
        return {
            "statusCode":200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type"
            },
            "body": json.dumps({"client_id":client_id,"queue_url":url})
        }
    except Exception as e:
        return {
            "statusCode":500,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type"
            },
            "body": json.dumps({"error": str(e)})
        }
