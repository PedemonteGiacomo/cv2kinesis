#!/usr/bin/env python3
"""
Deploy e test dell'infrastruttura cloud completa:
Producer → Kinesis → ECS Fargate → S3 + SQS → Consumer

Architettura finale:
📱 Webcam → 🎥 Kinesis → 🐳 ECS → 📦 S3 → 📨 SQS → 👁️ Consumer
"""
import subprocess
import time
import json
import sys
import os

def build_and_push_image():
    """Build e push dell'immagine Docker su ECR"""
    print("🔨 Building Docker image...")
    
    # Build
    build_cmd = ["docker", "build", "-t", "cv2kinesis:latest", "."]
    result = subprocess.run(build_cmd, cwd="stream_service")
    if result.returncode != 0:
        print("❌ Docker build failed")
        return False
    
    print("✅ Docker image built successfully")
    
    # ECR login, tag e push
    print("🚀 Pushing to ECR...")
    commands = [
        "aws ecr get-login-password --region eu-central-1 | docker login --username AWS --password-stdin 544547773663.dkr.ecr.eu-central-1.amazonaws.com",
        "docker tag cv2kinesis:latest 544547773663.dkr.ecr.eu-central-1.amazonaws.com/cv2kinesis:latest",
        "docker push 544547773663.dkr.ecr.eu-central-1.amazonaws.com/cv2kinesis:latest"
    ]
    
    for cmd in commands:
        result = subprocess.run(cmd, shell=True, cwd="stream_service")
        if result.returncode != 0:
            print(f"❌ Command failed: {cmd}")
            return False
    
    print("✅ Image pushed to ECR successfully")
    return True

def deploy_stack():
    """Deploy CDK stack"""
    print("☁️ Deploying CDK stack...")
    
    result = subprocess.run(["cdk", "deploy", "VideoPipelineStack", "--require-approval", "never"], 
                          cwd="cdk")
    if result.returncode != 0:
        print("❌ CDK deploy failed")
        return False, {}
    
    # Get stack outputs
    print("📋 Getting stack outputs...")
    try:
        result = subprocess.run(
            ["aws", "cloudformation", "describe-stacks", "--stack-name", "VideoPipelineStack"],
            capture_output=True, text=True
        )
        
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
    print("🎥 Starting producer (webcam → Kinesis)...")
    print("📹 Make sure your webcam is connected!")
    
    try:
        subprocess.run([sys.executable, "producer.py"], cwd="simple")
    except KeyboardInterrupt:
        print("\n⏹️ Producer stopped")

def run_consumer(sqs_queue_url):
    """Avvia consumer per ricevere messaggi da SQS"""
    print(f"📨 Starting SQS consumer...")
    print(f"📡 Queue: {sqs_queue_url}")
    
    try:
        subprocess.run([sys.executable, "sqs_consumer.py", sqs_queue_url])
    except KeyboardInterrupt:
        print("\n⏹️ Consumer stopped")

def wait_for_service_healthy(load_balancer_url):
    """Aspetta che il servizio ECS diventi healthy"""
    print("⏳ Waiting for ECS service to become healthy...")
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
    print("=== DEPLOY E TEST INFRASTRUTTURA CLOUD COMPLETA ===")
    print("🏗️ Architettura: Webcam → Kinesis → ECS → S3 → SQS → Consumer")
    print()
    
    choice = input("""Scegli operazione:
1. Build e deploy completo
2. Solo build e push immagine Docker
3. Solo deploy CDK stack  
4. Solo test producer
5. Solo test consumer (richiede SQS URL)
6. Test completo (producer + consumer)
> """)
    
    if choice == "1":
        # Build e deploy completo
        if not build_and_push_image():
            return
        
        success, outputs = deploy_stack()
        if not success:
            return
        
        if outputs:
            print("\n🎯 INFRASTRUTTURA PRONTA!")
            print(f"📺 Video stream: {outputs.get('LoadBalancerURL', 'N/A')}")
            print(f"📦 S3 bucket: {outputs.get('S3BucketName', 'N/A')}")
            print(f"📨 SQS queue: {outputs.get('SQSQueueURL', 'N/A')}")
            
            # Aspetta che il servizio sia healthy
            if 'LoadBalancerURL' in outputs:
                wait_for_service_healthy(outputs['LoadBalancerURL'])
            
            print("\n🚀 Ready to test! Run options 4 or 6 to test the pipeline.")
        
    elif choice == "2":
        build_and_push_image()
        
    elif choice == "3":
        deploy_stack()
        
    elif choice == "4":
        run_producer()
        
    elif choice == "5":
        sqs_url = input("Enter SQS Queue URL: ")
        if sqs_url:
            run_consumer(sqs_url)
        else:
            print("❌ SQS URL required")
            
    elif choice == "6":
        # Test completo
        sqs_url = input("Enter SQS Queue URL (from stack outputs): ")
        if not sqs_url:
            print("❌ SQS URL required")
            return
        
        print("\n🚀 Starting complete test...")
        print("🎥 Producer will start first, then consumer")
        print("📹 Make sure your webcam is working!")
        
        import threading
        
        # Start consumer in background
        consumer_thread = threading.Thread(target=run_consumer, args=(sqs_url,), daemon=True)
        consumer_thread.start()
        
        time.sleep(3)  # Give consumer time to start
        
        # Start producer (this will block until stopped)
        try:
            run_producer()
        except KeyboardInterrupt:
            print("\n⏹️ Test completed")
    else:
        print("❌ Invalid choice")

if __name__ == "__main__":
    main()
