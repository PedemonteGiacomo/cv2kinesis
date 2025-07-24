from infra.stacks.pacs_api_stack import PacsApiStack
from infra.stacks.image_pipeline import ImagePipeline
from aws_cdk import App, aws_s3 as s3

app = App()

# bucket DICOM già esistente, oppure creato qui
pacs_bucket = s3.Bucket.from_bucket_name(app, "PacsBucket", "pacs-dicom-dev-544547773663-us-east-1")

pacs_stack = PacsApiStack(app, "PacsApi", bucket=pacs_bucket)

img_stack = ImagePipeline(
    app,
    "ImagePipeline",
    env={"region": "us-east-1"},
)
# passa l'URL del PACS‑API come variabile d'ambiente ai container ECS:
for svc in img_stack.node.find_all("Svc"):
    svc.task_definition.default_container.add_environment("PACS_API_BASE", pacs_stack.api_url)

app.synth()
