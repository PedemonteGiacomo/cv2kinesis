import json
import os
import re
import boto3

sqs = boto3.client("sqs")
ROUTING = json.loads(os.environ["ROUTING"])


def lambda_handler(evt, _ctx):
    for r in evt["Records"]:
        key = r["s3"]["object"]["key"]
        for pat, qurl in ROUTING.items():
            if re.match(pat, key):
                sqs.send_message(
                    QueueUrl=qurl,
                    MessageBody=json.dumps(
                        {
                            "bucket": r["s3"]["bucket"]["name"],
                            "key": key,
                            "job_id": r["responseElements"]["x-amz-request-id"],
                        }
                    ),
                )
                break
