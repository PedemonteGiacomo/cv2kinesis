from __future__ import annotations
import os

import aws_cdk as cdk
from aws_cdk import (
    Duration,
    RemovalPolicy,
    Stack,
    CfnOutput,
)
from constructs import Construct

from aws_cdk import (
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_ecr as ecr,
    aws_iam as iam,
    aws_kinesis as kinesis,
    aws_lambda as _lambda,
    aws_s3 as s3,
    aws_s3_notifications as s3n,
    aws_sqs as sqs,
)


class HybridPipelineStack(Stack):
    """Deploy both the video pipeline and the image-processing pipeline."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        stage: str = "dev",
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        suffix = f"-{stage}"
        is_prod = stage.lower() == "prod"

        processed_frames_bucket = s3.Bucket(
            self,
            "ProcessedFramesBucket",
            bucket_name=f"processedframes{suffix}-{self.account}-{self.region}",
            removal_policy=RemovalPolicy.RETAIN if is_prod else RemovalPolicy.DESTROY,
            auto_delete_objects=not is_prod,
            versioned=is_prod,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
        )

        processing_queue = sqs.Queue(
            self,
            "ProcessingResultsQueue",
            queue_name=f"processing-results{suffix}.fifo",
            fifo=True,
            content_based_deduplication=True,
            visibility_timeout=Duration.seconds(300),
            removal_policy=RemovalPolicy.RETAIN if is_prod else RemovalPolicy.DESTROY,
        )

        stream = kinesis.Stream(
            self,
            "FrameStream",
            stream_name=f"cv2kinesis{suffix}",
            shard_count=1,
            retention_period=cdk.Duration.hours(24),
        )
        stream.apply_removal_policy(
            RemovalPolicy.RETAIN if is_prod else RemovalPolicy.DESTROY
        )

        vpc = ec2.Vpc(self, "Vpc", max_azs=2)
        cluster = ecs.Cluster(self, "Cluster", vpc=vpc)

        task = ecs.FargateTaskDefinition(
            self, "TaskDef", cpu=1024, memory_limit_mib=2048
        )

        image_uri = (
            self.node.try_get_context("image_uri")
            or os.environ.get("IMAGE_URI")
            or f"{self.account}.dkr.ecr.{self.region}.amazonaws.com/cv2kinesis:latest"
        )
        if ".dkr.ecr." in image_uri:
            repo_name = image_uri.split("/")[-1].split(":")[0]
            ecr_repo = ecr.Repository.from_repository_name(
                self, "ECRRepository", repo_name
            )
            container_image = ecs.ContainerImage.from_ecr_repository(ecr_repo, "latest")
        else:
            container_image = ecs.ContainerImage.from_registry(image_uri)

        container = task.add_container(
            "DetectorContainer",
            image=container_image,
            logging=ecs.LogDrivers.aws_logs(stream_prefix="yolo" + suffix),
            environment={
                "KINESIS_STREAM_NAME": stream.stream_name,
                "S3_BUCKET_NAME": processed_frames_bucket.bucket_name,
                "SQS_QUEUE_URL": processing_queue.queue_url,
                "AWS_REGION": self.region,
                "YOLO_MODEL": "yolov8n.pt",
                "THRESHOLD": "0.5",
            },
        )
        container.add_port_mappings(ecs.PortMapping(container_port=8080))

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
        task.execution_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=["*"],
            )
        )
        stream.grant_read(task.task_role)
        processed_frames_bucket.grant_read_write(task.task_role)
        processing_queue.grant_send_messages(task.task_role)

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

        raw_images_bucket = s3.Bucket(
            self,
            "RawImagesBucket",
            bucket_name=f"raw-images{suffix}-{self.account}-{self.region}",
            removal_policy=RemovalPolicy.RETAIN if is_prod else RemovalPolicy.DESTROY,
            auto_delete_objects=not is_prod,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            versioned=is_prod,
        )

        processed_images_bucket = s3.Bucket(
            self,
            "ProcessedImagesBucket",
            bucket_name=f"processed-images{suffix}-{self.account}-{self.region}",
            removal_policy=RemovalPolicy.RETAIN if is_prod else RemovalPolicy.DESTROY,
            auto_delete_objects=not is_prod,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            versioned=is_prod,
        )

        grayscale_lambda = _lambda.Function(
            self,
            "GrayscaleLambda",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="handler.main",
            code=_lambda.Code.from_asset(os.path.join("lambda", "grayscale")),
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={"DEST_BUCKET": processed_images_bucket.bucket_name},
        )

        raw_images_bucket.grant_read(grayscale_lambda)
        processed_images_bucket.grant_write(grayscale_lambda)

        notification = s3n.LambdaDestination(grayscale_lambda)
        raw_images_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            notification,
        )

        CfnOutput(
            self,
            "VideoLoadBalancerURL",
            value=f"http://{service.load_balancer.load_balancer_dns_name}",
        )
        CfnOutput(self, "VideoKinesisStream", value=stream.stream_name)
        CfnOutput(
            self, "VideoS3ProcessedFrames", value=processed_frames_bucket.bucket_name
        )
        CfnOutput(self, "VideoSQSQueueURL", value=processing_queue.queue_url)

        CfnOutput(self, "ImageRawBucket", value=raw_images_bucket.bucket_name)
        CfnOutput(
            self, "ImageProcessedBucket", value=processed_images_bucket.bucket_name
        )
        CfnOutput(self, "GrayscaleLambdaArn", value=grayscale_lambda.function_arn)
        CfnOutput(self, "ImageRawBucketArn", value=raw_images_bucket.bucket_arn)
