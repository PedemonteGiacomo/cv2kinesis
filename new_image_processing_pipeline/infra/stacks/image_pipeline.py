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

        out_bucket = s3.Bucket(self, "Output", removal_policy=RemovalPolicy.DESTROY)

        # 1️⃣ Crea il Topic SNS per i risultati
        results_topic = sns.Topic(self, "ImageResultsTopic", topic_name="ImageResultsTopic.fifo", fifo=True, content_based_deduplication=True)

        # Una coda risultati dedicata per ogni algoritmo
        result_queues = {}
        for algo in algos:
            result_queues[algo] = sqs.Queue(
                self,
                f"ImageResults{algo}.fifo",
                fifo=True,
                content_based_deduplication=True,
            )

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
                    "RESULT_QUEUE": result_queues[algo].queue_url,
                    "RESULTS_TOPIC_ARN": results_topic.topic_arn,
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
            result_queues[algo].grant_send_messages(task.task_role)
            out_bucket.grant_put(task.task_role)
            results_topic.grant_publish(task.task_role)

            svc.auto_scale_task_count(min_capacity=1, max_capacity=10).scale_on_metric(
                f"Scale{algo}",
                metric=request_queues[algo].metric_approximate_number_of_messages_visible(),
                scaling_steps=[{"upper": 0, "change": -1}, {"lower": 1, "change": 1}],
                adjustment_type=appscaling.AdjustmentType.CHANGE_IN_CAPACITY,
            )
        # Lambda Router & API Gateway

        queue_url_map = { algo: rq.queue_url for algo, rq in request_queues.items() }
        result_url_map = { algo: rq.queue_url for algo, rq in result_queues.items() }

        router = _lambda.Function(
            self, "RouterFunction",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="router.lambda_handler",
            code=_lambda.Code.from_asset(os.path.join(os.path.dirname(__file__), "../lambda")),
            environment={
               "QUEUE_URLS_JSON": json.dumps(queue_url_map),
               "RESULT_URLS_JSON": json.dumps(result_url_map)
            }
        )
        # Lambda di provisioning per /provision
        provision = _lambda.Function(
            self, "ProvisionFunction",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="provision.lambda_handler",
            code=_lambda.Code.from_asset(os.path.join(os.path.dirname(__file__), "../lambda")),
            environment={"RESULTS_TOPIC_ARN": results_topic.topic_arn}
        )
        # Permetti a provision di creare code e sottoscrizioni SNS
        results_topic.grant_publish(provision)
        provision.add_to_role_policy(iam.PolicyStatement(
            actions=[
                "sqs:CreateQueue","sqs:GetQueueAttributes","sqs:SetQueueAttributes",
                "sns:Subscribe"
            ],
            resources=["*"]
        ))
        # Lambda proxy SQS per polling HTTP
        # Espone /proxy-sqs su API Gateway per polling SQS via HTTP puro (frontend/browser)
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
        for rq in result_queues.values():
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
            CfnOutput(self, f"ImageResultsQueueUrl{algo}", value=result_queues[algo].queue_url)
        CfnOutput(self, "OutputBucketName",    value=out_bucket.bucket_name)
        # Output per SNS Topic ARN
        CfnOutput(self, "ImageResultsTopicArn", value=results_topic.topic_arn)
        # Output per API Gateway endpoint
        CfnOutput(self, "ProcessingApiEndpoint", value=api.url)
