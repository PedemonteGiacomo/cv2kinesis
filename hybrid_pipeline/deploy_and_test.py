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
    # Usa Dockerfile_aws per grayscale_service
    if "grayscale_service" in service_dir:
        build_cmd = ["docker", "build", "-t", image_name, "-f", "Dockerfile_aws", "."]
    else:
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
    print("✅ Stack deployed! Gli outputs sono già visibili sopra.")
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
    # Colori ANSI (se supportati)
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    SEP = f"{CYAN}{'═'*60}{RESET}"
    print(SEP)
    print(f"{BOLD}{YELLOW}🌟 MENU OPERAZIONI PIPELINE 🌟{RESET}")
    print(SEP)
    print(f"  {GREEN}1️⃣{RESET}  Build & Deploy completo (Docker + CDK)")
    print(f"  {GREEN}2️⃣{RESET}  Solo build & push immagini Docker")
    print(f"  {GREEN}3️⃣{RESET}  Solo deploy CDK stack")
    print(f"  {GREEN}4️⃣{RESET}  Test VIDEO PIPELINE")
    print(f"      {CYAN}4a.{RESET} 🎥 Live: Producer webcam → Kinesis + stream web")
    print(f"      {CYAN}4b.{RESET} 📦 Batch: Carica video su S3, verifica output su S3/SQS")
    print(f"  {GREEN}5️⃣{RESET}  Test IMAGE PIPELINE (carica immagine, verifica output)")
    print(SEP)
    print(f"{BOLD}Istruzioni:{RESET} Scegli l'opzione desiderata e premi Invio. Puoi interrompere in qualsiasi momento con Ctrl+C.")
    choice = input(f"\n👉 Scegli operazione [{GREEN}1,2,3,4a,4b,5{RESET}]: ")

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
            print("\n🚀 Pronto per il test! Usa le opzioni 4a, 4b o 5 per testare la pipeline.")
    elif choice == "2":
        build_and_push_image(os.path.join("services", "stream_service"), "cv2kinesis:latest", "hybrid-pipeline-stream")
        build_and_push_image(os.path.join("services", "grayscale_service"), "grayscale:latest", "hybrid-pipeline-grayscale")
    elif choice == "3":
        deploy_stack()
    elif choice == "4a":
        print_step("TEST LIVE VIDEO PIPELINE")
        print("Questo test avvia il producer (webcam → Kinesis) e apre il browser sul servizio stream per vedere i frame processati in tempo reale.")
        subprocess.run([sys.executable, "test_video_live_pipeline.py"])
    elif choice == "4b":
        print_step("TEST VIDEO PIPELINE DA FILE SU S3 (batch)")
        print("Questo test carica un video su S3, attende l'elaborazione e verifica l'output frame su S3 e il messaggio su SQS.")
        subprocess.run([sys.executable, "test_video_pipeline.py"])
    elif choice == "5":
        print_step("TEST AUTOMATICO IMAGE PIPELINE")
        print("Questo test carica un'immagine su S3, attende l'elaborazione e verifica l'output su S3/SQS.")
        subprocess.run([sys.executable, "test_image_pipeline.py"])
    else:
        print("❌ Scelta non valida")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Esecuzione terminata dall'utente. Tutto ok!")
