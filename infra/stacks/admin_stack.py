import os
from aws_cdk import (
    Stack,
    CfnOutput,
    Duration,
    RemovalPolicy,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_ecr as ecr,
    aws_certificatemanager as acm,
    aws_route53 as route53,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_s3 as s3,
    aws_iam as iam,
    aws_cognito as cognito,
    aws_logs as logs,
    aws_elasticloadbalancingv2 as elbv2,
    aws_ssm as ssm,
)
from constructs import Construct


class AdminStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.Vpc,
        api_gateway_url: str,
        domain_name: str = None,
        certificate_arn: str = None,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create dedicated ECS cluster for admin services
        admin_cluster = ecs.Cluster(
            self,
            "AdminCluster",
            vpc=vpc,
            cluster_name=f"{construct_id}-AdminCluster"
        )

        # Reference existing ECR repository for the admin app (created by create-ecr-repos.ps1)
        admin_app_repository = ecr.Repository.from_repository_name(
            self,
            "AdminAppRepository",
            repository_name="mip-admin-portal"
        )

        # Create Cognito User Pool for authentication
        user_pool = cognito.UserPool(
            self,
            "AdminUserPool",
            user_pool_name="mip-admin-users",
            sign_in_aliases=cognito.SignInAliases(email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=True, mutable=True)
            ),
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=True,
            ),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Create Cognito User Pool Client
        user_pool_client = cognito.UserPoolClient(
            self,
            "AdminUserPoolClient",
            user_pool=user_pool,
            user_pool_client_name="mip-admin-client",
            generate_secret=False,  # For frontend applications
            auth_flows=cognito.AuthFlow(
                user_srp=True,
                user_password=True,
            ),
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(
                    authorization_code_grant=True,
                    implicit_code_grant=True,
                ),
                scopes=[
                    cognito.OAuthScope.EMAIL,
                    cognito.OAuthScope.OPENID,
                    cognito.OAuthScope.PROFILE,
                ],
            ),
            refresh_token_validity=Duration.days(30),
            access_token_validity=Duration.hours(24),
            id_token_validity=Duration.hours(24),
        )

        # Create Cognito Groups for role-based access
        admin_group = cognito.CfnUserPoolGroup(
            self,
            "AdminGroup",
            user_pool_id=user_pool.user_pool_id,
            group_name="Administrators",
            description="Full access to algorithm management",
            precedence=1,
        )

        users_group = cognito.CfnUserPoolGroup(
            self,
            "UsersGroup", 
            user_pool_id=user_pool.user_pool_id,
            group_name="Users",
            description="Read-only access to algorithm information",
            precedence=2,
        )

        # Store User Pool ID in SSM Parameter Store for Lambda to access
        ssm.StringParameter(
            self,
            "UserPoolIdParameter",
            parameter_name="/mip/admin/user-pool-id",
            string_value=user_pool.user_pool_id,
            description="Cognito User Pool ID for MIP Admin Portal",
        )

        # Create CloudWatch Log Group
        log_group = logs.LogGroup(
            self,
            "AdminAppLogGroup",
            log_group_name="/aws/ecs/mip-admin-portal",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Create Task Definition
        task_definition = ecs.FargateTaskDefinition(
            self,
            "AdminAppTaskDefinition",
            memory_limit_mib=2048,
            cpu=1024,
        )

        # Add container to task definition
        container = task_definition.add_container(
            "AdminAppContainer",
            image=ecs.ContainerImage.from_ecr_repository(admin_app_repository, "latest"),
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="admin-app",
                log_group=log_group,
            ),
            port_mappings=[
                ecs.PortMapping(
                    container_port=80,
                    protocol=ecs.Protocol.TCP,
                )
            ],
            health_check=ecs.HealthCheck(
                command=["CMD-SHELL", "curl -f http://localhost:80/health || exit 1"],
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
                retries=3,
                start_period=Duration.seconds(60),
            ),
        )

        # Create Security Group for ALB
        alb_security_group = ec2.SecurityGroup(
            self,
            "AdminAppALBSecurityGroup",
            vpc=vpc,
            description="Security group for Admin App ALB",
            allow_all_outbound=True,
        )

        alb_security_group.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(80),
            "Allow HTTP traffic"
        )

        alb_security_group.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(443),
            "Allow HTTPS traffic"
        )

        # Create Security Group for ECS Service
        ecs_security_group = ec2.SecurityGroup(
            self,
            "AdminAppECSSecurityGroup",
            vpc=vpc,
            description="Security group for Admin App ECS Service",
            allow_all_outbound=True,
        )

        ecs_security_group.add_ingress_rule(
            alb_security_group,
            ec2.Port.tcp(80),
            "Allow traffic from ALB"
        )

        # Create Application Load Balanced Fargate Service
        if certificate_arn and domain_name:
            # Use HTTPS with custom domain
            certificate = acm.Certificate.from_certificate_arn(
                self, "AdminAppCertificate", certificate_arn
            )

            fargate_service = ecs_patterns.ApplicationLoadBalancedFargateService(
                self,
                "AdminAppService",
                cluster=admin_cluster,
                task_definition=task_definition,
                public_load_balancer=True,
                listener_port=443,
                protocol=elbv2.ApplicationProtocol.HTTPS,
                certificate=certificate,
                domain_name=domain_name,
                domain_zone=route53.HostedZone.from_lookup(
                    self, "AdminAppHostedZone", domain_name=domain_name.split(".", 1)[1]
                ),
                redirect_http=True,
                desired_count=2,
                assign_public_ip=True,
            )
        else:
            # Use HTTP without custom domain
            fargate_service = ecs_patterns.ApplicationLoadBalancedFargateService(
                self,
                "AdminAppService",
                cluster=admin_cluster,
                task_definition=task_definition,
                public_load_balancer=True,
                listener_port=80,
                protocol=elbv2.ApplicationProtocol.HTTP,
                desired_count=1,
                assign_public_ip=True,
            )

        # Configure service
        fargate_service.service.connections.security_groups[0].add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(80),
            "Allow HTTP traffic"
        )

        # Configure Auto Scaling
        scaling = fargate_service.service.auto_scale_task_count(
            min_capacity=1,
            max_capacity=10,
        )

        scaling.scale_on_cpu_utilization(
            "AdminAppCpuScaling",
            target_utilization_percent=70,
            scale_in_cooldown=Duration.minutes(5),
            scale_out_cooldown=Duration.minutes(2),
        )

        scaling.scale_on_memory_utilization(
            "AdminAppMemoryScaling",
            target_utilization_percent=80,
            scale_in_cooldown=Duration.minutes(5),
            scale_out_cooldown=Duration.minutes(2),
        )

        # Create CloudFront Distribution
        if domain_name:
            distribution_domain_names = [domain_name]
        else:
            distribution_domain_names = []

        cloudfront_distribution = cloudfront.Distribution(
            self,
            "AdminAppCloudFrontDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.LoadBalancerV2Origin(
                    fargate_service.load_balancer,
                    protocol_policy=cloudfront.OriginProtocolPolicy.HTTP_ONLY
                    if not certificate_arn
                    else cloudfront.OriginProtocolPolicy.HTTPS_ONLY,
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                cached_methods=cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
                cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                origin_request_policy=cloudfront.OriginRequestPolicy.CORS_S3_ORIGIN,
                compress=True,
            ),
            domain_names=distribution_domain_names,
            certificate=acm.Certificate.from_certificate_arn(
                self, "CloudFrontCertificate", certificate_arn
            ) if certificate_arn else None,
            minimum_protocol_version=cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.seconds(300),
                ),
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.seconds(300),
                ),
            ],
            comment="MIP Admin Portal CloudFront Distribution",
        )

        CfnOutput(
            self,
            "AdminClusterName",
            value=admin_cluster.cluster_name,
            description="ECS Cluster Name for Admin Services",
        )

        CfnOutput(
            self,
            "AdminAppRepositoryUri",
            value=admin_app_repository.repository_uri,
            description="ECR Repository URI for Admin App",
        )

        CfnOutput(
            self,
            "UserPoolId",
            value=user_pool.user_pool_id,
            description="Cognito User Pool ID",
        )

        CfnOutput(
            self,
            "UserPoolClientId",
            value=user_pool_client.user_pool_client_id,
            description="Cognito User Pool Client ID",
        )

        CfnOutput(
            self,
            "LoadBalancerDNS",
            value=fargate_service.load_balancer.load_balancer_dns_name,
            description="Application Load Balancer DNS name",
        )

        CfnOutput(
            self,
            "CloudFrontURL",
            value=f"https://{cloudfront_distribution.distribution_domain_name}",
            description="CloudFront Distribution URL",
        )

        CfnOutput(
            self,
            "AdminCloudFrontDistributionId",
            value=cloudfront_distribution.distribution_id,
            description="CloudFront Distribution ID for cache invalidation",
        )

        if domain_name:
            CfnOutput(
                self,
                "AdminPortalURL",
                value=f"https://{domain_name}",
                description="Admin Portal Custom Domain URL",
            )

        # Store references for other stacks
        self.admin_cluster = admin_cluster
        self.admin_app_repository = admin_app_repository
        self.user_pool = user_pool
        self.user_pool_client = user_pool_client
        self.fargate_service = fargate_service
        self.cloudfront_distribution = cloudfront_distribution
