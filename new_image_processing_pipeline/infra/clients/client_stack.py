from aws_cdk import (
    Stack,
    aws_sqs as sqs,
    aws_sns as sns,
    aws_sns_subscriptions as subs,
)
from constructs import Construct

class ClientResultsStack(Stack):
    def __init__(self, scope: Construct, id: str, client_id: str, topic_arn: str, **kw):
        super().__init__(scope, id, **kw)

        # 1. Recupera il topic SNS esistente
        topic = sns.Topic.from_topic_arn(self, "ImageResultsTopic", topic_arn)

        # 2. Crea la coda SQS FIFO per il client
        queue = sqs.Queue(self, "ClientResultsQueue",
            queue_name=f"{client_id}Results.fifo",
            fifo=True,
            content_based_deduplication=True
        )

        # 3. Sottoscrivi la coda al topic con filter policy su client_id
        topic.add_subscription(subs.SqsSubscription(
            queue,
            filter_policy={
                "client_id": sns.SubscriptionFilter.string_filter(allowlist=[client_id])
            }
        ))

        # 4. Output della coda per il client
        from aws_cdk import CfnOutput
        CfnOutput(self, "ClientResultsQueueUrl", value=queue.queue_url)
        CfnOutput(self, "ClientResultsQueueArn", value=queue.queue_arn)
