import os
from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_kinesis as kinesis,
    aws_ecr as ecr,
    aws_iam as iam,
    aws_s3 as s3,
    aws_sqs as sqs,
    CfnOutput,
)
from constructs import Construct


class VideoPipelineStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # S3 bucket for processed frames
        processed_frames_bucket = s3.Bucket(
            self,
            "ProcessedFramesBucket",
            bucket_name=f"processedframes-{self.account}-{self.region}",
            removal_policy=RemovalPolicy.DESTROY,  # For demo purposes
            auto_delete_objects=True,  # For demo purposes
        )

        # SQS queue for processing results - CAMBIO A FIFO
        processing_queue = sqs.Queue(
            self,
            "ProcessingResultsQueue",
            queue_name="processing-results.fifo",  # .fifo suffix obbligatorio
            fifo=True,  # Abilita FIFO
            content_based_deduplication=True,  # Deduplicazione automatica
            visibility_timeout=Duration.seconds(300),
        )

        # Kinesis stream for frames
        stream = kinesis.Stream(
            self,
            "FrameStream",
            stream_name="cv2kinesis",
        )

        # Networking and ECS cluster
        vpc = ec2.Vpc(self, "Vpc", max_azs=2)
        cluster = ecs.Cluster(self, "Cluster", vpc=vpc)

        task = ecs.FargateTaskDefinition(
            self,
            "TaskDef",
            cpu=1024,
            memory_limit_mib=2048,
        )

        image_uri = (
            self.node.try_get_context("image_uri")
            or os.environ.get("IMAGE_URI")
            or "544547773663.dkr.ecr.eu-central-1.amazonaws.com/cv2kinesis:latest"
        )

        # Handle ECR repository permissions properly
        if ".dkr.ecr." in image_uri and ".amazonaws.com" in image_uri:
            # Extract repository name from ECR URI
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
            logging=ecs.LogDrivers.aws_logs(stream_prefix="yolo"),
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

        # Add ECR permissions to BOTH execution role and task role
        ecr_policy = iam.PolicyStatement(
            actions=[
                "ecr:GetAuthorizationToken",
                "ecr:BatchCheckLayerAvailability", 
                "ecr:GetDownloadUrlForLayer",
                "ecr:BatchGetImage",
            ],
            resources=["*"],
        )
        
        # Execution role needs ECR permissions to pull images
        task.execution_role.add_to_policy(ecr_policy)
        
        # Task role also gets ECR permissions for extra safety
        task.task_role.add_to_policy(ecr_policy)
        
        # CloudWatch logs permissions for execution role
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

        # Grant permissions
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
            # Configure port mapping correctly
            platform_version=ecs.FargatePlatformVersion.LATEST,
        )
        
        # Configure the target group to use the correct port with optimized health check
        service.target_group.configure_health_check(
            path="/health",
            port="8080",
            healthy_http_codes="200",
            interval=Duration.seconds(30),
            timeout=Duration.seconds(5),
            healthy_threshold_count=2,
            unhealthy_threshold_count=5,
        )

        self.url_output = service.load_balancer.load_balancer_dns_name
        self.stream_name = stream.stream_name
        
        # Add outputs
        CfnOutput(self, "LoadBalancerURL", 
                  value=f"http://{service.load_balancer.load_balancer_dns_name}",
                  description="URL to access the video stream")
        CfnOutput(self, "KinesisStreamName", 
                  value=stream.stream_name,
                  description="Name of the Kinesis stream")
        CfnOutput(self, "S3BucketName", 
                  value=processed_frames_bucket.bucket_name,
                  description="S3 bucket for processed frames")
        CfnOutput(self, "SQSQueueURL", 
                  value=processing_queue.queue_url,
                  description="SQS queue URL for processing results")
        CfnOutput(self, "SQSQueueName", 
                  value=processing_queue.queue_name,
                  description="SQS queue name for processing results")
