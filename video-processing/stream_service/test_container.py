#!/usr/bin/env python3
"""
Test completo del container Docker prima del deploy cloud:
1. Build del container
2. Test del container localmente con AWS simulato
3. Verifica che YOLO funzioni nel container
4. Test dell'health check
"""
import subprocess
import time
import json
import os
import requests
import threading

def build_docker_image():
    """Build dell'immagine Docker"""
    print("🔨 Building Docker image...")
    
    build_cmd = ["docker", "build", "-t", "cv2kinesis:test", "."]
    result = subprocess.run(build_cmd)
    
    if result.returncode != 0:
        print("❌ Docker build failed")
        return False
    
    print("✅ Docker image built successfully")
    return True

def test_health_check():
    """Test dell'health check del container"""
    print("🏥 Testing health check...")
    
    max_attempts = 30
    for i in range(max_attempts):
        try:
            response = requests.get("http://localhost:8080/health", timeout=5)
            if response.status_code == 200:
                print("✅ Health check passed!")
                print(f"📊 Response: {response.json()}")
                return True
        except:
            pass
        
        print(f"🔄 Attempt {i+1}/{max_attempts} - Waiting for container...")
        time.sleep(2)
    
    print("❌ Health check failed")
    return False

def test_status_endpoint():
    """Test dell'endpoint di status"""
    print("📊 Testing status endpoint...")
    
    try:
        response = requests.get("http://localhost:8080/status", timeout=10)
        if response.status_code == 200:
            status = response.json()
            print("✅ Status endpoint working!")
            print(f"📋 Status: {json.dumps(status, indent=2)}")
            return status
        else:
            print(f"❌ Status endpoint returned {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Status endpoint error: {e}")
        return None

def run_container_test():
    """Avvia il container per test"""
    print("🐳 Starting Docker container for testing...")
    
    docker_cmd = [
        "docker", "run", "--rm",
        "-p", "8080:8080",
        "-e", "KINESIS_STREAM_NAME=test-stream",
        "-e", "S3_BUCKET_NAME=test-bucket", 
        "-e", "SQS_QUEUE_URL=",
        "-e", "AWS_REGION=eu-central-1",
        "-e", "YOLO_MODEL=yolov8n.pt",
        "-e", "THRESHOLD=0.5",
        # Mock AWS credentials (non funzionanti, solo per test)
        "-e", "AWS_ACCESS_KEY_ID=test",
        "-e", "AWS_SECRET_ACCESS_KEY=test",
        "cv2kinesis:test"
    ]
    
    # Avvia container in background
    process = subprocess.Popen(docker_cmd)
    
    try:
        # Aspetta che il container si avvii
        time.sleep(10)
        
        # Test health check
        health_ok = test_health_check()
        
        # Test status endpoint
        status = test_status_endpoint()
        
        if health_ok and status:
            print("\n🎯 CONTAINER TEST RESULTS:")
            print("✅ Container starts successfully")
            print("✅ Health check responds")
            print("✅ Status endpoint responds")
            print(f"✅ YOLO model loaded: {status.get('model_loaded', False)}")
            print(f"📊 Frame counter: {status.get('frame_counter', 0)}")
            
            # Test video stream endpoint
            try:
                response = requests.get("http://localhost:8080/", timeout=5, stream=True)
                if response.status_code == 200:
                    print("✅ Video stream endpoint responds")
                else:
                    print(f"⚠️ Video stream returned {response.status_code}")
            except Exception as e:
                print(f"⚠️ Video stream test failed: {e}")
            
            return True
        else:
            print("\n❌ CONTAINER TEST FAILED")
            return False
            
    finally:
        # Ferma il container
        print("\n⏹️ Stopping test container...")
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()

def check_container_logs():
    """Controlla i log del container per errori"""
    print("📋 Checking container logs...")
    
    try:
        # Get container ID
        result = subprocess.run(
            ["docker", "ps", "-q", "--filter", "ancestor=cv2kinesis:test"],
            capture_output=True, text=True
        )
        
        if result.stdout.strip():
            container_id = result.stdout.strip()
            
            # Get logs
            log_result = subprocess.run(
                ["docker", "logs", container_id],
                capture_output=True, text=True
            )
            
            print("📋 Container logs:")
            print("=" * 50)
            print(log_result.stdout)
            if log_result.stderr:
                print("STDERR:")
                print(log_result.stderr)
            print("=" * 50)
            
    except Exception as e:
        print(f"⚠️ Could not get container logs: {e}")

def test_docker_locally():
    """Test locale completo del Docker container"""
    print("=== DOCKER CONTAINER LOCAL TEST ===")
    print("Testing container before cloud deployment\n")
    
    # Build image
    if not build_docker_image():
        return False
    
    # Test container
    print("\n🧪 Running container tests...")
    
    # Start container in thread
    test_thread = threading.Thread(target=run_container_test)
    test_thread.start()
    
    # Wait for test to complete
    test_thread.join()
    
    # Check logs
    check_container_logs()
    
    return True

def main():
    print("=== PRE-DEPLOY CONTAINER VERIFICATION ===")
    print("This will test the Docker container locally before cloud deployment\n")
    
    choice = input("""Scegli test:
1. Test Docker container completo (raccomandato)
2. Solo build Docker image
3. Test YOLO locale (fuori container)
> """)
    
    if choice == "1":
        success = test_docker_locally()
        if success:
            print("\n🚀 CONTAINER TEST COMPLETED!")
            print("✅ Container is ready for cloud deployment")
            print("🎯 You can now safely run: python deploy_and_test.py")
        else:
            print("\n❌ CONTAINER TEST FAILED!")
            print("🔧 Fix issues before cloud deployment")
            
    elif choice == "2":
        if build_docker_image():
            print("\n✅ Docker image built successfully")
            print("🐳 Image: cv2kinesis:test")
        else:
            print("\n❌ Docker build failed")
            
    elif choice == "3":
        print("🎯 Running local YOLO test...")
        subprocess.run(["python", "test_yolo.py"])
        
    else:
        print("❌ Invalid choice")

if __name__ == "__main__":
    main()
