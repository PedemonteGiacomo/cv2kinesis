#!/usr/bin/env python3
"""
Launcher per Multi-Video Dashboard
Avvia HTTP server (porta 8000) e WebSocket server (porta 8080)
"""

import subprocess
import sys
import time
import webbrowser
import threading
import os

def print_banner():
    print("=" * 60)
    print("🎮 MULTI-VIDEO DASHBOARD LAUNCHER")
    print("=" * 60)
    print()

def check_websockets():
    """Verifica se websockets è installato"""
    try:
        import websockets
        return True
    except ImportError:
        return False

def start_websocket_server():
    """Avvia WebSocket server in subprocess"""
    try:
        print("⚡ Avvio WebSocket server (porta 8080)...")
        
        # Avvia in subprocess
        process = subprocess.Popen(
            [sys.executable, "simple_websocket_server.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Aspetta che si avvii
        time.sleep(2)
        
        if process.poll() is None:  # Still running
            print(f"✅ WebSocket server avviato (PID: {process.pid})")
            return process
        else:
            stdout, stderr = process.communicate()
            print(f"❌ Errore WebSocket server:")
            print(f"STDOUT: {stdout}")
            print(f"STDERR: {stderr}")
            return None
            
    except Exception as e:
        print(f"❌ Errore avvio WebSocket server: {e}")
        return None

def start_http_server():
    """Avvia HTTP server in subprocess"""
    try:
        print("🌐 Avvio HTTP server (porta 8000)...")
        
        # Avvia in subprocess
        process = subprocess.Popen(
            [sys.executable, "simple_http_server.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Aspetta che si avvii
        time.sleep(2)
        
        if process.poll() is None:  # Still running
            print(f"✅ HTTP server avviato (PID: {process.pid})")
            return process
        else:
            stdout, stderr = process.communicate()
            print(f"❌ Errore HTTP server:")
            print(f"STDOUT: {stdout}")
            print(f"STDERR: {stderr}")
            return None
            
    except Exception as e:
        print(f"❌ Errore avvio HTTP server: {e}")
        return None

def open_dashboard():
    """Apri dashboard nel browser"""
    print("🌐 Apertura dashboard...")
    
    # Aspetta che i server si avviino
    time.sleep(3)
    
    dashboard_url = "http://localhost:8000/frontend_dashboard.html"
    
    try:
        webbrowser.open(dashboard_url)
        print(f"✅ Dashboard aperto: {dashboard_url}")
    except Exception as e:
        print(f"❌ Errore apertura browser: {e}")
        print(f"📁 Apri manualmente: {dashboard_url}")

def show_instructions():
    """Mostra istruzioni per l'uso"""
    print("\n" + "=" * 60)
    print("🎯 DASHBOARD MULTI-VIDEO ATTIVO")
    print("=" * 60)
    print()
    print("📊 Dashboard: http://localhost:8000/frontend_dashboard.html")
    print("⚡ WebSocket: ws://localhost:8080")
    print()
    print("🎮 Controlli Dashboard:")
    print("  - 🚀 Avvia Tutti: Inizia tutti e 4 gli stream")
    print("  - 🛑 Ferma Tutti: Ferma tutti gli stream")
    print("  - 🔄 Switch: Cambia sorgente video")
    print("  - ⚙️ Config: Modifica detection settings")
    print()
    print("📺 Stream Disponibili:")
    print("  - 🚗 Traffic: Rilevamento veicoli")
    print("  - 👮 Security: Rilevamento persone")
    print("  - 👥 People: Conteggio persone")
    print("  - ⚽ Sports: Analisi sportiva")
    print()
    print("💡 Modalità Demo:")
    print("  - Dati simulati con SVG frames")
    print("  - Update ogni 3 secondi")
    print("  - Statistiche realistiche")
    print()
    print("⌨️  Premi Ctrl+C per fermare tutti i server")
    print()

def main():
    print_banner()
    
    # Verifica requirements
    if not check_websockets():
        print("❌ websockets non installato")
        print("📦 Installa con: pip install websockets")
        return
    
    print("🔍 Verifica file...")
    required_files = [
        "simple_websocket_server.py",
        "simple_http_server.py", 
        "frontend_dashboard.html"
    ]
    
    for file in required_files:
        if os.path.exists(file):
            print(f"  ✅ {file}")
        else:
            print(f"  ❌ {file}")
            print(f"❌ File mancante: {file}")
            return
    
    print("✅ Tutti i file presenti")
    print()
    
    # Avvia server
    ws_process = start_websocket_server()
    http_process = start_http_server()
    
    if not ws_process or not http_process:
        print("❌ Impossibile avviare i server")
        return
    
    # Apri dashboard in thread separato
    threading.Timer(3.0, open_dashboard).start()
    
    # Mostra istruzioni
    show_instructions()
    
    try:
        # Mantieni attivi i processi
        while True:
            time.sleep(1)
            
            # Verifica se i processi sono ancora attivi
            if ws_process.poll() is not None:
                print("❌ WebSocket server fermato")
                break
                
            if http_process.poll() is not None:
                print("❌ HTTP server fermato")
                break
                
    except KeyboardInterrupt:
        print("\n🛑 Fermando server...")
        
        # Ferma processi
        if ws_process and ws_process.poll() is None:
            ws_process.terminate()
            ws_process.wait()
            print("✅ WebSocket server fermato")
            
        if http_process and http_process.poll() is None:
            http_process.terminate()
            http_process.wait()
            print("✅ HTTP server fermato")
        
        print("👋 Arrivederci!")

if __name__ == "__main__":
    main()
