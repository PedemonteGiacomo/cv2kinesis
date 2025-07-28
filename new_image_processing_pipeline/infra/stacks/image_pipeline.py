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
    aws_ecr as ecr,
    CfnOutput,
    aws_lambda as _lambda,
    aws_apigateway as apigw,
    aws_sns as sns,
    aws_iam as iam
)
from constructs import Construct
import json
import os


class ImagePipeline(Stack):
        
    def __init__(self, scope: Construct, _id: str, pacs_api_url: str = None, **kw) -> None:
        super().__init__(scope, _id, **kw)

        algos_param = self.node.try_get_context("algos")
        algos = (
            algos_param.split(",") if algos_param else ["processing_1", "processing_6"]
        )

        ecr_repo = ecr.Repository.from_repository_name(
            self, "AlgosRepo", "mip-algos"
        )

        vpc = ec2.Vpc(self, "ImgVpc", max_azs=2)
        cluster = ecs.Cluster(self, "ImgCluster", vpc=vpc)

        out_bucket = s3.Bucket(self, "Output", removal_policy=RemovalPolicy.RETAIN)
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
                image=ecs.ContainerImage.from_ecr_repository(
                    ecr_repo,
                    tag=algo
                ),
                logging=ecs.LogDrivers.aws_logs(
                    stream_prefix=algo, log_retention=logs.RetentionDays.ONE_WEEK
                ),
                environment={
                    "QUEUE_URL": request_queues[algo].queue_url,
                    "OUTPUT_BUCKET": out_bucket.bucket_name,
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
            )
            request_queues[algo].grant_consume_messages(task.task_role)
            out_bucket.grant_put(task.task_role)
            out_bucket.grant_read(task.task_role)
            # Permesso per inviare a tutte le queue client dinamiche
            task.task_role.add_to_policy(iam.PolicyStatement(
                actions=["sqs:SendMessage"],
                resources=["arn:aws:sqs:*:*:ClientResults-*"]
            ))

            svc.auto_scale_task_count(min_capacity=1, max_capacity=10).scale_on_metric(
                f"Scale{algo}",
                metric=request_queues[algo].metric_approximate_number_of_messages_visible(),
                scaling_steps=[{"upper": 0, "change": -1}, {"lower": 1, "change": 1}],
                adjustment_type=appscaling.AdjustmentType.CHANGE_IN_CAPACITY,
            )
        # Lambda Router & API Gateway

        queue_url_map = { algo: rq.queue_url for algo, rq in request_queues.items() }

        router = _lambda.Function(
            self, "RouterFunction",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="router.lambda_handler",
            code=_lambda.Code.from_asset(os.path.join(os.path.dirname(__file__), "../lambda")),
            environment={
               "QUEUE_URLS_JSON": json.dumps(queue_url_map)
            }
        )
        # Lambda di provisioning per /provision
        provision = _lambda.Function(
            self, "ProvisionFunction",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="provision.lambda_handler",
            code=_lambda.Code.from_asset(os.path.join(os.path.dirname(__file__), "../lambda")),
        )
        provision.add_to_role_policy(iam.PolicyStatement(
            actions=[
                "sqs:CreateQueue","sqs:GetQueueAttributes","sqs:SetQueueAttributes"
            ],
            resources=["*"]
        ))
        # Lambda proxy SQS per polling HTTP
        proxy = _lambda.Function(
            self, "ProxySqsFunction",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="proxy_sqs.lambda_handler",
            code=_lambda.Code.from_asset(os.path.join(os.path.dirname(__file__), "../lambda")),
        )
        proxy.add_to_role_policy(iam.PolicyStatement(
            actions=["sqs:ReceiveMessage","sqs:DeleteMessage"],
            resources=["*"]
        ))

        for rq in request_queues.values():
            rq.grant_send_messages(router)

        api = apigw.RestApi(self, "ProcessingApi",
            rest_api_name="ImageProcessing API",
            default_cors_preflight_options=apigw.CorsOptions(
              allow_origins=apigw.Cors.ALL_ORIGINS,
              allow_methods=apigw.Cors.ALL_METHODS
            )
        )

        proc = api.root.add_resource("process")
        algo = proc.add_resource("{algo_id}")
        algo.add_method("POST", apigw.LambdaIntegration(router))
        # Endpoint /provision per provisioning dinamico
        prov = api.root.add_resource("provision")
        prov.add_method("POST", apigw.LambdaIntegration(provision))
        # Endpoint /proxy-sqs per polling SQS via HTTP (usato dal frontend React)
        ps = api.root.add_resource("proxy-sqs")
        ps.add_method("GET", apigw.LambdaIntegration(proxy))

        for algo in algos:
            CfnOutput(self, f"ImageRequestsQueueUrl{algo}", value=request_queues[algo].queue_url)
        CfnOutput(self, "OutputBucketName",    value=out_bucket.bucket_name)
        CfnOutput(self, "ProcessingApiEndpoint", value=api.url)
