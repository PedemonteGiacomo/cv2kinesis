import os
from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_kinesis as kinesis,
    aws_cloudwatch as cw,
    aws_applicationautoscaling as appscaling,
    aws_ecr as ecr,
    aws_iam as iam,
    aws_s3 as s3,
    aws_sqs as sqs,
    CfnOutput,
)
from constructs import Construct


class VideoPipelineStack(Stack):
    """Webcam → Kinesis (EFO) → ECS YOLO → S3 + SQS – autoscaling & dashboard"""

    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Get suffix from context for resource naming
        suffix = self.node.try_get_context("suffix") or ""
        print(f"🏷️ Using suffix: '{suffix}' for resource names")

        # ------------------------------------------------------------------#
        # 📦 STORAGE (S3 + SQS)
        # ------------------------------------------------------------------#
        processed_frames_bucket = s3.Bucket(
            self,
            "ProcessedFramesBucket",
            bucket_name=f"processedframes-{self.account}-{self.region}{suffix}",
            removal_policy=RemovalPolicy.DESTROY,             # demo-only
            auto_delete_objects=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
        )

        processing_queue = sqs.Queue(
            self,
            "ProcessingResultsQueue",
            queue_name=f"processing-results{suffix}",
            visibility_timeout=Duration.seconds(300),
        )

        # ------------------------------------------------------------------#
        # 📡 KINESIS STREAM (ON_DEMAND + Enhanced Fan-Out)
        # ------------------------------------------------------------------#
        stream = kinesis.Stream(
            self,
            "FrameStream",
            stream_name=f"cv2kinesis{suffix}",
            stream_mode=kinesis.StreamMode.ON_DEMAND,
            encryption=kinesis.StreamEncryption.MANAGED,
            removal_policy=RemovalPolicy.DESTROY,             # demo-only
        )

        efo_consumer = kinesis.CfnStreamConsumer(
            self,
            "ECSConsumer",
            consumer_name=f"ecs-consumer{suffix}",
            stream_arn=stream.stream_arn,
        )

        # ------------------------------------------------------------------#
        # ☁️ NETWORK & ECS CLUSTER
        # ------------------------------------------------------------------#
        vpc     = ec2.Vpc(self, "Vpc", max_azs=2)
        cluster = ecs.Cluster(self, "Cluster", vpc=vpc)

        task = ecs.FargateTaskDefinition(
            self, "TaskDef",
            cpu=2048,
            memory_limit_mib=4096,
        )

        # Docker image (passa con -c image_uri=…  oppure var IMAGE_URI)
        image_uri = (
            self.node.try_get_context("image_uri")
            or os.environ.get("IMAGE_URI")
            or "000000000000.dkr.ecr.eu-central-1.amazonaws.com/cv2kinesis:latest"
        )
        
        print(f"🐳 Using Docker image: {image_uri}")
        
        if ".dkr.ecr." in image_uri:
            # Parse repository name and tag correctly
            image_parts = image_uri.split("/")[-1]  # cv2kinesis:test
            if ":" in image_parts:
                repo_name, tag = image_parts.split(":", 1)  # cv2kinesis, test
            else:
                repo_name = image_parts
                tag = "latest"
            
            print(f"📦 ECR Repository: {repo_name}, Tag: {tag}")
            ecr_repo = ecr.Repository.from_repository_name(self, "ECRRepo", repo_name)
            container_image = ecs.ContainerImage.from_ecr_repository(ecr_repo, tag=tag)
        else:
            container_image = ecs.ContainerImage.from_registry(image_uri)

        container = task.add_container(
            "Detector",
            image=container_image,
            logging=ecs.LogDrivers.aws_logs(stream_prefix="yolo"),
            environment={
                "AWS_REGION":                self.region,
                "KINESIS_STREAM_ARN":        stream.stream_arn,
                "KINESIS_CONSUMER_ARN":      efo_consumer.attr_consumer_arn,
                "S3_BUCKET_NAME":            processed_frames_bucket.bucket_name,
                "SQS_QUEUE_URL":             processing_queue.queue_url,
                "YOLO_MODEL":                "yolov8n.pt",
                "THRESHOLD":                 "0.8",
                "POOL_SIZE":                 "4",      # worker processes
                "MAX_QUEUE_LEN":             "100",
            },
        )
        container.add_port_mappings(ecs.PortMapping(container_port=8080))

        # ------------------------------------------------------------------#
        # 🔐 PERMISSIONS
        # ------------------------------------------------------------------#
        # Pull from ECR
        ecr_policy = iam.PolicyStatement(
            actions=[
                "ecr:GetAuthorizationToken",
                "ecr:BatchCheckLayerAvailability",
                "ecr:GetDownloadUrlForLayer",
                "ecr:BatchGetImage",
            ],
            resources=["*"],
        )
        task.execution_role.add_to_policy(ecr_policy)
        task.task_role.add_to_policy(ecr_policy)

        # Logs
        task.execution_role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
                resources=["*"],
            )
        )

        # Access to Kinesis / S3 / SQS
        stream.grant_read(task.task_role)
        stream.grant(task.task_role, "kinesis:SubscribeToShard", "kinesis:DescribeStreamConsumer") # added for EFO
        processed_frames_bucket.grant_read_write(task.task_role)
        processing_queue.grant_send_messages(task.task_role)

        # ------------------------------------------------------------------#
        # 🐳 FARGATE SERVICE (+ ALB)
        # ------------------------------------------------------------------#
        service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "Service",
            cluster=cluster,
            task_definition=task,
            desired_count=1,
            public_load_balancer=True,
            listener_port=80,
            platform_version=ecs.FargatePlatformVersion.LATEST,
        )
        service.target_group.configure_health_check(
            path="/health",
            port="8080",
            healthy_http_codes="200",
            interval=Duration.seconds(30),
            timeout=Duration.seconds(5),
            healthy_threshold_count=2,
            unhealthy_threshold_count=5,
        )

        # ------------------------------------------------------------------#
        # ⚖️ AUTO-SCALING (CPU + lag Kinesis)
        # ------------------------------------------------------------------#
        scalable = service.service.auto_scale_task_count(min_capacity=1, max_capacity=50)

        scalable.scale_on_cpu_utilization(
            "Cpu80",
            target_utilization_percent=80,
            scale_in_cooldown=Duration.minutes(2),
            scale_out_cooldown=Duration.seconds(30),
        )

        scalable.scale_on_metric(
            "KinesisLag",
            metric=cw.Metric(
                namespace="Cv2Kinesis",
                metric_name="MillisBehindLatest",
                dimensions_map={"Service": "Detector"},
                statistic="Average",
                period=Duration.minutes(1)
            ),
            scaling_steps=[
                {"lower": 5_000,  "change": +1},   # >5 s lag  → +1 task
                {"lower": 30_000, "change": +3},   # >30 s     → +3
            ],
            adjustment_type=appscaling.AdjustmentType.CHANGE_IN_CAPACITY,
        )

        # ------------------------------------------------------------------#
        # 📊 DASHBOARD
        # ------------------------------------------------------------------#
        dashboard = cw.Dashboard(
            self, "VideoPipelineDashboard",
            dashboard_name=f"VideoPipeline-{self.stack_name}"
        )
        dashboard.add_widgets(
            cw.GraphWidget(
                title="Kinesis IncomingBytes / IncomingRecords",
                left=[stream.metric("IncomingBytes", statistic="Sum")],
                right=[stream.metric("IncomingRecords", statistic="Sum")],
                left_y_axis=cw.YAxisProps(label="Bytes"),
                right_y_axis=cw.YAxisProps(label="Records"),
            ),
            cw.SingleValueWidget(
                title="Lag stream (ms)",
                metrics=[cw.Metric(
                    namespace="Cv2Kinesis",
                    metric_name="MillisBehindLatest",
                    dimensions_map={"Service": "Detector"},
                    statistic="Average",
                    period=Duration.minutes(1)
                )],
            ),
        )

        # ------------------------------------------------------------------#
        # 🌐 OUTPUTS
        # ------------------------------------------------------------------#
        CfnOutput(self, "LoadBalancerURL",
                  value=f"http://{service.load_balancer.load_balancer_dns_name}")
        CfnOutput(self, "KinesisStreamName", value=stream.stream_name)
        CfnOutput(self, "KinesisConsumerARN", value=efo_consumer.attr_consumer_arn)
        CfnOutput(self, "S3BucketName", value=processed_frames_bucket.bucket_name)
        CfnOutput(self, "SQSQueueURL", value=processing_queue.queue_url)
        CfnOutput(self, "DashboardURL",
                  value=f"https://{self.region}.console.aws.amazon.com/cloudwatch/home?region={self.region}#dashboards:name={dashboard.dashboard_name}")
