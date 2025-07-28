import os, json, boto3, urllib.parse

sqs = boto3.client("sqs")

def lambda_handler(event, context):
    # legge la query string ?queue=<url>
    params = event.get("queryStringParameters") or {}
    raw = params.get("queue")
    if not raw:
        return {"statusCode":400, "body": json.dumps({"error":"missing queue"})}
    queue_url = urllib.parse.unquote(raw)
    # ricevi fino a 5 messaggi
    resp = sqs.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=5,
        WaitTimeSeconds=0,
        MessageAttributeNames=["All"]
    )
    msgs = resp.get("Messages", [])
    bodies = []
    for m in msgs:
        try:
            bodies.append(json.loads(m["Body"]))
        except:
            bodies.append({"Body": m["Body"]})
        # cancella subito per non riprendere due volte
        sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=m["ReceiptHandle"])
    return {
        "statusCode":200,
        "headers":{
            "Access-Control-Allow-Origin":"*",
            "Access-Control-Allow-Headers": "Content-Type"
        },
        "body": json.dumps(bodies)
    }
