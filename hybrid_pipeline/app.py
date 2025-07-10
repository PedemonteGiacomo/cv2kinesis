#!/usr/bin/env python3
import aws_cdk as cdk
import os
from hybrid_pipeline_stack import HybridPipelineStack

app = cdk.App()
stage = app.node.try_get_context("stage") or "dev"
HybridPipelineStack(
    app,
    f"HybridPipelineStack-{stage}",
    stage=stage,
    env=cdk.Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"), region="eu-central-1"
    ),
)
app.synth()
