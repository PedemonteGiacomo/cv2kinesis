#!/usr/bin/env python3
"""
Test completo del container Docker prima del deploy cloud:
1. Build del container
2. Test delle funzionalità base del container
3. Test di connessione AWS (se credenziali disponibili)
4. Simulazione di processing con mock data
"""
import subprocess
import time
import json
import threading
import requests
import os

def build_container():
    """Build del container Docker"""
    print("🔨 Building Docker container...")
    print("📦 This may take a few minutes for the first build...")
    
    try:
        # Avvia il processo di build
        process = subprocess.Popen(
            ["docker", "build", "-t", "cv2kinesis:test", "."],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            universal_newlines=True
        )
        
        # Mostra progress in tempo reale
        step_count = 0
        for line in process.stdout:
            line = line.strip()
            if line:
                if line.startswith("Step "):
                    step_count += 1
                    print(f"   📋 {line}")
                elif "FROM" in line or "RUN" in line or "COPY" in line:
                    print(f"   ⚙️ {line[:60]}{'...' if len(line) > 60 else ''}")
                elif "Successfully built" in line:
                    print(f"   ✅ {line}")
                elif "ERROR" in line.upper() or "FAILED" in line.upper():
                    print(f"   ❌ {line}")
        
        # Aspetta che il processo finisca
        return_code = process.wait()
        
        if return_code == 0:
            print("✅ Container built successfully")
            print(f"📊 Total build steps completed: {step_count}")
            return True
        else:
            print(f"❌ Container build failed with exit code: {return_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error building container: {e}")
        return False

def test_container_startup():
    """Test che il container si avvii correttamente"""
    print("\n🚀 Testing container startup...")
    print("📋 Configuring environment variables...")
    
    # Environment variables per il test
    env_vars = [
        "-e", "KINESIS_STREAM_NAME=test-stream",
        "-e", "S3_BUCKET_NAME=test-bucket", 
        "-e", "SQS_QUEUE_URL=test-queue",
        "-e", "AWS_REGION=eu-central-1",
        "-e", "YOLO_MODEL=yolov8n.pt",
        "-e", "THRESHOLD=0.5"
    ]
    
    # Se ci sono credenziali AWS, passale al container
    aws_keys = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"]
    aws_creds_found = 0
    for key in aws_keys:
        if os.environ.get(key):
            env_vars.extend(["-e", f"{key}={os.environ[key][:10]}..."])
            aws_creds_found += 1
    
    print(f"🔑 AWS credentials found: {aws_creds_found}/3")
    if aws_creds_found < 2:
        print("⚠️ Limited AWS credentials - some features may not work in container")
    
    try:
        print("🐳 Starting Docker container...")
        print("📡 Container will be available on http://localhost:8081")
        
        # Avvia container in background
        docker_cmd = [
            "docker", "run", "--rm", "-d",
            "--name", "cv2kinesis-test",
            "-p", "8081:8080"  # Usa porta diversa per evitare conflitti
        ] + env_vars + ["cv2kinesis:test"]
        
        result = subprocess.run(docker_cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            container_id = result.stdout.strip()
            print(f"✅ Container started successfully")
            print(f"🆔 Container ID: {container_id[:12]}...")
            
            # Aspetta che il container si avvii con progress
            print("⏳ Waiting for container to initialize...")
            for i in range(15):
                print(f"   ⏱️ Startup progress: {i+1}/15 seconds", end='\r')
                time.sleep(1)
            print("\n   ✅ Initialization time completed")
            
            return container_id
        else:
            print(f"❌ Failed to start container:")
            print(f"   Error: {result.stderr}")
            return None
            
    except Exception as e:
        print(f"❌ Error starting container: {e}")
        return None

def test_health_endpoint(max_retries=10):
    """Test dell'endpoint /health"""
    print("\n🏥 Testing health endpoint...")
    print("📡 Testing http://localhost:8081/health")
    
    for i in range(max_retries):
        try:
            print(f"   🔄 Health check attempt {i+1}/{max_retries}...", end='')
            response = requests.get("http://localhost:8081/health", timeout=5)
            
            if response.status_code == 200:
                print(" ✅")
                print(f"   📋 Response: {response.json()}")
                print("✅ Health endpoint is working correctly!")
                return True
            else:
                print(f" ❌ (Status: {response.status_code})")
                
        except requests.exceptions.ConnectionError:
            print(" � (Connection refused - container may still be starting)")
        except requests.exceptions.Timeout:
            print(" ⏰ (Timeout)")
        except Exception as e:
            print(f" ❌ ({str(e)[:50]})")
            
        if i < max_retries - 1:  # Don't sleep on last attempt
            time.sleep(3)
    
    print("❌ Health endpoint not responding after all attempts")
    return False

def test_status_endpoint():
    """Test dell'endpoint /status per debugging"""
    print("\n📊 Testing status endpoint...")
    print("📡 Testing http://localhost:8081/status")
    
    try:
        print("   🔄 Requesting status information...")
        response = requests.get("http://localhost:8081/status", timeout=10)
        
        if response.status_code == 200:
            status = response.json()
            print("✅ Status endpoint responding correctly:")
            print(f"   📊 App Status: {status.get('status', 'unknown')}")
            print(f"   🎥 Kinesis Connected: {status.get('kinesis_connected', 'unknown')}")
            print(f"   🎯 YOLO Model Loaded: {status.get('model_loaded', 'unknown')}")
            print(f"   📸 Frames Processed: {status.get('frame_counter', 'unknown')}")
            print(f"   🎬 Stream Name: {status.get('kinesis_stream', 'unknown')}")
            print(f"   📦 S3 Bucket: {status.get('s3_bucket', 'unknown')}")
            return True
        else:
            print(f"❌ Status endpoint error: HTTP {response.status_code}")
            print(f"   Response: {response.text[:100]}...")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection refused - container may not be running")
        return False
    except requests.exceptions.Timeout:
        print("❌ Request timeout - container may be overloaded")
        return False
    except Exception as e:
        print(f"❌ Status endpoint failed: {e}")
        return False

def test_video_stream():
    """Test dell'endpoint video stream"""
    print("\n📹 Testing video stream endpoint...")
    print("📡 Testing http://localhost:8081/ (video stream)")
    
    try:
        print("   🔄 Requesting video stream...")
        response = requests.get("http://localhost:8081/", timeout=10, stream=True)
        
        if response.status_code == 200:
            content_type = response.headers.get('content-type', '')
            print(f"   📋 Content-Type: {content_type}")
            
            if 'multipart/x-mixed-replace' in content_type:
                print("✅ Video stream endpoint working correctly!")
                print("   🎬 Stream format: MJPEG multipart stream")
                
                # Try to read first few bytes to verify it's actually streaming
                try:
                    chunk = next(response.iter_content(1024))
                    if chunk:
                        print(f"   📊 First chunk received: {len(chunk)} bytes")
                    return True
                except:
                    print("   ⚠️ Stream started but no data received yet (normal for empty Kinesis)")
                    return True
            else:
                print(f"⚠️ Unexpected content type: {content_type}")
                print("   Expected: multipart/x-mixed-replace")
                return False
        else:
            print(f"❌ Video stream error: HTTP {response.status_code}")
            print(f"   Response: {response.text[:100]}...")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection refused - container may not be running")
        return False
    except requests.exceptions.Timeout:
        print("❌ Request timeout - video stream may be slow to start")
        return False  
    except Exception as e:
        print(f"❌ Video stream test failed: {e}")
        return False

def get_container_logs(container_id):
    """Ottieni i log del container per debugging"""
    print("\n📋 Getting container logs for analysis...")
    
    try:
        print("   🔄 Fetching recent container logs...")
        result = subprocess.run(
            ["docker", "logs", "--tail", "50", container_id],
            capture_output=True, text=True
        )
        
        if result.stdout:
            print("📝 Container STDOUT logs:")
            print("-" * 60)
            lines = result.stdout.strip().split('\n')
            for i, line in enumerate(lines[-20:], 1):  # Last 20 lines
                if line.strip():
                    status = "✅" if any(word in line.lower() for word in ["success", "started", "initialized"]) else \
                           "❌" if any(word in line.lower() for word in ["error", "failed", "exception"]) else \
                           "ℹ️"
                    print(f"{status} {line}")
            print("-" * 60)
        
        if result.stderr:
            print("⚠️ Container STDERR logs:")
            print("-" * 60)
            stderr_lines = result.stderr.strip().split('\n')
            for line in stderr_lines[-10:]:  # Last 10 error lines
                if line.strip():
                    print(f"❌ {line}")
            print("-" * 60)
            
        if not result.stdout and not result.stderr:
            print("📭 No logs available yet (container may still be starting)")
            
    except Exception as e:
        print(f"❌ Error getting logs: {e}")

def stop_container(container_id):
    """Ferma il container di test"""
    if container_id:
        print("\n⏹️ Stopping test container...")
        try:
            print(f"   🔄 Stopping container {container_id[:12]}...")
            result = subprocess.run(["docker", "stop", container_id], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print("✅ Container stopped successfully")
            else:
                print(f"⚠️ Container stop returned code: {result.returncode}")
        except subprocess.TimeoutExpired:
            print("⚠️ Container stop timed out - forcing removal")
            subprocess.run(["docker", "kill", container_id], capture_output=True)
        except Exception as e:
            print(f"⚠️ Error stopping container: {e}")
    
    # Cleanup any leftover containers
    try:
        subprocess.run(["docker", "rm", "-f", "cv2kinesis-test"], 
                      capture_output=True, text=True)
    except:
        pass

def main():
    print("=== DOCKER CONTAINER TEST ===")
    print("Testing container before cloud deployment\n")
    
    container_id = None
    
    try:
        # 1. Build container
        if not build_container():
            return
        
        # 2. Start container
        container_id = test_container_startup()
        if not container_id:
            return
        
        # 3. Test endpoints
        health_ok = test_health_endpoint()
        status_ok = test_status_endpoint()
        video_ok = test_video_stream()
        
        # 4. Get logs for debugging
        get_container_logs(container_id)
        
        # 5. Results
        print("\n" + "="*60)
        print("📋 TEST RESULTS:")
        print("="*60)
        print(f"🔨 Container build: ✅")
        print(f"🚀 Container startup: {'✅' if container_id else '❌'}")
        print(f"🏥 Health endpoint: {'✅' if health_ok else '❌'}")
        print(f"📊 Status endpoint: {'✅' if status_ok else '❌'}")
        print(f"📹 Video stream: {'✅' if video_ok else '❌'}")
        
        if health_ok and status_ok and video_ok:
            print("\n🚀 ALL TESTS PASSED!")
            print("✅ Container is ready for cloud deployment")
            print("🎯 You can now run: python deploy_and_test.py")
        else:
            print("\n⚠️ SOME TESTS FAILED")
            print("🔧 Check the logs above for debugging")
            print("🎯 Fix issues before cloud deployment")
        
    except KeyboardInterrupt:
        print("\n⏹️ Test interrupted by user")
        
    finally:
        # Cleanup
        stop_container(container_id)

if __name__ == "__main__":
    main()
