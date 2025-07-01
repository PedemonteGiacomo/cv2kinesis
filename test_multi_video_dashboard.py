#!/usr/bin/env python3
"""
Test Multi-Video Dashboard
Script per testare il funzionamento completo del sistema multi-video
"""

import os
import sys
import time
import subprocess
import webbrowser
from pathlib import Path

def print_banner():
    print("=" * 60)
    print("🎮 MULTI-VIDEO DASHBOARD TEST")
    print("=" * 60)
    print()

def check_requirements():
    """Verifica requirements per il test"""
    print("🔍 Verifica requirements...")
    
    # Check Python packages
    required_packages = [
        ('websockets', 'websockets'),
        ('opencv-python', 'cv2'), 
        ('boto3', 'boto3')
    ]
    missing_packages = []
    
    for package_name, import_name in required_packages:
        try:
            __import__(import_name)
            print(f"  ✅ {package_name}")
        except ImportError:
            missing_packages.append(package_name)
            print(f"  ❌ {package_name}")
    
    if missing_packages:
        print(f"\n⚠️  Pacchetti mancanti: {', '.join(missing_packages)}")
        print("📦 Installa con: pip install " + " ".join(missing_packages))
        return False
    
    # Check files
    required_files = [
        'frontend_dashboard.html',
        'websocket_server.py',
        'multi_stream_controller.py'
    ]
    
    for file in required_files:
        if os.path.exists(file):
            print(f"  ✅ {file}")
        else:
            print(f"  ❌ {file}")
            return False
    
    print("✅ Tutti i requirements soddisfatti")
    return True

def create_demo_videos_info():
    """Crea info sui video demo necessari"""
    demo_dir = "demo_videos"
    
    print(f"\n📁 Directory video demo: {demo_dir}")
    
    if not os.path.exists(demo_dir):
        print(f"📁 Creando directory: {demo_dir}")
        os.makedirs(demo_dir)
    
    demo_videos = [
        "traffic.mp4",
        "security.mp4", 
        "people.mp4",
        "sports.mp4"
    ]
    
    print("\n📹 Video demo necessari:")
    for video in demo_videos:
        video_path = os.path.join(demo_dir, video)
        if os.path.exists(video_path):
            print(f"  ✅ {video}")
        else:
            print(f"  ❌ {video} (mancante)")
    
    print("\n💡 Per demo senza video reali:")
    print("   - Il sistema funziona comunque con webcam")
    print("   - Usa opzione 'webcam' nel frontend")
    print("   - Video demo opzionali per test completo")

def start_websocket_server():
    """Avvia server WebSocket"""
    print("\n🚀 Avvio WebSocket server...")
    
    try:
        # Avvia server in subprocess
        process = subprocess.Popen(
            [sys.executable, "websocket_server.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Aspetta che server si avvii
        time.sleep(3)
        
        if process.poll() is None:  # Still running
            print("✅ WebSocket server avviato (PID: {})".format(process.pid))
            return process
        else:
            stdout, stderr = process.communicate()
            print(f"❌ Errore avvio server:")
            print(f"STDOUT: {stdout}")
            print(f"STDERR: {stderr}")
            return None
            
    except Exception as e:
        print(f"❌ Errore avvio WebSocket server: {e}")
        return None

def open_frontend():
    """Apri frontend nel browser"""
    print("\n🌐 Apertura frontend dashboard...")
    
    frontend_path = os.path.abspath("frontend_dashboard.html")
    frontend_url = f"file://{frontend_path}"
    
    try:
        webbrowser.open(frontend_url)
        print(f"✅ Frontend aperto: {frontend_url}")
        return True
    except Exception as e:
        print(f"❌ Errore apertura frontend: {e}")
        print(f"📁 Apri manualmente: {frontend_path}")
        return False

def show_demo_instructions():
    """Mostra istruzioni per la demo"""
    print("\n" + "=" * 60)
    print("🎯 ISTRUZIONI PER DEMO MULTI-VIDEO")
    print("=" * 60)
    print()
    print("1. 🌐 Frontend Dashboard:")
    print("   - 4 card per stream diversi (Traffic, Security, People, Sports)")
    print("   - Controlli individuali per ogni stream")
    print("   - Switch sorgente video in tempo reale")
    print("   - Configurazione detection per stream")
    print()
    print("2. 🎮 Controlli Disponibili:")
    print("   - 🚀 Avvia Tutti: Inizia tutti e 4 gli stream")
    print("   - 🛑 Ferma Tutti: Ferma tutti gli stream")
    print("   - 🔄 Switch: Cambia sorgente (video → webcam)")
    print("   - ⚙️ Config: Modifica classi detection e FPS")
    print()
    print("3. 📊 Visualizzazione Live:")
    print("   - Conteggio oggetti rilevati per stream")
    print("   - Confidenza media detection")
    print("   - FPS processing in tempo reale")
    print("   - Status connessione WebSocket")
    print()
    print("4. 🧪 Test Scenario:")
    print("   - Avvia con video demo o webcam")
    print("   - Cambia sorgente su card diverse")
    print("   - Configura detection personalizzate")
    print("   - Osserva aggiornamenti live")
    print()
    print("5. 🔧 Architettura Supportata:")
    print("   - ✅ 4 stream Kinesis paralleli")
    print("   - ✅ ECS auto-scaling per carico")
    print("   - ✅ S3 organizzato per stream")
    print("   - ✅ SQS con tagging per stream")
    print("   - ✅ WebSocket real-time")
    print()

def show_production_steps():
    """Mostra step per implementazione production"""
    print("\n" + "=" * 60)
    print("🚀 STEP PER IMPLEMENTAZIONE PRODUCTION")
    print("=" * 60)
    print()
    print("1. 📡 Estendi CDK Stack:")
    print("   ```python")
    print("   # In pipeline_stack.py")
    print("   streams = ['traffic', 'security', 'people', 'sports']")
    print("   for stream in streams:")
    print("       kinesis.Stream(self, f'{stream}Stream', ...)")
    print("   ```")
    print()
    print("2. 🎯 Deploy Multi-Producer:")
    print("   ```bash")
    print("   python multi_stream_controller.py")
    print("   # Configura 4 stream paralleli")
    print("   ```")
    print()
    print("3. 🌐 Setup Frontend Production:")
    print("   - Host su S3 + CloudFront")
    print("   - WebSocket tramite API Gateway")
    print("   - Autenticazione Cognito")
    print("   - Real-time updates via WebSocket")
    print()
    print("4. 📊 Monitoring & Analytics:")
    print("   - CloudWatch per metriche stream")
    print("   - Dashboard X-Ray per tracing")
    print("   - Allarmi su soglie detection")
    print("   - Analytics su pattern rilevamento")
    print()

def main():
    print_banner()
    
    # Check requirements
    if not check_requirements():
        print("\n❌ Test interrotto per requirements mancanti")
        return
    
    # Create demo videos info
    create_demo_videos_info()
    
    print("\n🎯 Scegli modalità test:")
    print("1. 🎭 Demo Dashboard (solo frontend + WebSocket)")
    print("2. 🧪 Test Completo (con MultiStreamController)")
    print("3. 📖 Solo documentazione")
    print("0. ❌ Esci")
    
    choice = input("\n👉 Scelta: ").strip()
    
    if choice == '0':
        print("👋 Arrivederci!")
        return
    
    elif choice == '3':
        show_demo_instructions()
        show_production_steps()
        return
    
    elif choice in ['1', '2']:
        # Avvia WebSocket server
        server_process = start_websocket_server()
        
        if not server_process:
            print("❌ Impossibile avviare WebSocket server")
            return
        
        # Apri frontend
        if not open_frontend():
            print("⚠️ Frontend non aperto automaticamente")
        
        # Mostra istruzioni
        show_demo_instructions()
        
        if choice == '2':
            print("\n🔧 Per test completo:")
            print("   1. Apri altro terminale")
            print("   2. Esegui: python multi_stream_controller.py")
            print("   3. Collega controller al WebSocket server")
        
        try:
            print(f"\n⏳ Server attivo (PID: {server_process.pid})")
            print("⌨️  Premi Ctrl+C per fermare...")
            
            # Mantieni attivo
            server_process.wait()
            
        except KeyboardInterrupt:
            print("\n🛑 Fermando server...")
            server_process.terminate()
            server_process.wait()
            print("✅ Server fermato")
    
    else:
        print("❌ Opzione non valida")

if __name__ == "__main__":
    main()
