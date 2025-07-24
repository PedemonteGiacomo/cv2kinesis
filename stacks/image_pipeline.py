from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_s3 as s3,
    aws_sqs as sqs,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecr as ecr,
    aws_lambda as _lambda,
    aws_events as events,
    aws_events_targets as targets,
    aws_logs as logs,
)
from constructs import Construct
import json

ALGOS = ["processing_1", "processing_6"]


class ImagePipeline(Stack):
    def __init__(self, scope: Construct, _id: str, **kw) -> None:
        super().__init__(scope, _id, **kw)

        vpc = ec2.Vpc(self, "ImgVpc", max_azs=2)
        cluster = ecs.Cluster(self, "ImgCluster", vpc=vpc)

        in_bucket = s3.Bucket(self, "Input", removal_policy=RemovalPolicy.DESTROY)
        out_bucket = s3.Bucket(self, "Output", removal_policy=RemovalPolicy.DESTROY)

        dispatcher = _lambda.Function(
            self,
            "Dispatcher",
            runtime=_lambda.Runtime.PYTHON_3_11,
            code=_lambda.Code.from_inline(
                """import os, json, boto3, re\n"""
                "sqs = boto3.client('sqs')\n"
                "rules = json.loads(os.environ['ROUTING'])\n"
                "def lambda_handler(evt, ctx):\n"
                "    for r in evt['Records']:\n"
                "        key = r['s3']['object']['key']\n"
                "        for pat, qurl in rules.items():\n"
                "            if re.match(pat, key):\n"
                "                sqs.send_message(QueueUrl=qurl, MessageBody=json.dumps({'bucket': r['s3']['bucket']['name'], 'key': key, 'job_id': r['responseElements']['x-amz-request-id']}))\n"
                "                break\n"
            ),
            handler="index.lambda_handler",
            environment={"ROUTING": "{}"},
        )
        in_bucket.grant_read(dispatcher)

        routing = {}

        for algo in ALGOS:
            q = sqs.Queue(
                self,
                f"Queue{algo}",
                fifo=True,
                content_based_deduplication=True,
                visibility_timeout=Duration.minutes(10),
            )

            repo = ecr.Repository.from_repository_name(
                self, f"Repo{algo}", f"processing-{algo[-1]}"
            )
            task = ecs.FargateTaskDefinition(
                self, f"TaskDef{algo}", cpu=1024, memory_limit_mib=2048
            )

            task.add_container(
                "Main",
                image=ecs.ContainerImage.from_ecr_repository(repo, "latest"),
                logging=ecs.LogDrivers.aws_logs(
                    stream_prefix=algo, log_retention=logs.RetentionDays.ONE_WEEK
                ),
                environment={
                    "INPUT_BUCKET": in_bucket.bucket_name,
                    "OUTPUT_BUCKET": out_bucket.bucket_name,
                    "ALGO_ID": algo,
                    "QUEUE_URL": q.queue_url,
                },
                command=["/app/worker.sh"],
            )

            svc = ecs.FargateService(
                self,
                f"Svc{algo}",
                cluster=cluster,
                task_definition=task,
                desired_count=0,
            )

            in_bucket.grant_read(task.task_role)
            out_bucket.grant_write(task.task_role)
            q.grant_consume_messages(task.task_role)

            svc.auto_scale_task_count(max_capacity=10).scale_on_metric(
                f"Scale{algo}",
                metric=q.metric_approximate_number_of_messages_visible(),
                scaling_steps=[{"upper": 0, "change": -1}, {"lower": 1, "change": 1}],
                adjustment_type=ecs.AdjustmentType.CHANGE_IN_CAPACITY,
            )

            routing[f"^{algo}/.*\\.dcm$"] = q.queue_url

        dispatcher.add_environment("ROUTING", json.dumps(routing))
        events.Rule(
            self,
            "S3Put",
            event_pattern=events.EventPattern(
                source=["aws.s3"],
                detail_type=["Object Created"],
                detail={"bucket": {"name": [in_bucket.bucket_name]}},
            ),
            targets=[targets.LambdaFunction(dispatcher)],
        )
