#!/usr/bin/env python3
import aws_cdk as cdk
from pipeline_stack import HybridPipelineStack

app = cdk.App()
HybridPipelineStack(app, "HybridPipelineStack", env={
    "region": "eu-central-1",
    "account": "544547773663"
})
app.synth()
