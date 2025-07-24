#!/usr/bin/env python3
import aws_cdk as cdk
from image_pipeline import ImagePipeline

app = cdk.App()
ImagePipeline(
    app,
    "ImagePipeline",
    env=cdk.Environment(account="544547773663", region="eu-central-1"),
)
app.synth()
