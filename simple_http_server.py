#!/usr/bin/env python3
"""
Server HTTP semplice per servire il frontend dashboard
Include WebSocket mock per demo
"""

import http.server
import socketserver
import json
import webbrowser
import threading
import time
from pathlib import Path

class DashboardHTTPHandler(http.server.SimpleHTTPRequestHandler):
    """Handler HTTP che serve file statici e simula WebSocket"""
    
    def end_headers(self):
        # Aggiungi header CORS per permettere requests locali
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()
    
    def do_OPTIONS(self):
        """Gestisce preflight CORS"""
        self.send_response(200)
        self.end_headers()
    
    def do_POST(self):
        """Gestisce comandi dal frontend"""
        if self.path == '/api/command':
            # Leggi comando
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                command_data = json.loads(post_data.decode('utf-8'))
                command = command_data.get('command', 'unknown')
                
                print(f"📨 Comando ricevuto: {command}")
                
                # Simula risposta
                response = {
                    "success": True,
                    "message": f"Demo: Comando '{command}' eseguito",
                    "timestamp": int(time.time() * 1000)
                }
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode('utf-8'))
                
            except Exception as e:
                print(f"❌ Errore comando: {e}")
                self.send_response(400)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

def start_simple_server(port=8000):
    """Avvia server HTTP semplice"""
    try:
        # Cambia directory di lavoro per servire file
        import os
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        
        with socketserver.TCPServer(("", port), DashboardHTTPHandler) as httpd:
            print(f"[HTTP] Server avviato su porta {port}")
            print(f"[HTTP] Directory: {os.getcwd()}")
            print(f"[HTTP] Dashboard: http://localhost:{port}/frontend_dashboard.html")
            print(f"[HTTP] WebSocket: Avvia simple_websocket_server.py su porta 8080")
            
            # Apri automaticamente nel browser
            url = f"http://localhost:{port}/frontend_dashboard.html"
            threading.Timer(2.0, lambda: webbrowser.open(url)).start()
            
            print("[HTTP] Premi Ctrl+C per fermare...")
            httpd.serve_forever()
            
    except KeyboardInterrupt:
        print("\n[HTTP] Server fermato")
    except Exception as e:
        print(f"[HTTP] Errore server: {e}")

if __name__ == "__main__":
    start_simple_server()
