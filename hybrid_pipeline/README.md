# Hybrid Image & Video Pipeline

This folder contains a minimal AWS CDK stack that combines the existing video-processing path (YOLOv8 on ECS) with a simple image-processing workflow based on S3 and Lambda.

The stack creates:

- A Kinesis stream, ECS Fargate service and SQS queue for real-time video frame processing.
- Two S3 buckets and a Lambda function that converts uploaded images to grayscale.
- Convenient CloudFormation outputs so other teams or a frontend can easily integrate with the resources.

## Prerequisites

- An AWS account with credentials configured (`aws configure`).
- Node.js with the AWS CDK CLI installed:
  ```bash
  npm install -g aws-cdk
  ```
- Python 3.9 or later for the Lambda dependencies.

## Deployment

1. (Optional) install the Lambda requirements in a virtual environment if you want to test the handler locally:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r lambda/grayscale/requirements.txt
   ```

2. Deploy the stack (defaults to the `dev` stage):
   ```bash
   cdk deploy
   ```
   For a production deployment run:
   ```bash
   cdk deploy -c stage=prod
   ```

The command prints outputs such as the load balancer URL, Kinesis stream name and bucket names. These values are required by the frontend or additional services.

To remove the stack use the matching destroy command:
```bash
cdk destroy                # dev stage
cdk destroy -c stage=prod  # prod stage
```

## Testing

From the repository root you can run the project tests:
```bash
python -m pytest
```
The tests rely on optional packages like `requests` and `cv2`. If they are not installed or Docker is unavailable, test collection will fail.

## Workflow Summary

1. Send video frames to the listed Kinesis stream. YOLOv8 on ECS processes each frame and saves the result in the processed frames bucket. Detection results are published to the SQS queue.
2. Upload still images to the `raw-images` bucket (or mount it via AWS Storage Gateway). The Lambda triggered by S3 events saves a grayscale version in the `processed-images` bucket under `processed/`.

Refer to `hybrid_pipeline_stack.py` for full implementation details.
