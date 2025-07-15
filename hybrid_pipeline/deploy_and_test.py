#!/usr/bin/env python3
"""
Script di deploy e test per la pipeline cloud ibrida (image & video processing)
Compatibile con PowerShell/Windows. Output chiaro, emoji, istruzioni step-by-step.

Architettura:
📱 Webcam → 🎥 Kinesis → 🐳 ECS → 📦 S3 → 📨 SQS → 👁️ Consumer
"""
import subprocess
import time
import json
import sys
import os

def print_step(msg):
    print(f"\n{'='*60}\n{msg}\n{'='*60}")

def build_and_push_image(service_dir, image_name, ecr_repo):
    """Build e push dell'immagine Docker su ECR per un servizio"""
    print_step(f"🔨 BUILD DOCKER IMAGE ({service_dir})")
    build_cmd = ["docker", "build", "-t", image_name, "."]
    result = subprocess.run(build_cmd, cwd=service_dir)
    if result.returncode != 0:
        print(f"❌ Docker build failed for {service_dir}")
        return False
    print(f"✅ Docker image built successfully for {service_dir}")

    print_step(f"🚀 PUSH IMAGE TO ECR ({ecr_repo})")
    login_cmd = f"aws ecr get-login-password --region eu-central-1 | docker login --username AWS --password-stdin 544547773663.dkr.ecr.eu-central-1.amazonaws.com"
    tag_cmd = f"docker tag {image_name} 544547773663.dkr.ecr.eu-central-1.amazonaws.com/{ecr_repo}:latest"
    push_cmd = f"docker push 544547773663.dkr.ecr.eu-central-1.amazonaws.com/{ecr_repo}:latest"
    for cmd in [login_cmd, tag_cmd, push_cmd]:
        result = subprocess.run(cmd, shell=True, cwd=service_dir)
        if result.returncode != 0:
            print(f"❌ Command failed: {cmd}")
            return False
    print(f"✅ Image pushed to ECR successfully for {ecr_repo}")
    return True

def deploy_stack():
    """Deploy CDK stack e mostra gli output principali"""
    print_step("☁️ DEPLOY CDK STACK")
    result = subprocess.run("cdk deploy --require-approval never", shell=True, cwd="cdk")
    if result.returncode != 0:
        print("❌ CDK deploy failed")
        return False, {}

    print_step("📋 GET STACK OUTPUTS")
    try:
        result = subprocess.run([
            "aws", "cloudformation", "describe-stacks", "--stack-name", "HybridPipelineStack"
        ], capture_output=True, text=True)
        if result.returncode == 0:
            stack_data = json.loads(result.stdout)
            outputs = {}
            for output in stack_data['Stacks'][0].get('Outputs', []):
                outputs[output['OutputKey']] = output['OutputValue']
            print("✅ Stack deployed successfully!")
            print("\n📋 STACK OUTPUTS:")
            for key, value in outputs.items():
                print(f"   {key}: {value}")
            return True, outputs
        else:
            print("⚠️ Could not get stack outputs")
            return True, {}
    except Exception as e:
        print(f"⚠️ Error getting outputs: {e}")
        return True, {}

def run_producer():
    """Avvia producer per inviare video a Kinesis"""
    print_step("🎥 STARTING PRODUCER (Webcam → Kinesis)")
    print("📹 Assicurati che la webcam sia collegata!")
    try:
        subprocess.run([sys.executable, "producer.py"], cwd=os.path.join("..", "video-processing", "producer_and_consumer_examples"))
    except KeyboardInterrupt:
        print("\n⏹️ Producer stopped")

def run_consumer(sqs_queue_url):
    """Avvia consumer per ricevere messaggi da SQS"""
    print_step("📨 STARTING SQS CONSUMER")
    print(f"📡 Queue: {sqs_queue_url}")
    try:
        subprocess.run([sys.executable, "sqs_consumer.py", sqs_queue_url], cwd=os.path.join("..", "video-processing", "producer_and_consumer_examples"))
    except KeyboardInterrupt:
        print("\n⏹️ Consumer stopped")

def wait_for_service_healthy(load_balancer_url):
    """Aspetta che il servizio ECS diventi healthy"""
    print_step("⏳ WAITING FOR ECS SERVICE TO BECOME HEALTHY")
    print(f"🌐 Load Balancer: {load_balancer_url}")
    max_attempts = 30
    for i in range(max_attempts):
        try:
            import requests
            response = requests.get(f"{load_balancer_url}/health", timeout=10)
            if response.status_code == 200:
                print("✅ Service is healthy!")
                return True
        except:
            pass
        print(f"🔄 Attempt {i+1}/{max_attempts} - Service not ready yet...")
        time.sleep(30)
    print("⚠️ Service may not be fully healthy, but continuing...")
    return False

def main():
    print_step("DEPLOY & TEST PIPELINE CLOUD IBRIDA")
    print("🏗️ Architettura: Webcam → Kinesis → ECS → S3 → SQS → Consumer\n")
    print("Operazioni disponibili:")
    print("  1. Build e deploy completo (Docker + CDK)")
    print("  2. Solo build e push immagini Docker")
    print("  3. Solo deploy CDK stack")
    print("  4. Test live VIDEO PIPELINE (producer webcam → Kinesis + stream web)")
    print("  5. Test automatico IMAGE PIPELINE (carica immagine, verifica output)")
    choice = input("\nScegli operazione [1-5]: ")

    if choice == "1":
        # Build e push di entrambe le immagini
        ok1 = build_and_push_image(os.path.join("services", "stream_service"), "cv2kinesis:latest", "hybrid-pipeline-stream")
        ok2 = build_and_push_image(os.path.join("services", "grayscale_service"), "grayscale:latest", "hybrid-pipeline-grayscale")
        if not (ok1 and ok2):
            return
        success, outputs = deploy_stack()
        if not success:
            return
        if outputs:
            print("\n🎯 INFRASTRUTTURA PRONTA!")
            print(f"📺 Video stream: {outputs.get('VideoStreamServiceURL', 'N/A')}")
            print(f"📦 S3 bucket immagini: {outputs.get('ImageInputBucketName', 'N/A')}")
            print(f"📦 S3 bucket video: {outputs.get('VideoInputBucketName', 'N/A')}")
            print(f"📨 SQS queue: {outputs.get('VideoProcessingQueueURL', 'N/A')}")
            if 'VideoStreamServiceURL' in outputs:
                wait_for_service_healthy(outputs['VideoStreamServiceURL'])
            print("\n🚀 Pronto per il test! Usa le opzioni 4 o 5 per testare la pipeline.")
    elif choice == "2":
        build_and_push_image(os.path.join("services", "stream_service"), "cv2kinesis:latest", "hybrid-pipeline-stream")
        build_and_push_image(os.path.join("services", "grayscale_service"), "grayscale:latest", "hybrid-pipeline-grayscale")
    elif choice == "3":
        deploy_stack()
    elif choice == "4":
        print_step("TEST LIVE VIDEO PIPELINE")
        print("Questo test avvia il producer (webcam → Kinesis) e apre il browser sul servizio stream per vedere i frame processati in tempo reale.")
        subprocess.run([sys.executable, "test_video_live_pipeline.py"])
    elif choice == "5":
        print_step("TEST AUTOMATICO IMAGE PIPELINE")
        print("Questo test carica un'immagine su S3, attende l'elaborazione e verifica l'output su S3/SQS.")
        subprocess.run([sys.executable, "test_image_pipeline.py"])
    else:
        print("❌ Scelta non valida")

if __name__ == "__main__":
    main()
