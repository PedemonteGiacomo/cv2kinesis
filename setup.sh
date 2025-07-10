#!/usr/bin/env bash
set -euo pipefail

# Create Python virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip

# Install dependencies for all components
pip install -r video-processing/requirements.txt
pip install -r video-processing/producer_and_consumer_examples/requirements.txt
pip install -r video-processing/cdk/requirements.txt
pip install -r image-processing/frontend/requirements.txt
pip install -r image-processing/grayscale_service/requirements.txt

# Install AWS CDK CLI
npm install -g aws-cdk

echo "Environment ready. Activate with: source .venv/bin/activate"
