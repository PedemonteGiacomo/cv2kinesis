#!/usr/bin/env python3
import sys
import argparse
from aws_cdk import App, Fn, Stack
from aws_pdk.cdk_graph import CdkGraph, FilterPreset
from aws_pdk.cdk_graph_plugin_diagram import CdkGraphDiagramPlugin
from stacks.pacs_api_stack import PacsApiStack
from stacks.image_pipeline import ImagePipeline
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
        help="Virgola-separato: Imports,PacsApi,ImgPipeline. Default: tutte",
        default="Imports,PacsApi,ImgPipeline"
    )
    args = parser.parse_args()
    stacks_to_include = set(s.strip() for s in args.stacks.split(","))

    app = App()
    stack_objs = {}

    if "Imports" in stacks_to_include:
        imports = Imports(app, "Imports")
        stack_objs["Imports"] = imports
    else:
        imports = None

    if "PacsApi" in stacks_to_include:
        # Se Imports non incluso, crea bucket fittizio
        bucket = imports.pacs_bucket if imports else s3.Bucket.from_bucket_name(app, "PacsBucket", "pacs-dicom-dev-544547773663-us-east-1")
        pacs_api = PacsApiStack(app, "PacsApi", bucket=bucket)
        stack_objs["PacsApi"] = pacs_api
    else:
        pacs_api = None

    if "ImgPipeline" in stacks_to_include:
        pacs_api_url = Fn.import_value("PacsApiLoadBalancerDNS")
        img_pipe = ImagePipeline(app, "ImgPipeline", pacs_api_url=pacs_api_url)
        stack_objs["ImgPipeline"] = img_pipe
    else:
        img_pipe = None

    # Inietta variabili ambiente se tutte le stack sono presenti
    if img_pipe and pacs_api:
        from aws_cdk.aws_ecs import ContainerDefinition
        for node in img_pipe.node.find_all():
            if isinstance(node, ContainerDefinition):
                node.add_environment("PACS_API_BASE", f"http://{pacs_api.api_url}")
                node.add_environment("PACS_API_KEY", "")


    # Migliora la leggibilità del diagramma con layout left-right e best practice
    # Puoi anche personalizzare il filtro o aggiungere tag/commenti alle risorse
    graph = CdkGraph(
        app,
        plugins=[
            CdkGraphDiagramPlugin(
                defaults={
                    "filter_plan": {
                        "preset": FilterPreset.NON_EXTRANEOUS,  # Puoi provare anche NON_EXTRANEOUS o personalizzare
                    },
                    "theme": "dark"
                },
                diagrams=[
                    {
                        "name": "compact-diagram",
                        "title": "Compact Architecture (Left-Right)",
                        "rankdir": "LR"
                    }
                ]
            )
        ],
    )

    app.synth()
    graph.report()

if __name__ == "__main__":
    main()
