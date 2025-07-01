#!/usr/bin/env python3
"""
Test infrastruttura con RabbitMQ locale per simulare il flusso cloud:
Producer → Kinesis → Docker Processing → RabbitMQ → Consumer (ascolta messaggi JSON)

Simula l'infrastruttura finale:
- Processing genera messaggi JSON con risultati detection
- Consumer ascolta RabbitMQ per ricevere i messaggi
- Perfetto per sviluppo frontend separato
"""
import subprocess
import time
import threading
import sys
import os
import json

def start_rabbitmq():
    """Avvia RabbitMQ con Docker"""
    print("🐰 Avvio RabbitMQ locale...")
    docker_cmd = [
        "docker", "run", "--rm", "-d",
        "--name", "rabbitmq-test",
        "-p", "5672:5672", 
        "-p", "15672:15672",
        "-e", "RABBITMQ_DEFAULT_USER=admin",
        "-e", "RABBITMQ_DEFAULT_PASS=admin123",
        "rabbitmq:3-management"
    ]
    
    try:
        subprocess.run(docker_cmd, check=True)
        print("✅ RabbitMQ avviato su:")
        print("   - AMQP: localhost:5672 (admin/admin123)")
        print("   - Management UI: http://localhost:15672")
        time.sleep(10)  # Aspetta che RabbitMQ si avvii completamente
        return True
    except subprocess.CalledProcessError:
        print("❌ Errore nell'avvio di RabbitMQ")
        return False

def run_producer():
    """Avvia il producer (webcam → Kinesis)"""
    print("🎥 Avvio Producer (webcam → Kinesis)...")
    original_dir = os.getcwd()
    try:
        os.chdir("simple")
        subprocess.run([sys.executable, "producer.py"])
    finally:
        os.chdir(original_dir)

def run_docker_processing_with_rabbitmq():
    """Avvia Docker processing che invia risultati a RabbitMQ"""
    print("🐳 Avvio Docker processing (Kinesis → YOLO → RabbitMQ)...")
    print("📋 Container: cv2kinesis:latest")
    print("🔄 Processing: Kinesis → YOLO detection → RabbitMQ messages")
    
    # Avvia container con RabbitMQ configurato
    docker_cmd = [
        "docker", "run", 
        "--rm",
        "-p", "8080:8080",
        "-e", "KINESIS_STREAM_NAME=cv2kinesis",
        "-e", "AWS_REGION=eu-central-1", 
        "-e", "YOLO_MODEL=yolov8n.pt",
        "-e", "THRESHOLD=0.5",
        # Configurazione RabbitMQ
        "-e", "RABBITMQ_HOST=host.docker.internal",
        "-e", "RABBITMQ_PORT=5672",
        "-e", "RABBITMQ_USER=admin", 
        "-e", "RABBITMQ_PASS=admin123",
        "-e", "RABBITMQ_QUEUE=processing_results",
        # AWS credentials
        "-e", f"AWS_ACCESS_KEY_ID={os.environ.get('AWS_ACCESS_KEY_ID', '')}",
        "-e", f"AWS_SECRET_ACCESS_KEY={os.environ.get('AWS_SECRET_ACCESS_KEY', '')}",
        "-e", f"AWS_SESSION_TOKEN={os.environ.get('AWS_SESSION_TOKEN', '')}",
        "cv2kinesis:latest"
    ]
    
    subprocess.run(docker_cmd)

def run_message_consumer():
    """Consumer che ascolta i messaggi RabbitMQ"""
    print("📨 Avvio Message Consumer (RabbitMQ → JSON processing results)...")
    time.sleep(5)  # Aspetta che RabbitMQ e processing siano pronti
    
    # Crea un semplice consumer Python per RabbitMQ
    consumer_script = '''
import pika
import json
import time
import sys

def connect_rabbitmq():
    """Connessione a RabbitMQ con retry"""
    max_retries = 30
    for i in range(max_retries):
        try:
            credentials = pika.PlainCredentials('admin', 'admin123')
            connection = pika.BlockingConnection(
                pika.ConnectionParameters('localhost', 5672, '/', credentials)
            )
            return connection
        except Exception as e:
            print(f"🔄 Tentativo {i+1}/{max_retries} - Connecting to RabbitMQ...")
            time.sleep(2)
    raise Exception("❌ Impossibile connettersi a RabbitMQ")

def callback(ch, method, properties, body):
    """Callback per processare i messaggi ricevuti"""
    try:
        message = json.loads(body.decode())
        print("\\n" + "="*60)
        print("📨 MESSAGGIO RICEVUTO DA PROCESSING:")
        print("="*60)
        print(json.dumps(message, indent=2))
        print("="*60)
        
        # Esempio di come il frontend potrebbe usare questi dati:
        print(f"🎯 Detections trovate: {message.get('detections_count', 0)}")
        print(f"📸 Frame index: {message.get('frame_index', 'N/A')}")
        print(f"⏰ Timestamp: {message.get('timestamp', 'N/A')}")
        if 'summary' in message:
            for i, detection in enumerate(message['summary']):
                print(f"   {i+1}. {detection['class']} (conf: {detection['conf']:.2f})")
        print()
        
        # Acknowledge del messaggio
        ch.basic_ack(delivery_tag=method.delivery_tag)
        
    except json.JSONDecodeError as e:
        print(f"❌ Errore parsing JSON: {e}")
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        print(f"❌ Errore processing messaggio: {e}")
        ch.basic_ack(delivery_tag=method.delivery_tag)

def main():
    print("🎯 Consumer in ascolto su RabbitMQ per messaggi di processing...")
    print("📨 Queue: processing_results")
    print("🔄 Waiting for messages. Premi CTRL+C per uscire\\n")
    
    try:
        connection = connect_rabbitmq()
        channel = connection.channel()
        
        # Dichiara la queue (in caso non esista)
        channel.queue_declare(queue='processing_results', durable=True)
        
        # Configura il consumer
        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(queue='processing_results', on_message_callback=callback)
        
        print("✅ Connesso a RabbitMQ - In ascolto...")
        channel.start_consuming()
        
    except KeyboardInterrupt:
        print("\\n⏹️ Fermando consumer...")
        try:
            channel.stop_consuming()
            connection.close()
        except:
            pass
    except Exception as e:
        print(f"❌ Errore: {e}")

if __name__ == "__main__":
    main()
'''
    
    # Salva e esegui lo script del consumer
    with open("rabbitmq_consumer.py", "w") as f:
        f.write(consumer_script)
    
    subprocess.run([sys.executable, "rabbitmq_consumer.py"])

def stop_rabbitmq():
    """Ferma RabbitMQ"""
    try:
        subprocess.run(["docker", "stop", "rabbitmq-test"], check=True)
        print("✅ RabbitMQ fermato")
    except:
        pass

def check_prerequisites():
    """Verifica Docker e immagine"""
    # Verifica Docker
    try:
        subprocess.run(["docker", "--version"], capture_output=True, check=True)
    except:
        print("❌ Docker non disponibile")
        return False
    
    # Verifica immagine cv2kinesis
    try:
        result = subprocess.run(["docker", "images", "-q", "cv2kinesis:latest"], 
                              capture_output=True, text=True)
        if not result.stdout.strip():
            print("❌ Immagine Docker 'cv2kinesis:latest' non trovata!")
            print("🔨 Build prima l'immagine con:")
            print("   cd stream_service && docker build -t cv2kinesis:latest .")
            return False
    except:
        print("❌ Errore nel check dell'immagine Docker")
        return False
    
    return True

def main():
    print("=== TEST INFRASTRUTTURA CON RABBITMQ ===")
    print("Test del flusso completo per sviluppo frontend:")
    print("1. Producer: webcam → Kinesis")
    print("2. Docker processing: Kinesis → YOLO → RabbitMQ messages") 
    print("3. Message consumer: RabbitMQ → JSON results logging")
    print("4. Frontend team: può ascoltare RabbitMQ per ricevere risultati")
    print()
    
    if not check_prerequisites():
        return
    
    choice = input("Scegli test:\n1. Solo RabbitMQ\n2. Solo Producer\n3. Solo Processing\n4. Solo Message Consumer\n5. Flusso completo (raccomandato)\n> ")
    
    if choice == "1":
        if start_rabbitmq():
            print("RabbitMQ Management: http://localhost:15672 (admin/admin123)")
            input("Premi Enter per fermare RabbitMQ...")
            stop_rabbitmq()
    elif choice == "2":
        run_producer()
    elif choice == "3":
        run_docker_processing_with_rabbitmq()
    elif choice == "4":
        run_message_consumer()
    elif choice == "5":
        print("🚀 Avvio flusso completo infrastruttura...")
        
        # Avvia RabbitMQ
        if not start_rabbitmq():
            return
        
        try:
            # Avvia tutti i servizi
            processing_thread = threading.Thread(target=run_docker_processing_with_rabbitmq)
            producer_thread = threading.Thread(target=run_producer)
            consumer_thread = threading.Thread(target=run_message_consumer)
            
            processing_thread.start()
            time.sleep(8)  # Aspetta che processing si avvii
            
            producer_thread.start()
            time.sleep(3)  # Aspetta che producer inizi
            
            consumer_thread.start()
            
            print("\\n✅ Infrastruttura completa avviata:")
            print("- 🐰 RabbitMQ: localhost:5672")
            print("- 🎥 Producer: webcam → Kinesis")
            print("- 🐳 Processing: Kinesis → RabbitMQ")
            print("- 📨 Consumer: messaggi JSON nel terminale")
            print("- 🌐 RabbitMQ UI: http://localhost:15672")
            print("\\n🎯 Ora il frontend team può connettersi a RabbitMQ!")
            print("Premi Ctrl+C per fermare tutto")
            
            producer_thread.join()
            processing_thread.join()
            consumer_thread.join()
            
        except KeyboardInterrupt:
            print("\\n⏹️ Fermando infrastruttura...")
        finally:
            stop_rabbitmq()
            # Cleanup
            try:
                os.remove("rabbitmq_consumer.py")
            except:
                pass
    else:
        print("Scelta non valida")

if __name__ == "__main__":
    main()
