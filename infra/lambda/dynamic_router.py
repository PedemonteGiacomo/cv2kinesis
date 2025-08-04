import json, os, boto3

sqs = boto3.client("sqs")
dynamodb = boto3.resource("dynamodb")
TABLE = os.environ["ALGO_TABLE"]

def lambda_handler(event, _):
    try:
        algo = event["pathParameters"]["algo_id"]
        body = json.loads(event["body"] or "{}")

        table = dynamodb.Table(TABLE)
        item = table.get_item(Key={"algorithm_id": algo}).get("Item")
        if not item or item.get("status") != "ACTIVE":
            return {
                "statusCode": 404,
                "headers": {"Access-Control-Allow-Origin":"*","Access-Control-Allow-Headers":"Content-Type"},
                "body": json.dumps({"error":"Algorithm not found or not active"})
            }

        qurl = item["resource_status"]["queue_url"]
        resp = sqs.send_message(
            QueueUrl=qurl,
            MessageBody=json.dumps(body),
            MessageGroupId=body.get("job_id","default")
        )
        return {
            "statusCode": 202,
            "headers": {"Access-Control-Allow-Origin":"*","Access-Control-Allow-Headers":"Content-Type"},
            "body": json.dumps({"message":"Enqueued","sqs_message_id":resp["MessageId"]})
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Access-Control-Allow-Origin":"*","Access-Control-Allow-Headers":"Content-Type"},
            "body": json.dumps({"error":str(e)})
        }
