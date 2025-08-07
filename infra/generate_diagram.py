#!/usr/bin/env python3
import sys
import argparse
from aws_cdk import App, Fn, Stack
from aws_pdk.cdk_graph import CdkGraph, FilterPreset
from aws_pdk.cdk_graph_plugin_diagram import CdkGraphDiagramPlugin
from stacks.pacs_api_stack import PacsApiStack
from stacks.image_pipeline import ImagePipeline
from stacks.admin_stack import AdminStack
from aws_cdk import aws_s3 as s3
from constructs import Construct
import os


# Stack di import come in app.py
class Imports(Stack):
    def __init__(self, scope: Construct, _id: str, **kw):
        super().__init__(scope, _id, **kw)
        self.pacs_bucket = s3.Bucket.from_bucket_name(
            self,
            "PacsBucket",
            "pacs-dicom-dev-544547773663-us-east-1",
        )

def main():
    parser = argparse.ArgumentParser(description="Genera diagramma CDK compatto.")
    parser.add_argument(
        "--stacks",
        type=str,
        help="Virgola-separato: Imports,PacsApi,ImgPipeline,AdminStack. Default: tutte",
        default="Imports,PacsApi,ImgPipeline,AdminStack"
    )
    args = parser.parse_args()
    stacks_to_include = set(s.strip() for s in args.stacks.split(","))

    app = App()
    region = os.environ.get("AWS_REGION", "us-east-1")
    env = {"region": region}
    stack_objs = {}

    if "Imports" in stacks_to_include:
        imports = Imports(app, "Imports", env=env)
        stack_objs["Imports"] = imports
    else:
        imports = None

    if "PacsApi" in stacks_to_include:
        # Se Imports non incluso, crea bucket fittizio
        bucket = imports.pacs_bucket if imports else s3.Bucket.from_bucket_name(app, "PacsBucket", "pacs-dicom-dev-544547773663-us-east-1")
        pacs_api = PacsApiStack(app, "PacsApi", bucket=bucket, env=env)
        stack_objs["PacsApi"] = pacs_api
    else:
        pacs_api = None

    if "ImgPipeline" in stacks_to_include:
        pacs_api_url = Fn.import_value("PacsApiLoadBalancerDNS")
        img_pipe = ImagePipeline(app, "ImgPipeline", pacs_api_url=pacs_api_url, env=env)
        stack_objs["ImgPipeline"] = img_pipe
    else:
        img_pipe = None

    if "AdminStack" in stacks_to_include:
        # Optional: Custom domain configuration (same as app.py)
        domain_name = os.environ.get("ADMIN_DOMAIN_NAME")  # e.g., "admin.yourdomain.com"
        certificate_arn = os.environ.get("ADMIN_CERTIFICATE_ARN")  # ACM certificate ARN
        
        # AdminStack requires both VPC from ImgPipeline and API Gateway URL
        if img_pipe:
            admin_stack = AdminStack(
                app,
                "AdminStack",
                vpc=img_pipe.vpc,
                api_gateway_url=Fn.import_value("ImgPipelineApiGatewayUrl"),
                domain_name=domain_name,
                certificate_arn=certificate_arn,
                env=env,
            )
            # Add dependency to ensure proper deployment order
            admin_stack.add_dependency(img_pipe)
            stack_objs["AdminStack"] = admin_stack
        else:
            print("Warning: AdminStack requires ImgPipeline to be included for VPC dependency")
            admin_stack = None
    else:
        admin_stack = None

    # Inietta variabili ambiente se tutte le stack sono presenti
    if img_pipe and pacs_api:
        from aws_cdk.aws_ecs import ContainerDefinition
        for node in img_pipe.node.find_all():
            if isinstance(node, ContainerDefinition):
                node.add_environment("PACS_API_BASE", f"http://{pacs_api.api_url}")
                node.add_environment("PACS_API_KEY", "")


    # Improve diagram readability with left-right layout and best practices
    # You can also customize the filter or add tags/comments to resources
    graph = CdkGraph(
        app,
        plugins=[
            CdkGraphDiagramPlugin(
                defaults={
                    "filter_plan": {
                        "preset": FilterPreset.COMPACT,  # You can also try NON_EXTRANEOUS or customize
                    },
                    "theme": "dark"
                },
                diagrams=[
                    {
                        "name": "full-architecture-diagram",
                        "title": "Complete MIP Architecture (Left-Right)",
                        "rankdir": "LR"
                    },
                    {
                        "name": "compact-diagram",
                        "title": "Compact View (Top-Down)",
                        "rankdir": "TB"
                    }
                ]
            )
        ],
    )

    app.synth()
    graph.report()
    
    print(f"Generated diagrams for stacks: {', '.join(stacks_to_include)}")
    print("Available stacks: Imports, PacsApi, ImgPipeline, AdminStack")

if __name__ == "__main__":
    main()
