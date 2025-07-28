import os, json, boto3, uuid

sqs = boto3.client("sqs")
sns = boto3.client("sns")
TOPIC_ARN = os.environ["RESULTS_TOPIC_ARN"]

def lambda_handler(event, context):
    body = json.loads(event.get("body","{}"))
    client_id = body.get("client_id") or str(uuid.uuid4())
    # ① crea queue FIFO
    name = f"ClientResults-{client_id}.fifo"
    q = sqs.create_queue(QueueName=name, Attributes={
        "FifoQueue":"true","ContentBasedDeduplication":"true"
    })
    url = q["QueueUrl"]
    arn = sqs.get_queue_attributes(
        QueueUrl=url, AttributeNames=["QueueArn"]
    )["Attributes"]["QueueArn"]
    # ② sottoscrizione SNS → SQS con filter su client_id
    sns.subscribe(
      TopicArn=TOPIC_ARN,
      Protocol="sqs",
      Endpoint=arn,
      Attributes={"FilterPolicy": json.dumps({"client_id":[client_id]})}
    )
    # ③ autorizza SNS a scrivere in SQS
    policy = {
      "Version":"2012-10-17","Statement":[{  
        "Effect":"Allow","Principal":{"Service":"sns.amazonaws.com"},
        "Action":"sqs:SendMessage","Resource":arn,
        "Condition":{"ArnEquals":{"aws:SourceArn":TOPIC_ARN}}
      }]
    }
    sqs.set_queue_attributes(
      QueueUrl=url, Attributes={"Policy": json.dumps(policy)}
    )
    return {
      "statusCode":200,
      "headers": {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type"
      },
      "body": json.dumps({"client_id":client_id,"queue_url":url})
    }
