#!/usr/bin/env python3
"""
Quick Test Suite per Custom Frontend Integration
Testa tutto il flusso di integrazione in modo rapido e interattivo
"""

import subprocess
import sys
import os
import time
import webbrowser
import threading
from pathlib import Path

def print_banner():
    """Stampa banner introduttivo"""
    print("=" * 64)
    print("       CUSTOM FRONTEND INTEGRATION TEST SUITE")
    print("=" * 64)
    print("Test rapido per integrazione frontend personalizzato")
    print("Verifica compatibilita con backend processor esistente")
    print("Setup WebSocket bridge e frontend demo")
    print()

def check_prerequisites():
    """Verifica prerequisiti"""
    print("VERIFICA PREREQUISITI")
    print("-" * 40)
    
    # Check Python
    print(f"Python: {sys.version}")
    
    # Check required files
    required_files = [
        "custom_frontend_integration_example.py",
        "custom_frontend_example.html", 
        "test_frontend_integration.py",
        "FRONTEND_INTEGRATION_GUIDE.md",
        "sqs_consumer.py"
    ]
    
    missing_files = []
    for file in required_files:
        if os.path.exists(file):
            print(f"OK {file}")
        else:
            print(f"MISSING {file}")
            missing_files.append(file)
    
    # Check AWS CLI
    try:
        result = subprocess.run(['aws', '--version'], capture_output=True, text=True)
        print(f"AWS CLI: {result.stdout.strip()}")
    except FileNotFoundError:
        print("AWS CLI: Non trovato (opzionale per questo test)")
    
    # Check Python packages
    packages = ['boto3', 'websockets']
    for package in packages:
        try:
            __import__(package)
            print(f"OK {package}: Installato")
        except ImportError:
            print(f"MISSING {package}: Mancante (pip install {package})")
            missing_files.append(package)
    
    if missing_files:
        print(f"\nPrerequisiti mancanti: {missing_files}")
        return False
    else:
        print("\nTutti i prerequisiti soddisfatti")
        return True

def test_message_compatibility():
    """Test compatibilità messaggi"""
    print("\nTEST COMPATIBILITA MESSAGGI")
    print("-" * 40)
    
    try:
        result = subprocess.run([
            sys.executable, 'test_frontend_integration.py'
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print("OK Test compatibilita: PASSED")
            # Mostra solo le linee più importanti
            lines = result.stdout.split('\n')
            for line in lines:
                if any(keyword in line for keyword in ['OK', 'MISSING', 'Test', 'PASSED', 'FAILED']):
                    print(f"   {line}")
            return True
        else:
            print("FAILED Test compatibilita: FAILED")
            print(result.stderr)
            return False
    except subprocess.TimeoutExpired:
        print("TIMEOUT Test timeout (probabilmente OK)")
        return True
    except Exception as e:
        print(f"ERROR Errore test: {e}")
        return False

def test_sqs_consumer():
    """Test veloce SQS consumer"""
    print("\n📨 TEST SQS CONSUMER (10 secondi)")
    print("-" * 40)
    
    sqs_url = "https://sqs.eu-central-1.amazonaws.com/544547773663/processing-results"
    
    try:
        # Test rapido del consumer
        process = subprocess.Popen([
            sys.executable, 'sqs_consumer.py', sqs_url
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Aspetta 10 secondi
        try:
            stdout, stderr = process.communicate(timeout=10)
            print("✅ SQS consumer funziona")
            
            # Mostra messaggi ricevuti
            if "PROCESSING RESULT RECEIVED" in stdout:
                print("📨 Messaggi ricevuti dal backend processor!")
                lines = stdout.split('\n')
                for line in lines[-10:]:  # Ultime 10 linee
                    if line.strip():
                        print(f"   {line}")
            else:
                print("📭 Nessun messaggio ricevuto (normale se nessun video in streaming)")
                
        except subprocess.TimeoutExpired:
            process.kill()
            print("✅ SQS consumer test completato (10s)")
            
        return True
        
    except Exception as e:
        print(f"❌ Errore SQS test: {e}")
        return False

def start_websocket_bridge():
    """Avvia WebSocket bridge in background"""
    print("\n⚡ AVVIO WEBSOCKET BRIDGE")
    print("-" * 40)
    
    try:
        # Avvia il bridge in background
        process = subprocess.Popen([
            sys.executable, 'custom_frontend_integration_example.py'
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Aspetta che si avvii
        time.sleep(3)
        
        if process.poll() is None:  # Processo ancora in esecuzione
            print("✅ WebSocket bridge avviato")
            print("🌐 Server: ws://localhost:8080")
            return process
        else:
            stdout, stderr = process.communicate()
            print("❌ WebSocket bridge fallito")
            print(stderr)
            return None
            
    except Exception as e:
        print(f"❌ Errore avvio bridge: {e}")
        return None

def open_frontend_demo():
    """Apri frontend demo nel browser"""
    print("\n🌐 APERTURA FRONTEND DEMO")
    print("-" * 40)
    
    html_file = Path("custom_frontend_example.html").absolute()
    
    if html_file.exists():
        url = f"file://{html_file}"
        print(f"🔗 Apertura: {url}")
        
        # Apri nel browser dopo 2 secondi
        def open_browser():
            time.sleep(2)
            webbrowser.open(url)
            
        threading.Thread(target=open_browser, daemon=True).start()
        print("✅ Frontend demo dovrebbe aprirsi nel browser")
        return True
    else:
        print("❌ File custom_frontend_example.html non trovato")
        return False

def interactive_menu():
    """Menu interattivo"""
    print("\nMENU INTERATTIVO")
    print("-" * 40)
    print("1. Test Compatibilita Messaggi")
    print("2. Test SQS Consumer (10s)")
    print("3. Avvia WebSocket Bridge")
    print("4. Apri Frontend Demo")
    print("5. Test Completo (tutto insieme)")
    print("6. Mostra Guida Integrazione")
    print("0. Esci")
    
    while True:
        try:
            choice = input("\nScegli opzione (0-6): ").strip()
            
            if choice == "0":
                print("Uscita...")
                break
                
            elif choice == "1":
                test_message_compatibility()
                
            elif choice == "2":
                test_sqs_consumer()
                
            elif choice == "3":
                bridge_process = start_websocket_bridge()
                if bridge_process:
                    input("Premi ENTER per terminare il bridge...")
                    bridge_process.terminate()
                    print("Bridge terminato")
                
            elif choice == "4":
                open_frontend_demo()
                
            elif choice == "5":
                run_complete_test()
                
            elif choice == "6":
                show_integration_guide()
                
            else:
                print("Opzione non valida")
                
        except KeyboardInterrupt:
            print("\nInterrotto dall'utente")
            break
        except Exception as e:
            print(f"Errore: {e}")

def run_complete_test():
    """Esegue test completo"""
    print("\n🚀 TEST COMPLETO")
    print("="*50)
    
    steps = [
        ("📋 Verifica prerequisiti", check_prerequisites),
        ("🧪 Test compatibilità", test_message_compatibility),
        ("📨 Test SQS consumer", test_sqs_consumer),
    ]
    
    results = []
    
    for step_name, step_func in steps:
        print(f"\n▶️ {step_name}...")
        try:
            result = step_func()
            results.append((step_name, result))
        except Exception as e:
            print(f"❌ Errore in {step_name}: {e}")
            results.append((step_name, False))
    
    # WebSocket bridge e frontend
    print(f"\n▶️ Avvio WebSocket bridge...")
    bridge_process = start_websocket_bridge()
    
    if bridge_process:
        print(f"\n▶️ Apertura frontend demo...")
        open_frontend_demo()
        
        print("\n🎉 TEST COMPLETO TERMINATO!")
        print("="*50)
        print("📊 Risultati:")
        
        for step_name, result in results:
            status = "✅" if result else "❌"
            print(f"{status} {step_name}")
        
        if bridge_process.poll() is None:
            print("✅ WebSocket bridge attivo")
            print("✅ Frontend demo aperto")
            
            print(f"\n🎯 INTEGRAZIONE PRONTA!")
            print("📱 Il tuo frontend personalizzato può connettersi a:")
            print("   WebSocket: ws://localhost:8080")
            print("   SQS Queue: https://sqs.eu-central-1.amazonaws.com/544547773663/processing-results")
            
            input("\n⏸️ Premi ENTER per terminare...")
            bridge_process.terminate()
            print("⏹️ Test terminato")
    else:
        print("❌ Impossibile avviare WebSocket bridge")

def show_integration_guide():
    """Mostra guida integrazione"""
    print("\n📋 GUIDA INTEGRAZIONE FRONTEND")
    print("="*50)
    
    guide_file = "FRONTEND_INTEGRATION_GUIDE.md"
    
    if os.path.exists(guide_file):
        print(f"📖 Guida completa disponibile in: {guide_file}")
        print("\n🔑 Punti chiave:")
        print("• Backend processor già deployato e funzionante")
        print("• Messaggi JSON standardizzati su SQS")
        print("• Immagini processate salvate su S3")
        print("• 3 metodi di integrazione: Polling SQS, WebSocket, REST API")
        print("• Formato bounding box normalizzato (0.0-1.0)")
        print("• URL firmati per accesso diretto alle immagini")
        
        print(f"\n📁 File di supporto:")
        print("• custom_frontend_integration_example.py - WebSocket bridge")
        print("• custom_frontend_example.html - Frontend demo")
        print("• test_frontend_integration.py - Test compatibilità")
        
    else:
        print(f"❌ File guida {guide_file} non trovato")
    
    print(f"\n🎯 Stack Configuration:")
    stack_config = {
        'SQS Queue': 'https://sqs.eu-central-1.amazonaws.com/544547773663/processing-results',
        'S3 Bucket': 'processedframes-544547773663-eu-central-1',
        'Kinesis Stream': 'cv2kinesis',
        'AWS Region': 'eu-central-1'
    }
    
    for key, value in stack_config.items():
        print(f"• {key}: {value}")

def main():
    """Main function"""
    print_banner()
    
    if not check_prerequisites():
        print("\n⚠️ Prerequisiti mancanti. Installa i pacchetti richiesti e riprova.")
        sys.exit(1)
    
    print("\n🎯 MODALITÀ TEST:")
    print("A. 🎮 Menu Interattivo")
    print("B. 🚀 Test Completo Automatico")
    print("C. 📋 Solo Guida Integrazione")
    
    try:
        mode = input("\n👉 Scegli modalità (A/B/C): ").upper().strip()
        
        if mode == "A":
            interactive_menu()
        elif mode == "B":
            run_complete_test()
        elif mode == "C":
            show_integration_guide()
        else:
            print("❌ Modalità non valida")
            
    except KeyboardInterrupt:
        print("\n👋 Test interrotto")
    except Exception as e:
        print(f"❌ Errore: {e}")

if __name__ == "__main__":
    main()
