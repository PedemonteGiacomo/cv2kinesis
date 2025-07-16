import os
import json
import boto3

def main(event, context):
    sm = boto3.client("stepfunctions")
    state_machine_arn = os.environ["STATE_MACHINE_ARN"]
    for record in event.get("Records", []):
        sm.start_execution(
            stateMachineArn=state_machine_arn,
            input=json.dumps({"Records": [record]})
        )
    return {"statusCode": 200}
