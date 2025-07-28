import json
import os
import boto3

sqs = boto3.client("sqs")
QUEUE_URLS = json.loads(os.environ["QUEUE_URLS_JSON"])

def lambda_handler(event, context):
    algo = event["pathParameters"]["algo_id"]
    if algo not in QUEUE_URLS:
        return {"statusCode": 404, "body": json.dumps({"error":"Unknown algorithm"})}

    body = json.loads(event["body"])
    msg = json.dumps(body)
    resp = sqs.send_message(
        QueueUrl=QUEUE_URLS[algo],
        MessageBody=msg,
        MessageGroupId=body.get("job_id","default")
    )
    return {
        "statusCode": 202,
        "body": json.dumps({"message":"Enqueued","sqs_message_id":resp["MessageId"]})
    }
