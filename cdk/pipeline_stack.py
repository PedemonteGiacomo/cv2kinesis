import os
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_kinesis as kinesis,
)
from constructs import Construct


class VideoPipelineStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

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
            or "public.ecr.aws/placeholder/cv2kinesis:latest"
        )

        container = task.add_container(
            "DetectorContainer",
            image=ecs.ContainerImage.from_registry(image_uri),
            logging=ecs.LogDrivers.aws_logs(stream_prefix="yolo"),
            environment={
                "KINESIS_STREAM_NAME": stream.stream_name,
            },
        )
        container.add_port_mappings(ecs.PortMapping(container_port=8080))

        stream.grant_read(task.task_role)

        service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "Service",
            cluster=cluster,
            task_definition=task,
            desired_count=1,
            public_load_balancer=True,
        )

        self.url_output = service.load_balancer.load_balancer_dns_name
        self.stream_name = stream.stream_name
