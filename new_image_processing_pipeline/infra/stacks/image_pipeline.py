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
    aws_lambda as _lambda,
    aws_apigateway as apigw,
    aws_iam as iam,
    aws_dynamodb as ddb,
    aws_apigatewayv2 as apigwv2,
    CfnOutput
)
from aws_cdk.aws_apigatewayv2_integrations import WebSocketLambdaIntegration
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

        # ResultsQueue globale FIFO
        results_q = sqs.Queue(
            self, "ResultsQueue.fifo",
            fifo=True,
            content_based_deduplication=True,
            visibility_timeout=Duration.minutes(15),
            queue_name="ResultsQueue.fifo"
        )

        # DynamoDB Connections table
        connections = ddb.Table(
            self, "Connections",
            partition_key=ddb.Attribute(name="client_id", type=ddb.AttributeType.STRING),
            removal_policy=RemovalPolicy.DESTROY,
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST
        )
        # GSI ByConnection
        connections.add_global_secondary_index(
            index_name="ByConnection",
            partition_key=ddb.Attribute(name="connectionId", type=ddb.AttributeType.STRING)
        )

        # WebSocket API
        ws_api = apigwv2.WebSocketApi(self, "WebSocketApi",
            connect_route_options={
                "integration": WebSocketLambdaIntegration("OnConnectIntegration", _lambda.Function.from_function_arn(self, "OnConnectFnImport", "arn:aws:lambda:region:account-id:function:placeholder"))
            },
            disconnect_route_options={
                "integration": WebSocketLambdaIntegration("OnDisconnectIntegration", _lambda.Function.from_function_arn(self, "OnDisconnectFnImport", "arn:aws:lambda:region:account-id:function:placeholder"))
            }
        )
        ws_stage = apigwv2.WebSocketStage(self, "WebSocketStage", web_socket_api=ws_api, stage_name="prod", auto_deploy=True)

        # Lambda OnConnect
        insights_layer = _lambda.LayerVersion.from_layer_version_arn(
            self, "InsightsLayer", "arn:aws:lambda:us-east-1:580247275435:layer:LambdaInsightsExtension:40"
        )
        on_connect_fn = _lambda.Function(
            self, "OnConnectFn",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="on_connect.lambda_handler",
            code=_lambda.Code.from_asset(os.path.join(os.path.dirname(__file__), "../lambda")),
            environment={"CONN_TABLE": connections.table_name},
            layers=[insights_layer]
        )
        on_disconnect_fn = _lambda.Function(
            self, "OnDisconnectFn",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="on_disconnect.lambda_handler",
            code=_lambda.Code.from_asset(os.path.join(os.path.dirname(__file__), "../lambda")),
            environment={"CONN_TABLE": connections.table_name},
            retry_attempts=0,
            layers=[insights_layer]
        )
        push_fn = _lambda.Function(
            self, "ResultPushFn",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="result_push.lambda_handler",
            code=_lambda.Code.from_asset(os.path.join(os.path.dirname(__file__), "../lambda")),
            environment={
                "CONN_TABLE": connections.table_name,
                "WS_CALLBACK_URL": f"https://{ws_api.api_id}.execute-api.{self.region}.amazonaws.com/{ws_stage.stage_name}"
            },
            layers=[insights_layer]
        )
        # SQS event source con batch/concurrency
        from aws_cdk.aws_lambda_event_sources import SqsEventSource
        push_fn.add_event_source(SqsEventSource(results_q, batch_size=5, max_concurrency=10))
        results_q.grant_consume_messages(push_fn)
        # Log retention 1 giorno + Lambda Insights policy
        for fn in [on_connect_fn, on_disconnect_fn, push_fn]:
            logs.LogGroup(self, f"{fn.node.id}Logs",
                log_group_name=f"/aws/lambda/{fn.function_name}",
                removal_policy=RemovalPolicy.DESTROY,
                retention=logs.RetentionDays.ONE_DAY,
            )
            fn.role.add_managed_policy(
                iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchLambdaInsightsExecutionRolePolicy")
            )
        connections.grant_read_write_data(on_connect_fn)
        connections.grant_read_write_data(on_disconnect_fn)
        connections.grant_read_write_data(push_fn)
        push_fn.add_to_role_policy(iam.PolicyStatement(
            actions=["execute-api:ManageConnections"],
            resources=[f"arn:aws:execute-api:{self.region}:{self.account}:{ws_api.api_id}/*"]
        ))

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
                    "RESULT_QUEUE_URL": results_q.queue_url
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
            # Permesso per inviare SOLO alla results_q
            results_q.grant_send_messages(task.task_role)
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

        for algo in algos:
            CfnOutput(self, f"ImageRequestsQueueUrl{algo}", value=request_queues[algo].queue_url)
        CfnOutput(self, "OutputBucketName",    value=out_bucket.bucket_name)
        CfnOutput(self, "ProcessingApiEndpoint", value=api.url)
        CfnOutput(self, "WebSocketEndpoint", value=f"wss://{ws_api.api_id}.execute-api.{self.region}.amazonaws.com/{ws_stage.stage_name}")
        CfnOutput(self, "ResultsQueueUrl", value=results_q.queue_url)
