from aws_cdk import App, aws_s3 as s3, aws_ecs as ecs
from stacks.pacs_api_stack import PacsApiStack
from stacks.image_pipeline import ImagePipeline

app = App()

# 1. bucket DICOM esistente
pacs_bucket = s3.Bucket.from_bucket_name(
    app, "PacsBucket", "pacs-dicom-dev-544547773663-us-east-1"
)

# 2. micro‑servizio PACS
pacs = PacsApiStack(app, "PacsApi", bucket=pacs_bucket, env={"region": "eu-central-1"})

# 3. pipeline di processing
pipe = ImagePipeline(app, "ImgPipeline", env={"region": "eu-central-1"})

# 4. inietta la variabile d’ambiente nei task ECS
for node in pipe.node.find_all():
    if isinstance(node, ecs.ContainerDefinition):
        node.add_environment("PACS_API_BASE", f"http://{pacs.api_url}")
        # se non usi API‑Key lascia stringa vuota
        node.add_environment("PACS_API_KEY", "")

app.synth()
