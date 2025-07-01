#!/usr/bin/env python3
"""
Launcher semplificato per Multi-Video Dashboard
Senza emoji per compatibilità Windows
"""

import subprocess
import sys
import time
import webbrowser
import threading
import os

def main():
    print("=" * 60)
    print("MULTI-VIDEO DASHBOARD LAUNCHER")
    print("=" * 60)
    print()
    
    # Verifica file
    print("Verifica file...")
    files = ['simple_http_server.py', 'frontend_dashboard.html']
    
    for file in files:
        if os.path.exists(file):
            print(f"  [OK] {file}")
        else:
            print(f"  [MISSING] {file}")
            print("[ERROR] File mancanti")
            return
    
    print("[OK] Tutti i file presenti")
    print()
    
    # Avvia solo HTTP server (più semplice)
    print("Avvio HTTP server...")
    try:
        # Usa subprocess per avviare in background
        process = subprocess.Popen(
            [sys.executable, "simple_http_server.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        
        print(f"[OK] Server avviato (PID: {process.pid})")
        print("[INFO] Dashboard: http://localhost:8000/frontend_dashboard.html")
        print()
        print("Il browser si aprirà automaticamente...")
        print("Premi Ctrl+C per fermare")
        print()
        
        # Apri browser dopo 3 secondi
        threading.Timer(3.0, lambda: webbrowser.open("http://localhost:8000/frontend_dashboard.html")).start()
        
        # Aspetta che il processo termini
        process.wait()
        
    except KeyboardInterrupt:
        print("\n[INFO] Fermando server...")
        process.terminate()
        process.wait()
        print("[INFO] Server fermato")
        
    except Exception as e:
        print(f"[ERROR] Errore: {e}")

if __name__ == "__main__":
    main()
