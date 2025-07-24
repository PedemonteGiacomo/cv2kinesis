from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as patterns,
    aws_iam as iam,
    aws_secretsmanager as secrets,
)
from constructs import Construct
import os, pathlib

class PacsApiStack(Stack):
    def __init__(self, scope: Construct, id: str, *, bucket, **kw):
        super().__init__(scope, id, **kw)

        vpc = ec2.Vpc(self, "PacsVpc", max_azs=2)

        cluster = ecs.Cluster(self, "PacsCluster", vpc=vpc)

        img = ecs.ContainerImage.from_asset(
            path=pathlib.Path(__file__).parent.parent.parent / "pacs_api"
        )

        svc = patterns.ApplicationLoadBalancedFargateService(
            self,
            "PacsApiSvc",
            cluster=cluster,
            cpu=256,
            desired_count=1,
            memory_limit_mib=512,
            task_image_options=patterns.ApplicationLoadBalancedTaskImageOptions(
                image=img,
                environment={
                    "PACS_BUCKET": bucket.bucket_name,
                },
            ),
            public_load_balancer=True,
        )

        # permesso S3 read‑only (+ generate_presigned_url non richiede Put)
        bucket.grant_read(svc.task_definition.task_role)

        # opzionale: export ARN/URL per usare nel resto della pipeline
        self.api_url = svc.load_balancer.load_balancer_dns_name
