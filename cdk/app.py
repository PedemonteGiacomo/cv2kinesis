#!/usr/bin/env python3
import aws_cdk as cdk

from pipeline_stack import VideoPipelineStack

app = cdk.App()
VideoPipelineStack(
    app, 
    "VideoPipelineStack",
    env=cdk.Environment(
        account="544547773663",
        region="eu-central-1"
    )
)
app.synth()
