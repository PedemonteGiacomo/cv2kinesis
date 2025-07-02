#!/usr/bin/env python3
import aws_cdk as cdk

from pipeline_stack import VideoPipelineStack

app = cdk.App()

# Get configuration from context
suffix = app.node.try_get_context("suffix") or ""
stack_name = f"VideoPipelineStack{suffix.replace('-', '').title() if suffix else ''}"

print(f"🚀 Deploying stack: {stack_name}")
if suffix:
    print(f"🏷️ Using environment suffix: {suffix}")

VideoPipelineStack(
    app, 
    stack_name,
    env=cdk.Environment(
        account="544547773663",
        region="eu-central-1"
    )
)

app.synth()
