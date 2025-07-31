import os, boto3
ddb = boto3.client("dynamodb")
TABLE = os.environ["CONN_TABLE"]

def lambda_handler(event, _):
    conn_id = event["requestContext"]["connectionId"]
    resp = ddb.query(
        TableName=TABLE,
        IndexName="ByConnection",
        KeyConditionExpression="connectionId = :c",
        ExpressionAttributeValues={":c":{"S":conn_id}}
    )
    items = resp.get("Items", [])
    if not items:
        return {"statusCode":200,"body":"bye"}
    for item in items:
        ddb.delete_item(TableName=TABLE, Key={"client_id": item["client_id"]})
    return {"statusCode":200,"body":"bye"}
