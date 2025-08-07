# Automatic template generator for new MIP algorithms
param(
    [Parameter(Mandatory=$true)]
    [string] $AlgorithmName,
    
    [Parameter(Mandatory=$true)]
    [ValidateSet("python", "openmp", "hybrid")]
    [string] $Type,
    
    [string] $Description = "New algorithm for MIP",
    [string] $Author = $env:USERNAME,
    [switch] $OpenVSCode
)

$ErrorActionPreference = "Stop"

# Algorithm name validation
if ($AlgorithmName -notmatch '^[a-z][a-z0-9_]*$') {
    Write-Error "Algorithm name must be lowercase, start with letter, contain only letters, numbers, underscores"
}

$rootPath = (Get-Location).Path
$algoPath = Join-Path $rootPath "containers" $AlgorithmName

Write-Host "🎯 Generating new $Type algorithm: $AlgorithmName" -ForegroundColor Green
Write-Host "Path: $algoPath" -ForegroundColor Yellow

# Crea directory
if (Test-Path $algoPath) {
    Write-Error "Algorithm directory already exists: $algoPath"
}

New-Item -ItemType Directory -Path $algoPath -Force | Out-Null

try {
    switch ($Type) {
        "python" {
            Write-Host "`n📝 Creating Python algorithm template..." -ForegroundColor Cyan
            
            # algorithm.py
            $pythonCode = @"
"""
$AlgorithmName - $Description
Author: $Author
Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
"""
from medical_image_processing.processing.base import BaseProcessor
import numpy as np
import logging

logger = logging.getLogger(__name__)

class ${AlgorithmName}Processor(BaseProcessor):
    def __init__(self):
        super().__init__()
        self.name = "$AlgorithmName"
        logger.info(f"Initialized {self.name} processor")
    
    def process_image(self, image_data, metadata=None, **kwargs):
        """
        Process a DICOM image with $AlgorithmName algorithm
        
        Args:
            image_data (np.ndarray): Input image data
            metadata (dict): DICOM metadata (optional)
            **kwargs: Algorithm-specific parameters
            
        Returns:
            np.ndarray: Processed image data
        """
        logger.info(f"Processing image with {self.name}, shape: {image_data.shape}")
        
        # Extract parameters
        threshold = kwargs.get('threshold', 0.5)
        iterations = kwargs.get('iterations', 10)
        
        logger.info(f"Parameters: threshold={threshold}, iterations={iterations}")
        
        # Your algorithm implementation here
        processed_image = self._apply_algorithm(image_data, threshold, iterations)
        
        logger.info(f"Processing completed, output shape: {processed_image.shape}")
        return processed_image
    
    def _apply_algorithm(self, image, threshold, iterations):
        """
        Core algorithm implementation
        
        TODO: Replace this template with your actual algorithm
        """
        # Template: simple threshold + gaussian blur
        import cv2
        
        result = image.copy()
        
        # Apply threshold
        if len(result.shape) == 2:  # Grayscale
            _, result = cv2.threshold(result, threshold * 255, 255, cv2.THRESH_BINARY)
        
        # Apply iterations of processing
        for i in range(iterations):
            result = cv2.GaussianBlur(result, (5, 5), 1.0)
            
        return result
    
    def get_algorithm_info(self):
        """Return algorithm metadata"""
        return {
            "name": self.name,
            "version": "1.0.0",
            "description": "$Description",
            "author": "$Author",
            "parameters": {
                "threshold": {"type": "float", "default": 0.5, "range": [0.0, 1.0]},
                "iterations": {"type": "int", "default": 10, "range": [1, 100]}
            }
        }
"@
            Set-Content -Path (Join-Path $algoPath "algorithm.py") -Value $pythonCode
            
            # Dockerfile
            $dockerfile = @"
# Dockerfile for $AlgorithmName (Python)
# Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')

FROM 544547773663.dkr.ecr.us-east-1.amazonaws.com/mip-base:latest

# Install algorithm-specific dependencies
RUN pip install --no-cache-dir opencv-python-headless scikit-image

# Copy algorithm implementation
COPY algorithm.py /app/src/medical_image_processing/processing/${AlgorithmName}.py

# Use standard worker.sh entrypoint
CMD ["/app/worker.sh"]
"@
            Set-Content -Path (Join-Path $algoPath "Dockerfile") -Value $dockerfile
        }
        
        "openmp" {
            Write-Host "`n⚡ Creating OpenMP algorithm template..." -ForegroundColor Cyan
            
            # Create source directory
            $srcPath = Join-Path $algoPath "src"
            New-Item -ItemType Directory -Path $srcPath -Force | Out-Null
            
            # adapter.py
            $adapterCode = @"
#!/usr/bin/env python3
"""
OpenMP Adapter for $AlgorithmName
Author: $Author
Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
"""
import os, json, time, subprocess, shutil, tempfile
import boto3, requests
from urllib.parse import urlparse
from pathlib import Path

def _recv(queue_url):
    sqs = boto3.client("sqs")
    r = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=1, WaitTimeSeconds=20)
    msgs = r.get("Messages", [])
    if not msgs: return None
    m = msgs[0]
    return m["ReceiptHandle"], json.loads(m["Body"])

def _del(queue_url, rh):
    boto3.client("sqs").delete_message(QueueUrl=queue_url, ReceiptHandle=rh)

def _download(url, dst: Path):
    r = requests.get(url, stream=True, timeout=30)
    r.raise_for_status()
    with open(dst, "wb") as f: 
        shutil.copyfileobj(r.raw, f)

def main():
    # Standard environment variables
    qurl = os.environ["QUEUE_URL"]
    out_bucket = os.environ["OUTPUT_BUCKET"]
    pacs_base = os.environ.get("PACS_API_BASE", "")
    pacs_key = os.environ.get("PACS_API_KEY", "")
    result_q = os.environ["RESULT_QUEUE"]
    algo_id = os.environ["ALGO_ID"]
    
    # Algorithm-specific settings
    binary_path = "/app/bin/$AlgorithmName"
    default_threads = int(os.environ.get("OMP_NUM_THREADS", "2"))
    
    s3 = boto3.client("s3")
    sqs = boto3.client("sqs")

    print(f"[$AlgorithmName] Starting worker")
    print(f"[$AlgorithmName] Binary: {binary_path}")
    print(f"[$AlgorithmName] Threads: {default_threads}")

    if not os.path.exists(binary_path):
        raise FileNotFoundError(f"Binary not found: {binary_path}")

    while True:
        got = _recv(qurl)
        if not got: continue
            
        rh, body = got
        client_id = body["client_id"]
        job_id = body.get("job_id", "unknown")
        pacs = body["pacs"]
        
        # Extract job parameters
        job_threads = body.get("threads", default_threads)
        threshold = body.get("threshold", 0.5)
        iterations = body.get("iterations", 10)
        
        print(f"[$AlgorithmName] Processing job {job_id}")

        try:
            with tempfile.TemporaryDirectory() as tmp:
                # Download input
                if pacs.get("scope", "image") == "image":
                    ep = f"{pacs_base}/studies/{pacs['study_id']}/images/{pacs['series_id']}/{pacs['image_id']}"
                    r = requests.get(ep, headers={"x-api-key": pacs_key}, timeout=30)
                    r.raise_for_status()
                    url = r.json()["url"]
                    src = Path(tmp) / Path(urlparse(url).path).name
                    _download(url, src)
                    print(f"[$AlgorithmName] Downloaded: {src}")
                else:
                    raise ValueError("Only scope=image supported")

                # Process with OpenMP binary
                output_path = Path(tmp) / f"{src.stem}_{algo_id}{src.suffix}"
                
                env = os.environ.copy()
                env['OMP_NUM_THREADS'] = str(job_threads)
                
                cmd = [binary_path, str(src), str(output_path), 
                       "--threshold", str(threshold), "--iterations", str(iterations)]
                
                print(f"[$AlgorithmName] Executing: {' '.join(cmd)}")
                start_time = time.time()
                
                result = subprocess.run(cmd, check=True, capture_output=True, text=True, env=env)
                processing_time = time.time() - start_time
                
                print(f"[$AlgorithmName] Completed in {processing_time:.4f}s")
                print(f"[$AlgorithmName] Output: {result.stdout.strip()}")
                
                if not output_path.exists():
                    raise FileNotFoundError(f"Output not created: {output_path}")

                # Upload to S3
                dest_key = f"{pacs['study_id']}/{pacs['series_id']}/{output_path.name}"
                s3.upload_file(str(output_path), out_bucket, dest_key)
                
                presigned = s3.generate_presigned_url(
                    "get_object", 
                    Params={"Bucket": out_bucket, "Key": dest_key}, 
                    ExpiresIn=86400
                )

                # Send result
                msg = {
                    "job_id": job_id,
                    "algo_id": algo_id,
                    "client_id": client_id,
                    "dicom": {
                        "bucket": out_bucket,
                        "key": dest_key,
                        "url": presigned
                    },
                    "processing_stats": {
                        "threads": job_threads,
                        "threshold": threshold,
                        "iterations": iterations,
                        "processing_time": processing_time
                    }
                }
                
                sqs.send_message(
                    QueueUrl=result_q,
                    MessageBody=json.dumps(msg),
                    MessageGroupId=job_id or "default"
                )
                
                print(f"[$AlgorithmName] Job {job_id} completed")

        except Exception as e:
            print(f"[$AlgorithmName] Error: {e}")
            error_msg = {
                "job_id": job_id,
                "algo_id": algo_id,
                "client_id": client_id,
                "error": str(e)
            }
            try:
                sqs.send_message(
                    QueueUrl=result_q,
                    MessageBody=json.dumps(error_msg),
                    MessageGroupId=job_id or "default"
                )
            except:
                pass
        finally:
            _del(qurl, rh)

if __name__ == "__main__":
    main()
"@
            Set-Content -Path (Join-Path $algoPath "adapter.py") -Value $adapterCode
            
            # main.c
            $mainC = @"
// main.c for $AlgorithmName
// Author: $Author
// Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <omp.h>

void print_usage(const char* prog) {
    printf("Usage: %s <input> <output> [--threshold <val>] [--iterations <num>]\n", prog);
}

int main(int argc, char *argv[]) {
    if (argc < 3) {
        print_usage(argv[0]);
        return 1;
    }
    
    char *input_file = argv[1];
    char *output_file = argv[2];
    double threshold = 0.5;
    int iterations = 10;
    
    // Parse optional arguments
    for (int i = 3; i < argc; i++) {
        if (strcmp(argv[i], "--threshold") == 0 && i + 1 < argc) {
            threshold = atof(argv[++i]);
        } else if (strcmp(argv[i], "--iterations") == 0 && i + 1 < argc) {
            iterations = atoi(argv[++i]);
        }
    }
    
    printf("[$AlgorithmName] Starting processing\n");
    printf("[$AlgorithmName] Input: %s\n", input_file);
    printf("[$AlgorithmName] Output: %s\n", output_file);
    printf("[$AlgorithmName] Threads: %d\n", omp_get_max_threads());
    printf("[$AlgorithmName] Threshold: %.3f\n", threshold);
    printf("[$AlgorithmName] Iterations: %d\n", iterations);
    
    // TODO: Implement your algorithm here
    // This is a template - replace with actual processing
    
    printf("[$AlgorithmName] Processing completed\n");
    return 0;
}
"@
            Set-Content -Path (Join-Path $srcPath "main.c") -Value $mainC
            
            # Makefile
            $makefile = @"
# Makefile for $AlgorithmName
# Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')

CC=gcc
CFLAGS=-O3 -fopenmp -Wall -Wextra
SRC=main.c
BIN=../bin/$AlgorithmName

all: `$(BIN)

`$(BIN): `$(SRC)
	mkdir -p ../bin
	`$(CC) `$(CFLAGS) `$(SRC) -lm -o `$(BIN)

clean:
	rm -f `$(BIN)

.PHONY: all clean
"@
            Set-Content -Path (Join-Path $srcPath "Makefile") -Value $makefile
            
            # Dockerfile
            $dockerfile = @"
# Dockerfile for $AlgorithmName (OpenMP)
# Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')

FROM python:3.11-slim

# Install build tools and OpenMP
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ make libgomp1 curl unzip jq \
    && rm -rf /var/lib/apt/lists/*

# Install AWS CLI v2
RUN curl -sSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip \
    && unzip -q /tmp/awscliv2.zip -d /tmp \
    && /tmp/aws/install \
    && rm -rf /tmp/aws*

WORKDIR /app

# Build algorithm
COPY src/ /app/src/
WORKDIR /app/src
RUN make && ls -la ../bin/

WORKDIR /app

# Copy adapter and install Python dependencies
COPY adapter.py requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && chmod +x adapter.py

# Verify binary
RUN ls -la /app/bin/$AlgorithmName && ldd /app/bin/$AlgorithmName

ENTRYPOINT ["/app/adapter.py"]
"@
            Set-Content -Path (Join-Path $algoPath "Dockerfile") -Value $dockerfile
            
            # requirements.txt
            $requirements = @"
boto3
requests
pydicom
pillow
numpy
"@
            Set-Content -Path (Join-Path $algoPath "requirements.txt") -Value $requirements
        }
        
        "hybrid" {
            Write-Host "`n🔀 Creating hybrid Python+OpenMP template..." -ForegroundColor Cyan
            Write-Host "This template combines Python preprocessing with OpenMP processing" -ForegroundColor Yellow
            
            # TODO: Implement hybrid template if needed
            Write-Host "Hybrid template not implemented yet. Use 'python' or 'openmp' for now." -ForegroundColor Yellow
        }
    }
    
    # Common files for all types
    
    # deploy.ps1
    $deployScript = @"
# Deploy script for $AlgorithmName
# Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
param(
    [string] `$Account = "544547773663",
    [string] `$Region = "us-east-1",
    [string] `$AdminKey = "dev-admin"
)

`$ErrorActionPreference = "Stop"
`$repo = "`$Account.dkr.ecr.`$Region.amazonaws.com/mip-algos"

Write-Host "🚀 Deploying $AlgorithmName algorithm" -ForegroundColor Green

try {
    # Build container
    Write-Host "`n🔨 Building container..." -ForegroundColor Cyan
    docker build -t "mip-$AlgorithmName" .
    docker tag "mip-$AlgorithmName" "`${repo}:$AlgorithmName"
    
    # Push to ECR
    Write-Host "`n📤 Pushing to ECR..." -ForegroundColor Cyan
    aws ecr get-login-password --region `$Region | docker login --username AWS --password-stdin "`$Account.dkr.ecr.`$Region.amazonaws.com"
    docker push "`${repo}:$AlgorithmName"
    
    # Register algorithm
    Write-Host "`n📝 Registering algorithm..." -ForegroundColor Cyan
    `$spec = @{
        algo_id = "$AlgorithmName"
        image_uri = "`${repo}:$AlgorithmName"
        cpu = $(if ($Type -eq "openmp") { 2048 } else { 1024 })
        memory = $(if ($Type -eq "openmp") { 4096 } else { 2048 })
        desired_count = 1
        command = @($(if ($Type -eq "openmp") { '"/app/adapter.py"' } else { '"/app/worker.sh"' }))
        env = @{
            $(if ($Type -eq "openmp") { 'OMP_NUM_THREADS = "4"' } else { 'ALGORITHM_TYPE = "python"' })
        }
    }
    
    `$response = Invoke-RestMethod -Uri "`$env:API_BASE/admin/algorithms" -Method POST -Headers @{
        'Content-Type' = 'application/json'
        'x-admin-key' = `$AdminKey
    } -Body (`$spec | ConvertTo-Json -Depth 10)
    
    Write-Host "`n✅ Algorithm $AlgorithmName deployed successfully!" -ForegroundColor Green
    Write-Host "Image: `${repo}:$AlgorithmName" -ForegroundColor Yellow
    `$response | ConvertTo-Json -Depth 10 | Write-Host
    
} catch {
    Write-Host "`n❌ Deploy failed: `$(`$_.Exception.Message)" -ForegroundColor Red
    exit 1
}
"@
    Set-Content -Path (Join-Path $algoPath "deploy.ps1") -Value $deployScript
    
    # README.md
    $readme = @"
# $AlgorithmName Algorithm

$Description

**Type:** $Type  
**Author:** $Author  
**Generated:** $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')

## Quick Start

``````bash
# Build and test locally
docker build -t $AlgorithmName .

# Deploy to MIP
.\deploy.ps1

# Test algorithm
curl -X POST "`$API_BASE/process/$AlgorithmName" \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "test-$(Get-Date -Format 'yyyyMMdd-HHmmss')",
    "client_id": "test-client",
    "pacs": {
      "study_id": "test-study",
      "series_id": "test-series", 
      "image_id": "test-image",
      "scope": "image"
    }
  }'
``````

## Parameters

$(if ($Type -eq "openmp") {
@"
- **threads**: Number of OpenMP threads (default: 4)
- **threshold**: Processing threshold (default: 0.5)
- **iterations**: Number of iterations (default: 10)
"@
} else {
@"
- **threshold**: Processing threshold (default: 0.5)
- **iterations**: Number of iterations (default: 10)
"@
})

## Development

$(if ($Type -eq "openmp") {
@"
1. Modify `src/main.c` with your algorithm
2. Update `adapter.py` if needed
3. Rebuild: `docker build -t $AlgorithmName .`
4. Deploy: `.\deploy.ps1`
"@
} else {
@"
1. Modify `algorithm.py` with your implementation
2. Update dependencies in Dockerfile if needed
3. Rebuild: `docker build -t $AlgorithmName .`
4. Deploy: `.\deploy.ps1`
"@
})

## Monitoring

- **Logs**: `/ecs/mip-$AlgorithmName`
- **Status**: `curl -H "x-admin-key: dev-admin" "`$API_BASE/admin/algorithms/$AlgorithmName"`
- **Queue**: Check SQS metrics in AWS Console
"@
    Set-Content -Path (Join-Path $algoPath "README.md") -Value $readme
    
    Write-Host "`n✅ Algorithm template created successfully!" -ForegroundColor Green
    Write-Host "`nNext steps:" -ForegroundColor Cyan
    Write-Host "1. cd containers\$AlgorithmName" -ForegroundColor White
    Write-Host "2. Implement your algorithm $(if ($Type -eq "openmp") { "in src/main.c" } else { "in algorithm.py" })" -ForegroundColor White
    Write-Host "3. Test locally: docker build -t $AlgorithmName ." -ForegroundColor White
    Write-Host "4. Deploy: .\deploy.ps1" -ForegroundColor White
    
    if ($OpenVSCode) {
        Write-Host "`n🔍 Opening in VS Code..." -ForegroundColor Cyan
        Set-Location $algoPath
        code .
    }
    
} catch {
    Write-Host "`n❌ Error creating algorithm template: $($_.Exception.Message)" -ForegroundColor Red
    
    # Cleanup on error
    if (Test-Path $algoPath) {
        Remove-Item $algoPath -Recurse -Force
    }
    
    exit 1
}
