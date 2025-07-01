# CDK Stack for Real-Time YOLO Demo

This CDK project creates the AWS infrastructure required to run the real-time video processing demo.

Resources provisioned:

- **Amazon Kinesis Data Stream** used to transport video frames.
- **Amazon ECS Fargate Service** running the YOLO container.
- **Application Load Balancer** exposing the processed MJPEG stream.

## Usage

1. Install dependencies in a Python virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Deploy the stack:
   ```bash
   cdk deploy
   ```
3. After deployment finishes, note the stream name and load balancer URL output by CDK.

Destroy the stack with:
```bash
cdk destroy
```
