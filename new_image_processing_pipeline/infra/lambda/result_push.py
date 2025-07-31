import json, os, boto3, logging
import aws_embedded_metrics

metrics = aws_embedded_metrics.metric_scope()
log = logging.getLogger()
log.setLevel(logging.INFO)
ddb = boto3.client("dynamodb")
TABLE = os.environ["CONN_TABLE"]
api = boto3.client("apigatewaymanagementapi",
                   endpoint_url=os.environ["WS_CALLBACK_URL"])

@metrics
def lambda_handler(event, context):
    metrics.set_namespace("ImagePipeline")
    metrics.set_dimension("Function","ResultPush")
    for r in event["Records"]:
        body = json.loads(r["body"])
        cid = body["client_id"]
        item = ddb.get_item(TableName=TABLE, Key={"client_id":{"S":cid}}).get("Item")
        if not item:
            log.warning("No connection found for client_id %s", cid)
            metrics.put_metric("PushFailures", 1, "Count")
            continue
        try:
            api.post_to_connection(ConnectionId=item["connectionId"]["S"],
                                   Data=json.dumps(body).encode())
            metrics.put_metric("MessagesPushed", 1, "Count")
        except api.exceptions.GoneException:
            log.warning("Gone – client %s disconnected", cid)
            ddb.delete_item(TableName=TABLE, Key={"client_id":{"S":cid}})
            metrics.put_metric("Disconnected", 1, "Count")
