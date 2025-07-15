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

def build_and_push_image():
    """Build e push dell'immagine Docker su ECR"""
    print_step("🔨 BUILD DOCKER IMAGE")
    build_cmd = ["docker", "build", "-t", "cv2kinesis:latest", "."]
    result = subprocess.run(build_cmd, cwd="stream_service")
    if result.returncode != 0:
        print("❌ Docker build failed")
        return False
    print("✅ Docker image built successfully")

    print_step("🚀 PUSH IMAGE TO ECR")
    ecr_url = "544547773663.dkr.ecr.eu-central-1.amazonaws.com/cv2kinesis:latest"
    login_cmd = "aws ecr get-login-password --region eu-central-1 | docker login --username AWS --password-stdin 544547773663.dkr.ecr.eu-central-1.amazonaws.com"
    tag_cmd = f"docker tag cv2kinesis:latest {ecr_url}"
    push_cmd = f"docker push {ecr_url}"
    for cmd in [login_cmd, tag_cmd, push_cmd]:
        result = subprocess.run(cmd, shell=True, cwd="stream_service")
        if result.returncode != 0:
            print(f"❌ Command failed: {cmd}")
            return False
    print("✅ Image pushed to ECR successfully")
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
        subprocess.run([sys.executable, "producer.py"], cwd="simple")
    except KeyboardInterrupt:
        print("\n⏹️ Producer stopped")

def run_consumer(sqs_queue_url):
    """Avvia consumer per ricevere messaggi da SQS"""
    print_step("📨 STARTING SQS CONSUMER")
    print(f"📡 Queue: {sqs_queue_url}")
    try:
        subprocess.run([sys.executable, "sqs_consumer.py", sqs_queue_url])
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
    print("  1. Build e deploy completo (Docker + CDK + test)")
    print("  2. Solo build e push immagine Docker")
    print("  3. Solo deploy CDK stack")
    print("  4. Solo test producer (webcam → Kinesis)")
    print("  5. Solo test consumer (richiede SQS URL)")
    print("  6. Test completo (producer + consumer)")
    choice = input("\nScegli operazione [1-6]: ")

    if choice == "1":
        if not build_and_push_image():
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
            print("\n🚀 Pronto per il test! Usa le opzioni 4 o 6 per testare la pipeline.")
    elif choice == "2":
        build_and_push_image()
    elif choice == "3":
        deploy_stack()
    elif choice == "4":
        run_producer()
    elif choice == "5":
        sqs_url = input("Inserisci SQS Queue URL: ")
        if sqs_url:
            run_consumer(sqs_url)
        else:
            print("❌ SQS URL richiesto")
    elif choice == "6":
        sqs_url = input("Inserisci SQS Queue URL (dagli outputs dello stack): ")
        if not sqs_url:
            print("❌ SQS URL richiesto")
            return
        print("\n🚀 Avvio test completo: prima consumer, poi producer")
        import threading
        consumer_thread = threading.Thread(target=run_consumer, args=(sqs_url,), daemon=True)
        consumer_thread.start()
        time.sleep(3)
        try:
            run_producer()
        except KeyboardInterrupt:
            print("\n⏹️ Test completato")
    else:
        print("❌ Scelta non valida")

if __name__ == "__main__":
    main()
