# Real-time Video Processing Demo

This repository is organized for collaborative development of a demo that streams camera frames to AWS Kinesis, processes them with YOLO in Fargate and sends annotated results back to the browser.

The original proof of concept has been moved to the **old/** directory. New work should happen in the folders below:

- **infra/** – CDK project describing the AWS stack (Kinesis, Fargate, S3, Lambda, WebSocket API).
- **processing/** – code and Dockerfile for the YOLO container running on Fargate.
- **frontend/** – web application that captures video and pushes frames to Kinesis, then receives notifications and displays processed frames.
- **docs/** – architecture notes and any additional documentation.

See `old/` for the previous scripts and examples.
