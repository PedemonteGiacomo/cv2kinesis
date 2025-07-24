# infra/bin/app.py
from aws_cdk import (
    App,
    Stack,
    aws_s3 as s3,
    aws_ecs as ecs,
)
from constructs import Construct

from stacks.pacs_api_stack import PacsApiStack
from stacks.image_pipeline import ImagePipeline


class RootStack(Stack):
    def __init__(self, scope: Construct, _id: str, **kwargs):
        super().__init__(scope, _id, **kwargs)

        # bucket PACS già esistente
        pacs_bucket = s3.Bucket.from_bucket_name(
            self,             # <‑‑ adesso siamo in uno Stack
            "PacsBucket",
            "pacs-dicom-dev-544547773663-us-east-1",
        )

        # micro‑servizio PACS‑API
        pacs_api = PacsApiStack(
            self,
            "PacsApi",
            bucket=pacs_bucket,
        )

        # image‑processing pipeline
        img_pipe = ImagePipeline(self, "ImgPipeline")

        # propaga l’URL dell’API ai container worker
        for node in img_pipe.node.find_all():
            if isinstance(node, ecs.ContainerDefinition):
                node.add_environment("PACS_API_BASE", f"http://{pacs_api.api_url}")
                node.add_environment("PACS_API_KEY", "")   # se usi API‑Key mettila qui


app = App()

# RootStack è l’unico stack che verrà effettivamente deployato
RootStack(app, "ImageProcessingRoot", env={"region": "us-east-1"})

app.synth()
