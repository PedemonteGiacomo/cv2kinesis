from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as sfn_tasks,
    aws_s3_notifications as s3n,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_ec2 as ec2,
    aws_ecr as ecr,
    aws_sqs as sqs,
    aws_iam as iam,
    aws_kinesis as kinesis,
    RemovalPolicy,
    Duration,
    CfnOutput,
    aws_lambda as _lambda,
    aws_lambda_event_sources as lambda_event_sources
)
from constructs import Construct
import os
import boto3
import botocore

class HybridPipelineStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)
        account = self.account
        region = self.region
        session = boto3.session.Session(region_name=region)
        s3_client = session.client('s3')
        ecr_client = session.client('ecr')
        sqs_client = session.client('sqs')
        kinesis_client = session.client('kinesis')

        def bucket_exists(name):
            try:
                s3_client.head_bucket(Bucket=name)
                return True
            except botocore.exceptions.ClientError:
                return False
        def ecr_exists(name):
            try:
                ecr_client.describe_repositories(repositoryNames=[name])
                return True
            except botocore.exceptions.ClientError:
                return False
        def sqs_exists(name):
            try:
                queues = sqs_client.list_queues(QueueNamePrefix=name).get('QueueUrls', [])
                return any(name in q for q in queues)
            except botocore.exceptions.ClientError:
                return False
        def kinesis_exists(name):
            try:
                streams = kinesis_client.list_streams()['StreamNames']
                return name in streams
            except botocore.exceptions.ClientError:
                return False

        # S3 Buckets for images
        image_input_name = f"images-input-{account}-{region}"
        # Forza sempre la creazione come nuovo bucket per trigger S3 → Lambda
        image_input_bucket = s3.Bucket(self, "ImageInputBucket", bucket_name=image_input_name, removal_policy=RemovalPolicy.DESTROY, auto_delete_objects=True)

        image_output_name = f"images-output-{account}-{region}"
        image_output_bucket = s3.Bucket(self, "ImageOutputBucket", bucket_name=image_output_name, removal_policy=RemovalPolicy.DESTROY, auto_delete_objects=True)

        # SQS Queue for image processing results
        image_processing_name = "ImageProcessingQueue"
        image_processing_arn = f"arn:aws:sqs:{region}:{account}:{image_processing_name}"
        if sqs_exists(image_processing_name):
            image_processing_queue = sqs.Queue.from_queue_arn(self, "ImageProcessingQueue", image_processing_arn)
        else:
            image_processing_queue = sqs.Queue(self, "ImageProcessingQueue", visibility_timeout=Duration.seconds(300), retention_period=Duration.days(14))

        # ECR Repository for the grayscale service
        grayscale_ecr_name = "hybrid-pipeline-grayscale"
        if ecr_exists(grayscale_ecr_name):
            grayscale_ecr_repository = ecr.Repository.from_repository_name(self, "GrayscaleRepository", grayscale_ecr_name)
        else:
            grayscale_ecr_repository = ecr.Repository(self, "GrayscaleRepository", repository_name=grayscale_ecr_name, removal_policy=RemovalPolicy.DESTROY)

        # S3 bucket for video frames and processed results
        video_frames_name = f"video-frames-{account}-{region}"
        if bucket_exists(video_frames_name):
            video_frames_bucket = s3.Bucket.from_bucket_name(self, "VideoFramesBucket", video_frames_name)
        else:
            video_frames_bucket = s3.Bucket(self, "VideoFramesBucket", bucket_name=video_frames_name, removal_policy=RemovalPolicy.DESTROY, auto_delete_objects=True)

        # S3 bucket for video input
        video_input_name = f"videos-input-{account}-{region}"
        if bucket_exists(video_input_name):
            video_input_bucket = s3.Bucket.from_bucket_name(self, "VideoInputBucket", video_input_name)
        else:
            video_input_bucket = s3.Bucket(self, "VideoInputBucket", bucket_name=video_input_name, removal_policy=RemovalPolicy.DESTROY, auto_delete_objects=True)

        # SQS queue for video processing results (FIFO)
        video_processing_name = f"video-processing-results-{account}.fifo"
        video_processing_queue = sqs.Queue(
            self,
            "VideoProcessingQueue",
            queue_name=video_processing_name,
            fifo=True,
            content_based_deduplication=True,
            visibility_timeout=Duration.seconds(300),
            removal_policy=RemovalPolicy.RETAIN
        )

        # Kinesis stream for video frames
        kinesis_stream_name = "cv2kinesis-hybrid"
        kinesis_stream_arn = f"arn:aws:kinesis:{region}:{account}:stream/{kinesis_stream_name}"
        if kinesis_exists(kinesis_stream_name):
            video_stream = kinesis.Stream.from_stream_arn(self, "VideoFrameStream", kinesis_stream_arn)
        else:
            video_stream = kinesis.Stream(self, "VideoFrameStream", stream_name=kinesis_stream_name)

        # ECR Repository for the video stream service
        stream_ecr_name = "hybrid-pipeline-stream"
        if ecr_exists(stream_ecr_name):
            stream_ecr_repository = ecr.Repository.from_repository_name(self, "StreamRepository", stream_ecr_name)
        else:
            stream_ecr_repository = ecr.Repository(self, "StreamRepository", repository_name=stream_ecr_name, removal_policy=RemovalPolicy.DESTROY)

        # ===========================================
        # SHARED INFRASTRUCTURE
        # ===========================================
        vpc = ec2.Vpc(self, "HybridVpc", max_azs=2)
        cluster = ecs.Cluster(self, "HybridCluster", vpc=vpc)

        # ===========================================
        # IMAGE PROCESSING PIPELINE
        # ===========================================

        # ECS Task Definition for grayscale processing
        grayscale_task_definition = ecs.FargateTaskDefinition(
            self,
            "GrayscaleTaskDefinition",
            cpu=1024,
            memory_limit_mib=2048,
        )

        # Grayscale container definition
        grayscale_container = grayscale_task_definition.add_container(
            "GrayscaleContainer",
            image=ecs.ContainerImage.from_ecr_repository(grayscale_ecr_repository, "latest"),
            environment={
                "INPUT_BUCKET": image_input_bucket.bucket_name,
                "OUTPUT_BUCKET": image_output_bucket.bucket_name,
                "QUEUE_URL": image_processing_queue.queue_url,
                "AWS_DEFAULT_REGION": self.region
            },
            logging=ecs.LogDrivers.aws_logs(stream_prefix="grayscale")
        )

        # Grant permissions to the grayscale task
        image_input_bucket.grant_read(grayscale_task_definition.task_role)
        image_output_bucket.grant_write(grayscale_task_definition.task_role)
        image_processing_queue.grant_send_messages(grayscale_task_definition.task_role)
        # Policy IAM esplicita per S3 (PutObject, GetObject, ListBucket) e SQS
        grayscale_task_definition.task_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "s3:PutObject",
                "s3:GetObject",
                "s3:ListBucket"
            ],
            resources=[
                image_output_bucket.bucket_arn,
                f"{image_output_bucket.bucket_arn}/*",
                image_input_bucket.bucket_arn,
                f"{image_input_bucket.bucket_arn}/*"
            ]
        ))
        grayscale_task_definition.task_role.add_to_policy(iam.PolicyStatement(
            actions=["sqs:SendMessage", "sqs:GetQueueAttributes", "sqs:ReceiveMessage"],
            resources=[image_processing_queue.queue_arn]
        ))

        # ===========================================
        
        # ECS Task Definition for video stream processing
        stream_task_definition = ecs.FargateTaskDefinition(
            self,
            "StreamTaskDefinition",
            cpu=2048,  # More CPU for YOLO processing
            memory_limit_mib=4096,  # More memory for YOLO processing
        )

        # Stream container definition
        image_uri = (
            self.node.try_get_context("stream_image_uri")
            or os.environ.get("STREAM_IMAGE_URI")
            or f"{stream_ecr_repository.repository_uri}:latest"
        )

        # Handle ECR repository permissions properly
        if ".dkr.ecr." in image_uri and ".amazonaws.com" in image_uri:
            container_image = ecs.ContainerImage.from_ecr_repository(stream_ecr_repository, "latest")
        else:
            container_image = ecs.ContainerImage.from_registry(image_uri)

        stream_container = stream_task_definition.add_container(
            "StreamContainer",
            image=container_image,
            logging=ecs.LogDrivers.aws_logs(stream_prefix="yolo-stream"),
            environment={
                "KINESIS_STREAM_NAME": video_stream.stream_name,
                "S3_BUCKET_NAME": video_frames_bucket.bucket_name,
                "SQS_QUEUE_URL": video_processing_queue.queue_url,
                "AWS_REGION": self.region,
                "YOLO_MODEL": "yolov8n.pt",
                "THRESHOLD": "0.5",
            },
        )
        stream_container.add_port_mappings(ecs.PortMapping(container_port=8080))

        # Add ECR permissions
        ecr_policy = iam.PolicyStatement(
            actions=[
                "ecr:GetAuthorizationToken",
                "ecr:BatchCheckLayerAvailability", 
                "ecr:GetDownloadUrlForLayer",
                "ecr:BatchGetImage",
            ],
            resources=["*"],
        )
        
        stream_task_definition.execution_role.add_to_policy(ecr_policy)
        stream_task_definition.task_role.add_to_policy(ecr_policy)
        
        # CloudWatch logs permissions
        stream_task_definition.execution_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream", 
                    "logs:PutLogEvents",
                ],
                resources=["*"],
            )
        )

        # Grant permissions to the video stream task
        video_stream.grant_read(stream_task_definition.task_role)
        video_frames_bucket.grant_read_write(stream_task_definition.task_role)
        launch_target=sfn_tasks.EcsFargateLaunchTarget(platform_version=ecs.FargatePlatformVersion.LATEST),

        # ECS Service for video stream processing (always running)
        video_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "VideoStreamService",
            cluster=cluster,
            task_definition=stream_task_definition,
            desired_count=1,
            public_load_balancer=True,
            listener_port=80,
            platform_version=ecs.FargatePlatformVersion.LATEST,
        )
        
        # Configure health check
        video_service.target_group.configure_health_check(
            path="/health",
            port="8080",
            healthy_http_codes="200",
            interval=Duration.seconds(30),
            timeout=Duration.seconds(5),
            healthy_threshold_count=2,
            unhealthy_threshold_count=5,
        )

        # ===========================================
        # STEP FUNCTIONS - IMAGE PROCESSING WORKFLOW
        # ===========================================
        
        # Define the ECS task for image processing
        image_grayscale_task = sfn_tasks.EcsRunTask(
            self, "ImageGrayscaleTask",
            integration_pattern=sfn.IntegrationPattern.RUN_JOB,
            cluster=cluster,
            task_definition=grayscale_task_definition,
            launch_target=sfn_tasks.EcsFargateLaunchTarget(platform_version=ecs.FargatePlatformVersion.LATEST),
            container_overrides=[
                sfn_tasks.ContainerOverride(
                    container_definition=grayscale_container,
                    environment=[
                        sfn_tasks.TaskEnvironmentVariable(
                            name="IMAGE_KEY",
                            value=sfn.JsonPath.string_at("$.Records[0].s3.object.key")
                        ),
                        sfn_tasks.TaskEnvironmentVariable(
                            name="SOURCE_BUCKET", 
                            value=sfn.JsonPath.string_at("$.Records[0].s3.bucket.name")
                        )
                    ]
                )
            ]
        )

        # Define the image processing state machine
        image_processing_machine = sfn.StateMachine(
            self, "ImageProcessingStateMachine",
            definition_body=sfn.DefinitionBody.from_chainable(image_grayscale_task),
            timeout=Duration.minutes(15)
        )

        # ===========================================
        # STEP FUNCTIONS - VIDEO PROCESSING WORKFLOW  
        # ===========================================
        
        # TODO: Video workflow will be added here
        # For now, video processing runs continuously via ECS service
        
        # ===========================================
        # S3 EVENT TRIGGERS
        # ===========================================

        # Lambda dispatcher già creato sopra
        # (Assicurati che la definizione sia presente prima di questa sezione)

        # Dispatcher Lambda per S3 -> Step Functions
        dispatcher_lambda = _lambda.Function(
            self,
            "ImageS3DispatcherLambda",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="dispatcher.main",
            code=_lambda.Code.from_asset(os.path.join(os.path.dirname(__file__), "..", "lambda", "dispatcher")),
            environment={
                "STATE_MACHINE_ARN": image_processing_machine.state_machine_arn
            },
            timeout=Duration.seconds(30)
        )
        image_input_bucket.grant_read(dispatcher_lambda)
        image_processing_machine.grant_start_execution(dispatcher_lambda)

        # S3 trigger per dispatcher Lambda (solo per file immagine)
        dispatcher_lambda.add_event_source(
            lambda_event_sources.S3EventSource(
                image_input_bucket,
                events=[s3.EventType.OBJECT_CREATED],
                filters=[{"suffix": ".jpg"}]
            )
        )
        dispatcher_lambda.add_event_source(
            lambda_event_sources.S3EventSource(
                image_input_bucket,
                events=[s3.EventType.OBJECT_CREATED],
                filters=[{"suffix": ".png"}]
            )
        )

        # ===========================================
        # OUTPUTS
        # ===========================================
        
        # Image Processing Outputs
        CfnOutput(
            self, "ImageInputBucketName",
            value=image_input_bucket.bucket_name,
            description="S3 bucket for input images"
        )
        
        CfnOutput(
            self, "ImageOutputBucketName", 
            value=image_output_bucket.bucket_name,
            description="S3 bucket for processed images"
        )
        
        CfnOutput(
            self, "GrayscaleECRRepositoryURI",
            value=grayscale_ecr_repository.repository_uri,
            description="ECR repository for grayscale service container"
        )
        
        CfnOutput(
            self, "ImageProcessingStateMachineArn",
            value=image_processing_machine.state_machine_arn,
            description="Step Functions state machine ARN for image processing"
        )
        
        # Video Processing Outputs
        CfnOutput(
            self, "VideoInputBucketName",
            value=video_input_bucket.bucket_name,
            description="S3 bucket for input videos"
        )
        
        CfnOutput(
            self, "VideoFramesBucketName", 
            value=video_frames_bucket.bucket_name,
            description="S3 bucket for video frames and processed results"
        )
        
        CfnOutput(
            self, "StreamECRRepositoryURI",
            value=stream_ecr_repository.repository_uri,
            description="ECR repository for video stream service container"
        )
        
        CfnOutput(
            self, "VideoStreamServiceURL",
            value=f"http://{video_service.load_balancer.load_balancer_dns_name}",
            description="URL to access the video stream service"
        )
        
        CfnOutput(
            self, "KinesisStreamName", 
            value=video_stream.stream_name,
            description="Name of the Kinesis stream for video frames"
        )
        
        CfnOutput(
            self, "VideoProcessingQueueURL", 
            value=video_processing_queue.queue_url,
            description="SQS queue URL for video processing results"
        )
