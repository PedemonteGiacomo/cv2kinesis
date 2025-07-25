from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_s3 as s3,
    aws_sqs as sqs,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_applicationautoscaling as appscaling,
    aws_logs as logs,
    CfnOutput,
)
import time
from constructs import Construct
import os


class ImagePipeline(Stack):
    def __init__(self, scope: Construct, _id: str, pacs_api_url: str = None, **kw) -> None:
        super().__init__(scope, _id, **kw)

        algos_param = self.node.try_get_context("algos")
        algos = (
            algos_param.split(",") if algos_param else ["processing_1", "processing_6"]
        )

        vpc = ec2.Vpc(self, "ImgVpc", max_azs=2)
        cluster = ecs.Cluster(self, "ImgCluster", vpc=vpc)

        out_bucket = s3.Bucket(self, "Output", removal_policy=RemovalPolicy.DESTROY)

        # Una coda per ogni algoritmo
        result_q = sqs.Queue(
            self,
            "ImageResults.fifo",
            fifo=True,
            content_based_deduplication=True,
        )

        rev = str(int(time.time()))  # epoch, cambia ad ogni deploy

        request_queues = {}
        for algo in algos:
            rq = sqs.Queue(
                self,
                f"ImageRequests{algo}.fifo",
                fifo=True,
                content_based_deduplication=True,
                visibility_timeout=Duration.minutes(15),
            )
            request_queues[algo] = rq

        for algo in algos:
            task = ecs.FargateTaskDefinition(
                self, f"TaskDef{algo}", cpu=1024, memory_limit_mib=2048
            )
            task.add_container(
                "Main",
                image=ecs.ContainerImage.from_asset(
                    os.path.abspath(
                        os.path.join(
                            os.path.dirname(__file__), "..", "..", "containers", algo
                        )
                    ),
                    build_args={"REVISION": rev},
                ),
                logging=ecs.LogDrivers.aws_logs(
                    stream_prefix=algo, log_retention=logs.RetentionDays.ONE_WEEK
                ),
                environment={
                    "QUEUE_URL": request_queues[algo].queue_url,
                    "OUTPUT_BUCKET": out_bucket.bucket_name,
                    "RESULT_QUEUE": result_q.queue_url,
                    "ALGO_ID": algo,
                    "PACS_API_BASE": pacs_api_url if pacs_api_url else "",
                    "PACS_API_KEY":  "devkey",
                },
                command=["/app/worker.sh"],
            )

            svc = ecs.FargateService(
                self,
                f"Svc{algo}",
                cluster=cluster,
                task_definition=task,
                desired_count=1,
            )

            request_queues[algo].grant_consume_messages(task.task_role)
            result_q.grant_send_messages(task.task_role)
            out_bucket.grant_put(task.task_role)

            svc.auto_scale_task_count(min_capacity=1, max_capacity=10).scale_on_metric(
                f"Scale{algo}",
                metric=request_queues[algo].metric_approximate_number_of_messages_visible(),
                scaling_steps=[{"upper": 0, "change": -1}, {"lower": 1, "change": 1}],
                adjustment_type=appscaling.AdjustmentType.CHANGE_IN_CAPACITY,
            )

        for algo in algos:
            CfnOutput(self, f"ImageRequestsQueueUrl{algo}", value=request_queues[algo].queue_url)
        CfnOutput(self, "ImageResultsQueueUrl", value=result_q.queue_url)
        CfnOutput(self, "OutputBucketName",    value=out_bucket.bucket_name)
