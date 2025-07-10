# Agent Instructions for cv2kinesis

## Repository Overview
This repository contains two main subprojects:

- **image-processing** – a local event-driven prototype using RabbitMQ and MinIO.
- **video-processing** – an AWS CDK based solution for streaming video frames to a YOLOv8 detector running on ECS. It includes infrastructure code and sample producers/consumers.

Both projects are written primarily in Python.

## Coding Guidelines
- **Style**: Format Python code with [black](https://black.readthedocs.io/en/stable/) using the default line length. Use 4 spaces for indentation.
- **Imports**: Group built-in, third‑party and local imports separately.
- **Docstrings**: Public functions and modules should include docstrings explaining their purpose.
- **Shell scripts**: start with `#!/usr/bin/env bash` and include `set -euo pipefail`.
- **Commit messages**: write a short imperative sentence in present tense.

## Testing
- Before committing, run `python -m pytest` from the repository root. The tests rely on optional heavy dependencies (Docker, OpenCV, ultralytics). If they fail due to missing packages or services, include the provided disclaimer in the PR.

## Environment Setup
A helper script `setup.sh` in the repository root installs the required tools. Run it once after cloning to create a virtual environment, install Python requirements for all components and install the AWS CDK CLI.

```bash
./setup.sh
```

This prepares the environment for CDK commands such as `cdk synth` or `cdk deploy`.

## Project Goal
The main focus of this repository is building a complete Python CDK stack for a unified, hybrid infrastructure handling both images and videos in AWS region `eu-central-1`. Separate configurations for **test/dev** and **prod** should be maintained, and useful outputs should be provided for frontend integration.
