from aws_cdk import (
    Stack, Duration, RemovalPolicy,
    aws_s3 as s3,
    aws_sqs as sqs,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_applicationautoscaling as appscaling,
    aws_logs as logs,
    aws_lambda as _lambda,
    aws_apigateway as apigw,
    aws_iam as iam,
    aws_dynamodb as ddb,
    aws_apigatewayv2 as apigwv2,
    CfnOutput,
)
from aws_cdk.aws_lambda_python_alpha import PythonFunction
from aws_cdk.aws_apigatewayv2_integrations import WebSocketLambdaIntegration
from constructs import Construct
import os, json

class ImagePipeline(Stack):
    def __init__(self, scope: Construct, _id: str, pacs_api_url: str = None, **kw) -> None:
        super().__init__(scope, _id, **kw)

        # -------------------- VPC / Cluster --------------------
        vpc = ec2.Vpc(self, "ImgVpc", max_azs=2)
        cluster = ecs.Cluster(self, "ImgCluster", vpc=vpc)
        svc_sg = ec2.SecurityGroup(self, "SvcSG", vpc=vpc, allow_all_outbound=True)

        # -------------------- Output & Results --------------------
        out_bucket = s3.Bucket(self, "Output", removal_policy=RemovalPolicy.RETAIN)

        results_q = sqs.Queue(
            self, "ResultsQueue.fifo",
            fifo=True, content_based_deduplication=True,
            visibility_timeout=Duration.minutes(15),
            queue_name="ResultsQueue.fifo"
        )

        # -------------------- Connections & WebSocket --------------------
        connections = ddb.Table(
            self, "Connections",
            partition_key=ddb.Attribute(name="client_id", type=ddb.AttributeType.STRING),
            removal_policy=RemovalPolicy.DESTROY,
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST
        )
        connections.add_global_secondary_index(
            index_name="ByConnection",
            partition_key=ddb.Attribute(name="connectionId", type=ddb.AttributeType.STRING)
        )

        insights_layer = _lambda.LayerVersion.from_layer_version_arn(
            self, "InsightsLayer", f"arn:aws:lambda:{self.region}:580247275435:layer:LambdaInsightsExtension:40"
        )

        lambda_dir = os.path.join(os.path.dirname(__file__), "../lambda")
        on_connect_fn = PythonFunction(
            self, "OnConnectFn",
            entry=lambda_dir, runtime=_lambda.Runtime.PYTHON_3_11,
            index="on_connect.py", handler="lambda_handler",
            environment={"CONN_TABLE": connections.table_name},
            layers=[insights_layer]
        )
        on_disconnect_fn = PythonFunction(
            self, "OnDisconnectFn",
            entry=lambda_dir, runtime=_lambda.Runtime.PYTHON_3_11,
            index="on_disconnect.py", handler="lambda_handler",
            environment={"CONN_TABLE": connections.table_name},
            retry_attempts=0, layers=[insights_layer]
        )

        ws_api = apigwv2.WebSocketApi(
            self, "WebSocketApi",
            connect_route_options={"integration": WebSocketLambdaIntegration("OnConnectIntegration", on_connect_fn)},
            disconnect_route_options={"integration": WebSocketLambdaIntegration("OnDisconnectIntegration", on_disconnect_fn)}
        )
        ws_stage = apigwv2.WebSocketStage(self, "WebSocketStage", web_socket_api=ws_api, stage_name="prod", auto_deploy=True)

        push_fn = PythonFunction(
            self, "ResultPushFn",
            entry=lambda_dir, runtime=_lambda.Runtime.PYTHON_3_11,
            index="result_push.py", handler="lambda_handler",
            environment={"CONN_TABLE": connections.table_name},
            layers=[insights_layer]
        )
        from aws_cdk.aws_lambda_event_sources import SqsEventSource
        push_fn.add_event_source(SqsEventSource(results_q, batch_size=5, max_concurrency=10))
        results_q.grant_consume_messages(push_fn)

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

        # -------------------- Algorithm Registry (DynamoDB) --------------------
        algo_registry = ddb.Table(
            self, "AlgorithmRegistry",
            partition_key=ddb.Attribute(name="algorithm_id", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY
        )

        # -------------------- ECS Roles riutilizzabili --------------------
        task_exec_role = iam.Role(
            self, "MipTaskExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonECSTaskExecutionRolePolicy")]
        )
        task_role = iam.Role(
            self, "MipTaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )
        out_bucket.grant_read_write(task_role)
        results_q.grant_send_messages(task_role)

        # -------------------- API Gateway (Processing + Admin) --------------------
        api = apigw.RestApi(self, "ProcessingApi",
            rest_api_name="ImageProcessing API",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "Authorization", "x-admin-key"]
            )
        )

        # router dinamico
        router = PythonFunction(
            self, "DynamicRouterFn",
            entry=lambda_dir, runtime=_lambda.Runtime.PYTHON_3_11,
            index="dynamic_router.py", handler="lambda_handler",
            environment={"ALGO_TABLE": algo_registry.table_name}
        )
        algo_registry.grant_read_data(router)
        # Permesso per inviare messaggi a tutte le code Requests-*.fifo
        router.add_to_role_policy(iam.PolicyStatement(
            actions=["sqs:SendMessage"],
            resources=[f"arn:aws:sqs:{self.region}:{self.account}:Requests-*.fifo"]
        ))

        proc = api.root.add_resource("process")
        algo = proc.add_resource("{algo_id}")
        algo.add_method("POST", apigw.LambdaIntegration(router))

        # admin (cognito jwt auth)
        admin = PythonFunction(
            self, "AdminAlgosFn",
            entry=lambda_dir, runtime=_lambda.Runtime.PYTHON_3_11,
            index="algos_admin.py", handler="handler",
            environment={
                "ALGO_TABLE": algo_registry.table_name,
                "USER_POOL_ID_PARAM": "/mip/admin/user-pool-id",  # SSM Parameter path
                "USER_POOL_REGION": self.region,
                "PROVISIONER_ARN": "dummy"  # placeholder, lo settiamo sotto
            }
        )
        algo_registry.grant_read_write_data(admin)
        
        # Grant permission to read SSM parameter
        admin.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameter"],
                resources=[f"arn:aws:ssm:{self.region}:{self.account}:parameter/mip/admin/user-pool-id"]
            )
        )

        admin_root = api.root.add_resource("admin").add_resource("algorithms")
        admin_root.add_method("GET",  apigw.LambdaIntegration(admin))
        admin_root.add_method("POST", apigw.LambdaIntegration(admin))
        admin_item = admin_root.add_resource("{algo_id}")
        admin_item.add_method("GET",    apigw.LambdaIntegration(admin))
        admin_item.add_method("PATCH",  apigw.LambdaIntegration(admin))
        admin_item.add_method("DELETE", apigw.LambdaIntegration(admin))

        # -------------------- Provisioner Lambda --------------------
        provisioner = PythonFunction(
            self, "ProvisionerFn",
            entry=lambda_dir, runtime=_lambda.Runtime.PYTHON_3_11,
            index="provisioner.py", handler="handler",
            timeout=Duration.minutes(5),
            environment={
                "ALGO_TABLE": algo_registry.table_name,
                "ECS_CLUSTER_NAME": cluster.cluster_name,
                "VPC_ID": vpc.vpc_id,
                "SUBNETS_JSON": json.dumps([sn.subnet_id for sn in vpc.private_subnets[:2]] or [sn.subnet_id for sn in vpc.public_subnets[:2]]),
                "SERVICE_SG": svc_sg.security_group_id,
                "RESULTS_QUEUE_URL": results_q.queue_url,
                "OUTPUT_BUCKET": out_bucket.bucket_name,
                "PACS_API_URL": pacs_api_url or "",
                "PACS_API_KEY": "devkey",
                "TASK_EXEC_ROLE_ARN": task_exec_role.role_arn,
                "TASK_ROLE_ARN": task_role.role_arn,
            }
        )
        # Log group per la Lambda ProvisionerFn
        logs.LogGroup(self, f"{provisioner.node.id}Logs",
            log_group_name=f"/aws/lambda/{provisioner.function_name}",
            removal_policy=RemovalPolicy.DESTROY,
            retention=logs.RetentionDays.ONE_DAY,
        )
        # permessi provisioning
        algo_registry.grant_read_write_data(provisioner)
        provisioner.add_to_role_policy(iam.PolicyStatement(actions=[
            "sqs:CreateQueue","sqs:GetQueueAttributes","sqs:SetQueueAttributes"
        ], resources=["*"]))
        provisioner.add_to_role_policy(iam.PolicyStatement(actions=[
            "ecs:RegisterTaskDefinition","ecs:DescribeTaskDefinition",
            "ecs:CreateService","ecs:UpdateService","ecs:DescribeServices","ecs:DeleteService"
        ], resources=["*"]))
        provisioner.add_to_role_policy(iam.PolicyStatement(actions=[
            "iam:PutRolePolicy","iam:GetRolePolicy"
        ], resources=[task_role.role_arn]))
        provisioner.add_to_role_policy(iam.PolicyStatement(actions=[
            "logs:CreateLogGroup","logs:PutRetentionPolicy","logs:CreateLogStream","logs:DescribeLogGroups"
        ], resources=["*"]))
        # Permesso necessario per ECS:PassRole su entrambi i ruoli ECS (task e execution)
        provisioner.add_to_role_policy(iam.PolicyStatement(
            actions=["iam:PassRole"],
            resources=[task_role.role_arn, task_exec_role.role_arn]
        ))

        # collega l'ARN del provisioner nell'admin
        admin.add_environment("PROVISIONER_ARN", provisioner.function_arn)
        # Permesso per invocare la Lambda di provisioning
        admin.add_to_role_policy(
            iam.PolicyStatement(
                actions=["lambda:InvokeFunction"],
                resources=[provisioner.function_arn]
            )
        )
        # RIMOSSO: admin.grant_invoke(provisioner) per evitare dipendenza circolare

        # push lambda: aggiungi callback URL WS
        push_fn.add_environment(
            "WS_CALLBACK_URL",
            f"https://{ws_api.api_id}.execute-api.{self.region}.amazonaws.com/{ws_stage.stage_name}"
        )

        # -------------------- Outputs --------------------
        CfnOutput(self, "OutputBucketName",    value=out_bucket.bucket_name)
        CfnOutput(self, "ProcessingApiEndpoint", value=api.url)
        CfnOutput(self, "WebSocketEndpoint", value=f"wss://{ws_api.api_id}.execute-api.{self.region}.amazonaws.com/{ws_stage.stage_name}")
        CfnOutput(self, "ResultsQueueUrl", value=results_q.queue_url)
        CfnOutput(self, "ClusterName", value=cluster.cluster_name)
        CfnOutput(self, "TaskRoleArn", value=task_role.role_arn)
        CfnOutput(self, "TaskExecutionRoleArn", value=task_exec_role.role_arn)
        CfnOutput(self, "AlgoTableName", value=algo_registry.table_name)
        
        # Export API Gateway URL for use in AdminStack
        CfnOutput(
            self, "ApiGatewayUrl",
            value=api.url,
            export_name="ImgPipelineApiGatewayUrl"
        )
        
        # Store references for other stacks
        self.vpc = vpc
        self.ecs_cluster = cluster
        self.admin_function = admin
        self.api_gateway = api
