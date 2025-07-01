#!/usr/bin/env python3
"""
Test completo del flusso locale con processing containerizzato (analogo al cloud):
1. Producer locale → Kinesis → Docker container (Flask app) → browser
2. Simula esattamente il comportamento cloud: ECS Fargate = Docker locale
"""
import subprocess
import time
import threading
import sys
import os
import json

def run_producer():
    """Avvia il producer nella cartella simple"""
    print("🎥 Avvio Producer (webcam → Kinesis)...")
    original_dir = os.getcwd()
    try:
        os.chdir("simple")
        subprocess.run([sys.executable, "producer.py"])
    finally:
        os.chdir(original_dir)

def run_docker_processing():
    """Avvia il container Docker per il processing (simula ECS Fargate)"""
    print("🐳 Avvio Docker container (simula ECS Fargate)...")
    print("📋 Container: cv2kinesis:latest")
    print("🌐 Endpoint: http://localhost:8080")
    print("🔄 Processing: Kinesis → YOLO → HTTP stream")
    
    # Avvia il container con le stesse env vars del cloud
    docker_cmd = [
        "docker", "run", 
        "--rm",
        "-p", "8080:8080",
        "-e", "KINESIS_STREAM_NAME=cv2kinesis",
        "-e", "AWS_REGION=eu-central-1", 
        "-e", "YOLO_MODEL=yolov8n.pt",
        "-e", "THRESHOLD=0.5",
        # Passa le credenziali AWS al container
        "-e", f"AWS_ACCESS_KEY_ID={os.environ.get('AWS_ACCESS_KEY_ID', '')}",
        "-e", f"AWS_SECRET_ACCESS_KEY={os.environ.get('AWS_SECRET_ACCESS_KEY', '')}",
        "-e", f"AWS_SESSION_TOKEN={os.environ.get('AWS_SESSION_TOKEN', '')}",
        "cv2kinesis:latest"
    ]
    
    subprocess.run(docker_cmd)

def run_consumer_logs():
    """Avvia consumer locale per logging detection (opzionale)"""
    print("� Avvio Consumer logs (Kinesis → detection logging)...")
    time.sleep(3)  # Aspetta che il producer inizi
    original_dir = os.getcwd()
    try:
        os.chdir("simple")
        subprocess.run([sys.executable, "consumer.py"])
    finally:
        os.chdir(original_dir)

def check_docker_image():
    """Verifica che l'immagine Docker sia disponibile"""
    try:
        result = subprocess.run(["docker", "images", "-q", "cv2kinesis:latest"], 
                              capture_output=True, text=True)
        if not result.stdout.strip():
            print("❌ Immagine Docker 'cv2kinesis:latest' non trovata!")
            print("🔨 Build prima l'immagine con:")
            print("   cd stream_service && docker build -t cv2kinesis:latest .")
            return False
        else:
            print("✅ Immagine Docker 'cv2kinesis:latest' trovata")
            return True
    except subprocess.CalledProcessError:
        print("❌ Docker non disponibile o errore nel check dell'immagine")
        return False

def main():
    print("=== TEST FLUSSO LOCALE CONTAINERIZZATO (SIMULA CLOUD) ===")
    print("Questo script testa il pipeline con Docker (come ECS Fargate):")
    print("1. Producer locale: webcam → Kinesis stream 'cv2kinesis'")
    print("2. Docker container: Kinesis → YOLO → HTTP video stream")  
    print("3. Browser: http://localhost:8080 per vedere il video")
    print("4. [Opzionale] Consumer logs: logging detection nel terminale")
    print()
    
    # Verifica che Docker e l'immagine siano disponibili
    if not check_docker_image():
        return
        
    choice = input("Scegli cosa testare:\n1. Solo Producer\n2. Solo Docker processing\n3. Producer + Docker (raccomandato)\n4. Tutto + Consumer logs\n> ")
    
    if choice == "1":
        run_producer()
    elif choice == "2":
        run_docker_processing()
    elif choice == "3":
        # Producer e Docker processing in parallelo (simula cloud)
        print("\n🚀 Avvio flusso completo containerizzato...")
        
        producer_thread = threading.Thread(target=run_producer)
        docker_thread = threading.Thread(target=run_docker_processing)
        
        docker_thread.start()
        time.sleep(5)  # Aspetta che il container si avvii
        producer_thread.start()
        
        print("\n✅ Servizi avviati:")
        print("- 🎥 Producer: webcam → Kinesis")
        print("- 🐳 Docker: Kinesis → http://localhost:8080")
        print("- 🌐 Apri http://localhost:8080 nel browser!")
        print("\nPremi Ctrl+C per fermare tutto")
        
        try:
            producer_thread.join()
            docker_thread.join()
        except KeyboardInterrupt:
            print("\n⏹️ Fermando tutti i servizi...")
            subprocess.run(["docker", "stop", "$(docker ps -q --filter ancestor=cv2kinesis:latest)"], shell=True)
            
    elif choice == "4":
        # Tutto insieme con logging
        print("\n🚀 Avvio flusso completo con logging...")
        
        producer_thread = threading.Thread(target=run_producer)
        docker_thread = threading.Thread(target=run_docker_processing)
        consumer_thread = threading.Thread(target=run_consumer_logs)
        
        docker_thread.start()
        time.sleep(5)  # Aspetta che il container si avvii
        producer_thread.start()
        time.sleep(3)  # Aspetta che il producer inizi
        consumer_thread.start()
        
        print("\n✅ Tutti i servizi avviati:")
        print("- 🎥 Producer: webcam → Kinesis")
        print("- 🐳 Docker: Kinesis → http://localhost:8080") 
        print("- 📊 Consumer: logging detection nel terminale")
        print("- 🌐 Apri http://localhost:8080 nel browser!")
        print("\nPremi Ctrl+C per fermare tutto")
        
        try:
            producer_thread.join()
            docker_thread.join()
            consumer_thread.join()
        except KeyboardInterrupt:
            print("\n⏹️ Fermando tutti i servizi...")
            subprocess.run(["docker", "stop", "$(docker ps -q --filter ancestor=cv2kinesis:latest)"], shell=True)
    else:
        print("Scelta non valida")

if __name__ == "__main__":
    main()
