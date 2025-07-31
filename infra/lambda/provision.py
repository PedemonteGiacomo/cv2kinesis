
import json
import uuid

def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body", "{}"))
        client_id = body.get("client_id") or str(uuid.uuid4())
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type"
            },
            "body": json.dumps({"client_id": client_id})
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type"
            },
            "body": json.dumps({"error": str(e)})
        }
