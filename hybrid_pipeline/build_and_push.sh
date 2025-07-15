#!/bin/bash

# Build and push script for grayscale service
set -e

REGION="eu-central-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPOSITORY="hybrid-pipeline-grayscale"
IMAGE_TAG="latest"

echo "Building and pushing grayscale service to ECR..."
echo "Region: $REGION"
echo "Account: $ACCOUNT_ID"
echo "Repository: $ECR_REPOSITORY"

# Get ECR login token
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com

# Build the image
echo "Building Docker image..."
cd services/grayscale_service
docker build -f Dockerfile_aws -t $ECR_REPOSITORY:$IMAGE_TAG .

# Tag for ECR
docker tag $ECR_REPOSITORY:$IMAGE_TAG $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_REPOSITORY:$IMAGE_TAG

# Push to ECR
echo "Pushing to ECR..."
docker push $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_REPOSITORY:$IMAGE_TAG

echo "Successfully pushed image: $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_REPOSITORY:$IMAGE_TAG"
