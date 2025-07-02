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

# Configuration globals
STACK_CONFIG = {
    "account": "544547773663",
    "region": "eu-central-1",
    "ecr_registry": "544547773663.dkr.ecr.eu-central-1.amazonaws.com",
    "image_name": "cv2kinesis"
}

def get_user_configuration():
    """Richiede configurazione dall'utente"""
    print("🔧 CONFIGURAZIONE DEPLOYMENT")
    print("=" * 50)
    
    # Environment suffix
    suffix = input("""
🏷️ Environment suffix (per nomi risorse):
   Esempi: -dev, -test, -v2, -staging
   Lascia vuoto per ambiente base
   Suffix: """).strip()
    
    if suffix and not suffix.startswith('-'):
        suffix = f"-{suffix}"
    
    # Stack name
    default_stack_name = f"VideoPipelineStack{suffix.replace('-', '').title() if suffix else ''}"
    stack_name = input(f"""
📦 Nome dello stack CDK:
   Default: {default_stack_name}
   Nome stack: """).strip() or default_stack_name
    
    # Image tag
    image_tag = input("""
🐳 Tag immagine Docker:
   Default: latest
   Tag: """).strip() or "latest"
    
    image_uri = f"{STACK_CONFIG['ecr_registry']}/{STACK_CONFIG['image_name']}:{image_tag}"
    
    config = {
        "suffix": suffix,
        "stack_name": stack_name,
        "image_tag": image_tag,
        "image_uri": image_uri
    }
    
    print(f"""
✅ CONFIGURAZIONE CONFERMATA:
   Environment suffix: '{suffix or '(none)'}'
   Stack name: {stack_name}
   Image URI: {image_uri}
   
   🎯 Risorse che saranno create:
   - Kinesis Stream: cv2kinesis{suffix}
   - S3 Bucket: processedframes-{STACK_CONFIG['account']}-{STACK_CONFIG['region']}{suffix}
   - SQS Queue: processing-results{suffix}
   - EFO Consumer: ecs-consumer{suffix}
""")
    
    confirm = input("Procedere? (y/N): ").strip().lower()
    if confirm != 'y':
        print("❌ Deployment annullato")
        return None
    
    return config

def build_and_push_image(config):
    """Build e push dell'immagine Docker su ECR"""
    print("🔨 Building Docker image...")
    print(f"🐳 Tag: {config['image_tag']}")
    
    # Build
    build_cmd = ["docker", "build", "-t", f"cv2kinesis:{config['image_tag']}", "."]
    result = subprocess.run(build_cmd, cwd="stream_service", shell=True)
    if result.returncode != 0:
        print("❌ Docker build failed")
        return False
    
    print("✅ Docker image built successfully")
    
    # ECR login, tag e push
    print("🚀 Pushing to ECR...")
    commands = [
        f"aws ecr get-login-password --region {STACK_CONFIG['region']} | docker login --username AWS --password-stdin {STACK_CONFIG['ecr_registry']}",
        f"docker tag cv2kinesis:{config['image_tag']} {config['image_uri']}",
        f"docker push {config['image_uri']}"
    ]
    
    for cmd in commands:
        result = subprocess.run(cmd, shell=True, cwd="stream_service")
        if result.returncode != 0:
            print(f"❌ Command failed: {cmd}")
            return False
    
    print("✅ Image pushed to ECR successfully")
    return True

def deploy_stack(config):
    """Deploy CDK stack con parametri configurabili"""
    print("☁️ Deploying CDK stack...")
    print(f"📦 Stack: {config['stack_name']}")
    print(f"🏷️ Suffix: {config['suffix']}")
    print(f"🐳 Image: {config['image_uri']}")
    
    # Debug: verifica directory e comando
    import os
    cdk_dir = os.path.join(os.getcwd(), "cdk")
    print(f"🔍 CDK directory: {cdk_dir}")
    print(f"🔍 Directory exists: {os.path.exists(cdk_dir)}")
    
    if os.path.exists(cdk_dir):
        files = os.listdir(cdk_dir)
        print(f"🔍 Files in cdk/: {files}")
    
    # Trova il comando CDK
    def find_cdk_command():
        """Trova il comando CDK disponibile"""
        import shutil
        import os
        
        # Path comuni dove npm installa CDK su Windows
        npm_prefix = os.path.expanduser("~\\AppData\\Roaming\\npm")
        possible_paths = [
            "cdk",                                          # PATH globale
            "cdk.cmd",                                     # Windows CMD
            os.path.join(npm_prefix, "cdk.cmd"),          # npm globale
            os.path.join(npm_prefix, "cdk"),              # npm senza .cmd
            "npx",                                         # npx fallback
        ]
        
        print("🔍 Searching for CDK command...")
        for cmd_path in possible_paths:
            if cmd_path == "npx":
                # Test npx
                if shutil.which("npx"):
                    print(f"✅ Found CDK via npx: npx cdk")
                    return ["npx", "cdk"]
            elif os.path.isfile(cmd_path):
                # Path assoluto
                print(f"✅ Found CDK at: {cmd_path}")
                return [cmd_path]
            elif shutil.which(cmd_path):
                # Nel PATH
                print(f"✅ Found CDK in PATH: {cmd_path}")
                return [cmd_path]
            else:
                print(f"❌ Not found: {cmd_path}")
        
        print("❌ CDK command not found anywhere")
        return None

    cdk_command = find_cdk_command()
    if not cdk_command:
        print("❌ CDK not found. Trying npx as last resort...")
        # Forza npx se disponibile
        import shutil
        if shutil.which("npx"):
            print("✅ Using npx cdk as fallback")
            cdk_command = ["npx", "cdk"]
        else:
            print("❌ Neither CDK nor npx found. Please install with: npm install -g aws-cdk")
            return False, {}
    
    # Costruisci comando CDK con context
    cdk_cmd = cdk_command + [
        "deploy", 
        "--require-approval", "never",
        "--context", f"suffix={config['suffix']}",
        "--context", f"image_uri={config['image_uri']}"
    ]
    
    print(f"🔍 CDK command: {' '.join(cdk_cmd)}")
    print(f"🔍 Working directory: {os.path.join(os.getcwd(), 'cdk')}")
    
    print("🔧 Executing CDK command...")
    result = subprocess.run(cdk_cmd, cwd="cdk", shell=True)
    if result.returncode != 0:
        print("❌ CDK deploy failed")
        return False, {}
    
    # Get stack outputs
    print("📋 Getting stack outputs...")
    try:
        result = subprocess.run(
            ["aws", "cloudformation", "describe-stacks", "--stack-name", config['stack_name']],
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

def run_producer(config=None):
    """Avvia producer per inviare video a Kinesis"""
    if config is None:
        # Se non abbiamo config, chiediamo all'utente
        print("🔧 CONFIGURAZIONE PRODUCER")
        print("=" * 30)
        
        suffix = input("""
🏷️ Environment suffix da utilizzare:
   Esempi: -dev, -test, -v2, -staging
   Lascia vuoto per ambiente base
   Suffix: """).strip()
        
        if suffix and not suffix.startswith('-'):
            suffix = f"-{suffix}"
        
        config = {"suffix": suffix}
    
    stream_name = f"cv2kinesis{config['suffix']}"
    
    print(f"🎥 Starting producer (webcam → Kinesis)...")
    print(f"📡 Target Kinesis Stream: {stream_name}")
    print("📹 Make sure your webcam is connected!")
    
    # Passa il nome dello stream come variabile d'ambiente
    env = os.environ.copy()
    env['KINESIS_STREAM_NAME'] = stream_name
    
    try:
        subprocess.run([sys.executable, "producer.py"], cwd="simple", env=env)
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

def verify_deployment(config, outputs):
    """Verifica completa del deployment"""
    print("\n🔍 VERIFICA DEPLOYMENT")
    print("=" * 30)
    
    success = True
    
    # 1. Health check del Load Balancer
    if 'LoadBalancerURL' in outputs:
        lb_url = outputs['LoadBalancerURL']
        print(f"🌐 Testing Load Balancer health: {lb_url}/health")
        try:
            import requests
            response = requests.get(f"{lb_url}/health", timeout=15)
            if response.status_code == 200:
                print("✅ Load Balancer health check: OK")
            else:
                print(f"❌ Load Balancer health check failed: {response.status_code}")
                success = False
        except Exception as e:
            print(f"❌ Load Balancer unreachable: {e}")
            success = False
    
    # 2. Verifica Kinesis Stream
    if config['suffix']:
        stream_name = f"cv2kinesis{config['suffix']}"
    else:
        stream_name = "cv2kinesis"
    
    print(f"📡 Checking Kinesis stream: {stream_name}")
    try:
        result = subprocess.run([
            "aws", "kinesis", "describe-stream", 
            "--stream-name", stream_name,
            "--region", STACK_CONFIG['region']
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            stream_data = json.loads(result.stdout)
            status = stream_data['StreamDescription']['StreamStatus']
            print(f"✅ Kinesis stream status: {status}")
            if status != 'ACTIVE':
                print("⚠️ Stream not yet ACTIVE")
                success = False
        else:
            print("❌ Failed to check Kinesis stream")
            success = False
    except Exception as e:
        print(f"❌ Error checking Kinesis: {e}")
        success = False
    
    # 3. Verifica EFO Consumer
    consumer_name = f"ecs-consumer{config['suffix']}"
    print(f"🔄 Checking EFO consumer: {consumer_name}")
    try:
        result = subprocess.run([
            "aws", "kinesis", "list-stream-consumers",
            "--stream-arn", f"arn:aws:kinesis:{STACK_CONFIG['region']}:{STACK_CONFIG['account']}:stream/{stream_name}",
            "--region", STACK_CONFIG['region']
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            consumers_data = json.loads(result.stdout)
            consumer_found = False
            for consumer in consumers_data.get('Consumers', []):
                if consumer['ConsumerName'] == consumer_name:
                    status = consumer['ConsumerStatus']
                    print(f"✅ EFO Consumer status: {status}")
                    consumer_found = True
                    if status != 'ACTIVE':
                        print("⚠️ Consumer not yet ACTIVE")
                        success = False
                    break
            
            if not consumer_found:
                print("❌ EFO Consumer not found")
                success = False
        else:
            print("❌ Failed to check EFO consumers")
            success = False
    except Exception as e:
        print(f"❌ Error checking EFO consumer: {e}")
        success = False
    
    # 4. Summary
    if success:
        print("\n🎉 DEPLOYMENT VERIFICATION: SUCCESS!")
        print("✅ All components are healthy and ready")
    else:
        print("\n⚠️ DEPLOYMENT VERIFICATION: PARTIAL SUCCESS")
        print("Some components may need more time to become fully ready")
    
    return success

def main():
    print("=== DEPLOY E TEST INFRASTRUTTURA CLOUD COMPLETA ===")
    print("🏗️ Architettura: Webcam → Kinesis → ECS → S3 → SQS → Consumer")
    print()
    
    choice = input("""Scegli operazione:
1. 🚀 Build e deploy completo (con configurazione)
2. 🔨 Solo build e push immagine Docker
3. ☁️  Solo deploy CDK stack  
4. 🎥 Test producer (webcam → Kinesis)
5. 📨 Test consumer (SQS → Console)
6. 🔄 Test completo (producer + consumer)
7. 📋 Lista stack deployati
> """)
    
    if choice == "1":
        # Build e deploy completo
        config = get_user_configuration()
        if not config:
            return
        
        if not build_and_push_image(config):
            return
        
        success, outputs = deploy_stack(config)
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
            
            # Verifica deployment
            verify_deployment(config, outputs)
            
            print("\n🚀 Ready to test! Run options 4 or 6 to test the pipeline.")
        
    elif choice == "2":
        config = get_user_configuration()
        if config:
            build_and_push_image(config)
        
    elif choice == "3":
        config = get_user_configuration()
        if config:
            success, outputs = deploy_stack(config)
            if success and outputs:
                verify_deployment(config, outputs)
        
    elif choice == "4":
        # Test producer con configurazione
        config = {"suffix": ""}  # Default
        
        # Chiedi suffix se non specificato
        suffix = input("""
🎥 CONFIGURAZIONE PRODUCER
🏷️ Environment suffix da utilizzare:
   Esempi: -dev, -test, -v2, -staging
   Lascia vuoto per ambiente base
   Suffix: """).strip()
        
        if suffix and not suffix.startswith('-'):
            suffix = f"-{suffix}"
        
        config["suffix"] = suffix
        stream_name = f"cv2kinesis{suffix}"
        
        print(f"📡 Connecting to Kinesis Stream: {stream_name}")
        
        # Verifica che lo stream esista
        try:
            result = subprocess.run([
                "aws", "kinesis", "describe-stream", 
                "--stream-name", stream_name,
                "--region", STACK_CONFIG['region']
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"❌ Kinesis stream '{stream_name}' not found!")
                print(f"💡 Make sure to deploy the stack with suffix '{suffix}' first")
                return
            else:
                stream_data = json.loads(result.stdout)
                status = stream_data['StreamDescription']['StreamStatus']
                print(f"✅ Stream found with status: {status}")
                
        except Exception as e:
            print(f"⚠️ Cannot verify stream: {e}")
        
        run_producer(config)
        
    elif choice == "5":
        # Test consumer con selezione automatica
        print("📨 CONFIGURAZIONE CONSUMER")
        print("=" * 30)
        
        # Opzione 1: Inserire manualmente SQS URL
        print("\nOpzioni disponibili:")
        print("1. Inserire manualmente SQS Queue URL")
        print("2. Selezionare da stack deployati")
        
        sub_choice = input("Scegli opzione (1/2): ").strip()
        
        if sub_choice == "1":
            sqs_url = input("Enter SQS Queue URL: ")
            if sqs_url:
                run_consumer(sqs_url)
            else:
                print("❌ SQS URL required")
        
        elif sub_choice == "2":
            # Lista stack disponibili
            try:
                result = subprocess.run([
                    "aws", "cloudformation", "list-stacks",
                    "--stack-status-filter", "CREATE_COMPLETE", "UPDATE_COMPLETE",
                    "--region", STACK_CONFIG['region']
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    stacks_data = json.loads(result.stdout)
                    video_stacks = [
                        stack for stack in stacks_data['StackSummaries'] 
                        if stack['StackName'].startswith('VideoPipelineStack')
                    ]
                    
                    if not video_stacks:
                        print("❌ No VideoPipelineStack found")
                        return
                    
                    print("\nStack disponibili:")
                    for i, stack in enumerate(video_stacks, 1):
                        print(f"{i}. {stack['StackName']} (Status: {stack['StackStatus']})")
                    
                    try:
                        choice_idx = int(input("Seleziona stack (numero): ")) - 1
                        if 0 <= choice_idx < len(video_stacks):
                            selected_stack = video_stacks[choice_idx]['StackName']
                            
                            # Get stack outputs
                            result = subprocess.run([
                                "aws", "cloudformation", "describe-stacks", 
                                "--stack-name", selected_stack,
                                "--region", STACK_CONFIG['region']
                            ], capture_output=True, text=True)
                            
                            if result.returncode == 0:
                                stack_data = json.loads(result.stdout)
                                outputs = {}
                                
                                for output in stack_data['Stacks'][0].get('Outputs', []):
                                    outputs[output['OutputKey']] = output['OutputValue']
                                
                                sqs_url = outputs.get('SQSQueueURL')
                                if sqs_url:
                                    print(f"✅ Using SQS Queue: {sqs_url}")
                                    run_consumer(sqs_url)
                                else:
                                    print("❌ SQS Queue URL not found in stack outputs")
                            else:
                                print("❌ Failed to get stack outputs")
                        else:
                            print("❌ Invalid selection")
                    except ValueError:
                        print("❌ Invalid number")
                else:
                    print("❌ Failed to list stacks")
            except Exception as e:
                print(f"❌ Error: {e}")
        else:
            print("❌ Invalid choice")
            
    elif choice == "6":
        # Test completo con selezione stack
        print("🚀 TEST COMPLETO (PRODUCER + CONSUMER)")
        print("=" * 40)
        
        # Opzione 1: Usa outputs dall'ultimo deployment
        # Opzione 2: Seleziona da stack disponibili
        print("\nCome vuoi configurare il test?")
        print("1. Inserire manualmente SQS Queue URL e suffix")
        print("2. Selezionare da stack deployati automaticamente")
        
        sub_choice = input("Scegli opzione (1/2): ").strip()
        
        sqs_url = None
        suffix = ""
        
        if sub_choice == "1":
            sqs_url = input("Enter SQS Queue URL: ")
            suffix = input("Enter environment suffix (es. -dev, -test): ").strip()
            if suffix and not suffix.startswith('-'):
                suffix = f"-{suffix}"
                
        elif sub_choice == "2":
            # Lista e seleziona stack
            try:
                result = subprocess.run([
                    "aws", "cloudformation", "list-stacks",
                    "--stack-status-filter", "CREATE_COMPLETE", "UPDATE_COMPLETE",
                    "--region", STACK_CONFIG['region']
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    stacks_data = json.loads(result.stdout)
                    video_stacks = [
                        stack for stack in stacks_data['StackSummaries'] 
                        if stack['StackName'].startswith('VideoPipelineStack')
                    ]
                    
                    if not video_stacks:
                        print("❌ No VideoPipelineStack found")
                        return
                    
                    print("\nStack disponibili:")
                    for i, stack in enumerate(video_stacks, 1):
                        print(f"{i}. {stack['StackName']}")
                    
                    try:
                        choice_idx = int(input("Seleziona stack (numero): ")) - 1
                        if 0 <= choice_idx < len(video_stacks):
                            selected_stack = video_stacks[choice_idx]['StackName']
                            
                            # Extract suffix from stack name
                            if selected_stack == "VideoPipelineStack":
                                suffix = ""
                            else:
                                # VideoPipelineStackDev -> -dev
                                suffix_part = selected_stack.replace("VideoPipelineStack", "")
                                suffix = f"-{suffix_part.lower()}" if suffix_part else ""
                            
                            # Get SQS URL from stack outputs
                            result = subprocess.run([
                                "aws", "cloudformation", "describe-stacks", 
                                "--stack-name", selected_stack,
                                "--region", STACK_CONFIG['region']
                            ], capture_output=True, text=True)
                            
                            if result.returncode == 0:
                                stack_data = json.loads(result.stdout)
                                outputs = {}
                                
                                for output in stack_data['Stacks'][0].get('Outputs', []):
                                    outputs[output['OutputKey']] = output['OutputValue']
                                
                                sqs_url = outputs.get('SQSQueueURL')
                                if not sqs_url:
                                    print("❌ SQS Queue URL not found in stack outputs")
                                    return
                                
                                print(f"✅ Selected stack: {selected_stack}")
                                print(f"✅ Using suffix: '{suffix}'")
                                print(f"✅ SQS Queue: {sqs_url}")
                            else:
                                print("❌ Failed to get stack outputs")
                                return
                        else:
                            print("❌ Invalid selection")
                            return
                    except ValueError:
                        print("❌ Invalid number")
                        return
                else:
                    print("❌ Failed to list stacks")
                    return
            except Exception as e:
                print(f"❌ Error: {e}")
                return
        else:
            print("❌ Invalid choice")
            return
        
        if not sqs_url:
            print("❌ SQS URL required")
            return
        
        print(f"\n🚀 Starting complete test...")
        print(f"📡 Kinesis Stream: cv2kinesis{suffix}")
        print(f"📨 SQS Queue: {sqs_url}")
        print("🎥 Producer will start first, then consumer")
        print("📹 Make sure your webcam is working!")
        
        import threading
        
        # Start consumer in background
        consumer_thread = threading.Thread(target=run_consumer, args=(sqs_url,), daemon=True)
        consumer_thread.start()
        
        time.sleep(3)  # Give consumer time to start
        
        # Start producer with correct config
        config = {"suffix": suffix}
        try:
            run_producer(config)
        except KeyboardInterrupt:
            print("\n⏹️ Test completed")
            
    elif choice == "7":
        # Lista stack deployati
        print("📋 STACK DEPLOYATI")
        print("=" * 20)
        
        try:
            result = subprocess.run([
                "aws", "cloudformation", "list-stacks",
                "--stack-status-filter", "CREATE_COMPLETE", "UPDATE_COMPLETE", "CREATE_IN_PROGRESS", "UPDATE_IN_PROGRESS",
                "--region", STACK_CONFIG['region']
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                stacks_data = json.loads(result.stdout)
                video_stacks = [
                    stack for stack in stacks_data['StackSummaries'] 
                    if stack['StackName'].startswith('VideoPipelineStack')
                ]
                
                if not video_stacks:
                    print("❌ Nessun VideoPipelineStack trovato")
                    return
                
                print(f"\n🔍 Trovati {len(video_stacks)} stack:")
                for stack in video_stacks:
                    status_emoji = "✅" if "COMPLETE" in stack['StackStatus'] else "🔄"
                    
                    # Extract suffix from name
                    suffix = ""
                    if stack['StackName'] != "VideoPipelineStack":
                        suffix_part = stack['StackName'].replace("VideoPipelineStack", "")
                        suffix = f" (suffix: -{suffix_part.lower()})" if suffix_part else ""
                    
                    print(f"   {status_emoji} {stack['StackName']}{suffix}")
                    print(f"      Status: {stack['StackStatus']}")
                    print(f"      Created: {stack['CreationTime']}")
                    
                    # Get outputs for complete stacks
                    if "COMPLETE" in stack['StackStatus']:
                        try:
                            outputs_result = subprocess.run([
                                "aws", "cloudformation", "describe-stacks", 
                                "--stack-name", stack['StackName'],
                                "--region", STACK_CONFIG['region']
                            ], capture_output=True, text=True)
                            
                            if outputs_result.returncode == 0:
                                outputs_data = json.loads(outputs_result.stdout)
                                outputs = {}
                                
                                for output in outputs_data['Stacks'][0].get('Outputs', []):
                                    outputs[output['OutputKey']] = output['OutputValue']
                                
                                print(f"      🎯 Resources:")
                                if 'KinesisStreamName' in outputs:
                                    print(f"         📡 Kinesis: {outputs['KinesisStreamName']}")
                                if 'S3BucketName' in outputs:
                                    print(f"         📦 S3: {outputs['S3BucketName']}")
                                if 'LoadBalancerURL' in outputs:
                                    print(f"         🌐 LB: {outputs['LoadBalancerURL']}")
                        except:
                            pass
                    
                    print()
                    
            else:
                print("❌ Errore nel recupero degli stack")
                
        except Exception as e:
            print(f"❌ Errore: {e}")
    else:
        print("❌ Invalid choice")

if __name__ == "__main__":
    main()
