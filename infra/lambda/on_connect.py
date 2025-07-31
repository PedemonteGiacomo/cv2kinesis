import json, os, boto3

ddb = boto3.client("dynamodb")
TABLE = os.environ["CONN_TABLE"]

def lambda_handler(event, _):
    conn_id = event["requestContext"]["connectionId"]
    cid = (event.get("queryStringParameters") or {}).get("client_id")
    if cid:
        ddb.put_item(TableName=TABLE,
                     Item={"client_id":{"S":cid},
                           "connectionId":{"S":conn_id}})
    return {"statusCode":200,"body":"OK"}
