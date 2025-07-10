#!/usr/bin/env python3
"""
CDK App con generazione automatica del diagramma dell'architettura
Pipeline: Webcam → Kinesis → ECS Fargate → S3 + SQS → Consumer
"""
import aws_cdk as cdk

# Import CdkGraph and diagram plugin
from aws_pdk.cdk_graph import CdkGraph, FilterPreset
from aws_pdk.cdk_graph_plugin_diagram import CdkGraphDiagramPlugin

from pipeline_stack import VideoPipelineStack

def main():
    app = cdk.App()

    # 1) Instantiate the existing stack
    VideoPipelineStack(
        app,
        "VideoPipelineStack",
        env=cdk.Environment(
            account="544547773663",
            region="eu-central-1"
        ),
    )

    # 2) Instantiate CdkGraph for automatic diagram generation
    graph = CdkGraph(
        app,
        plugins=[
            CdkGraphDiagramPlugin(
                defaults={
                    "filter_plan": {
                        # Using "COMPACT" to show only core resources
                        "preset": FilterPreset.COMPACT,
                    },
                    # Dark theme for the diagram
                    "theme": "dark"
                },
                diagrams=[
                    {
                        "name": "video-pipeline-architecture",
                        "title": "CV2 Kinesis Object Detection Pipeline",
                        # Inherits defaults: COMPACT filter + dark theme
                    },
                    {
                        "name": "detailed-architecture", 
                        "title": "Detailed Infrastructure View",
                        "filter_plan": {
                            # Show more detailed view
                            "preset": FilterPreset.NON_EXTRANEOUS,
                        },
                    }
                ]
            )
        ],
    )

    # 3) CDK synth and diagram generation
    print("🎨 Generating architecture diagrams...")
    app.synth()
    graph.report()
    print("✅ Diagrams generated in cdk.out/")


if __name__ == "__main__":
    main()
