# infra/bin/app.py
from aws_cdk import (
    App,
    Stack,
    aws_s3 as s3,
    Fn,
)

from stacks.pacs_api_stack import PacsApiStack
from stacks.image_pipeline import ImagePipeline
from constructs import Construct
import os

app = App()
region = os.environ.get("AWS_REGION", "us-east-1")
env = {"region": region}

# ───────────────────────── Imports stack ────────────────────────────
class Imports(Stack):
    def __init__(self, scope: Construct, _id: str, **kw):
        super().__init__(scope, _id, **kw)

        # bucket PACS già presente in S3
        self.pacs_bucket = s3.Bucket.from_bucket_name(
            self,
            "PacsBucket",
            f"pacs-dicom-dev-544547773663-{region}",
        )

imports = Imports(app, "Imports", env=env)            # 👈 1° stack

# ──────────────────────── PACS‑API micro‑service ────────────────────
pacs_api = PacsApiStack(                      # 👈 2° stack
    app,
    "PacsApi",
    bucket=imports.pacs_bucket,
    env=env
)

# ───────────────────── Image‑processing pipeline ────────────────────
pacs_api_url = Fn.import_value("PacsApiLoadBalancerDNS")
img_pipe = ImagePipeline(app, "ImgPipeline", pacs_api_url=pacs_api_url, env=env)  # 👈 3° stack

# Inietta la base‑URL dell’API in tutti i container worker
from aws_cdk.aws_ecs import ContainerDefinition
for node in img_pipe.node.find_all():
    if isinstance(node, ContainerDefinition):
        node.add_environment("PACS_API_BASE", f"http://{pacs_api.api_url}")
        node.add_environment("PACS_API_KEY", "")   # se usi API‑Key, mettila qui

app.synth()
