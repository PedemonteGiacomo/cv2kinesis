#!/usr/bin/env python3
"""
Server Ibrido HTTP + WebSocket per Multi-Video Dashboard
Serve file statici e gestisce WebSocket connections
"""

import asyncio
import json
import logging
import threading
import time
import webbrowser
from pathlib import Path
from typing import Set, Dict, Any
import os

# Import websockets con fallback
try:
    import websockets
    from websockets.asyncio.server import serve
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    print("❌ websockets non disponibile. Installa con: pip install websockets")
    WEBSOCKETS_AVAILABLE = False

# Import aiohttp per HTTP server
try:
    import aiohttp
    from aiohttp import web
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class HybridDashboardServer:
    """
    Server ibrido che gestisce sia HTTP che WebSocket
    """
    
    def __init__(self, host="localhost", http_port=8000, ws_port=8080):
        self.host = host
        self.http_port = http_port
        self.ws_port = ws_port
        self.connected_clients: Set = set()
        
        # Demo data
        self.demo_mode = True
        self.demo_running = False
        
    async def websocket_handler(self, websocket, path):
        """Handler per connessioni WebSocket"""
        await self.register_client(websocket)
        
        try:
            async for message in websocket:
                await self.handle_client_message(websocket, message)
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logger.error(f"❌ Errore WebSocket handler: {e}")
        finally:
            await self.unregister_client(websocket)
    
    async def register_client(self, websocket):
        """Registra nuovo client WebSocket"""
        self.connected_clients.add(websocket)
        client_count = len(self.connected_clients)
        logger.info(f"✅ Nuovo client WebSocket connesso (totale: {client_count})")
        
        # Invia stato iniziale
        await self.send_initial_status(websocket)
        
        # Avvia simulatore se primo client
        if client_count == 1 and not self.demo_running:
            self.start_demo_simulator()
    
    async def unregister_client(self, websocket):
        """Rimuovi client disconnesso"""
        self.connected_clients.discard(websocket)
        client_count = len(self.connected_clients)
        logger.info(f"❌ Client WebSocket disconnesso (totale: {client_count})")
    
    async def send_initial_status(self, websocket):
        """Invia stato iniziale al client"""
        try:
            await websocket.send(json.dumps({
                "type": "initial_status",
                "data": {
                    "traffic": {"active": True},
                    "security": {"active": True},
                    "people": {"active": True},
                    "sports": {"active": True}
                }
            }))
        except Exception as e:
            logger.error(f"❌ Errore invio status iniziale: {e}")
    
    async def handle_client_message(self, websocket, message_str: str):
        """Gestisce messaggi dal client WebSocket"""
        try:
            message = json.loads(message_str)
            command = message.get('command')
            
            logger.info(f"📨 Comando WebSocket ricevuto: {command}")
            
            # Echo comando a tutti i client
            await self.broadcast_message({
                "type": "command_response",
                "command": command,
                "success": True,
                "message": f"Demo: Comando '{command}' eseguito",
                "params": message
            })
            
        except json.JSONDecodeError:
            logger.error("❌ Messaggio JSON non valido")
        except Exception as e:
            logger.error(f"❌ Errore gestione messaggio: {e}")
    
    async def broadcast_message(self, message: dict):
        """Invia messaggio a tutti i client WebSocket connessi"""
        if not self.connected_clients:
            return
        
        message_str = json.dumps(message)
        disconnected_clients = set()
        
        for client in self.connected_clients.copy():
            try:
                await client.send(message_str)
            except websockets.exceptions.ConnectionClosed:
                disconnected_clients.add(client)
            except Exception as e:
                logger.error(f"❌ Errore invio a client: {e}")
                disconnected_clients.add(client)
        
        # Rimuovi client disconnessi
        for client in disconnected_clients:
            await self.unregister_client(client)
    
    def start_demo_simulator(self):
        """Avvia simulatore dati demo"""
        if self.demo_running:
            return
            
        self.demo_running = True
        
        def simulate():
            import random
            streams = ['traffic', 'security', 'people', 'sports']
            
            logger.info("🎭 Simulatore demo avviato")
            
            while self.demo_running and self.connected_clients:
                try:
                    for stream_name in streams:
                        # Simula detection data
                        detection_data = {
                            "stream_name": stream_name,
                            "object_count": random.randint(1, 15),
                            "avg_confidence": random.randint(60, 95),
                            "fps": random.randint(8, 20),
                            "timestamp": int(time.time() * 1000),
                            "frame_url": f"data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMzIwIiBoZWlnaHQ9IjI0MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KICA8cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjMzMzIi8+CiAgPHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PSJBcmlhbCwgc2Fucy1zZXJpZiIgZm9udC1zaXplPSIxOCIgZmlsbD0iI2ZmZiIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPnt0aXRsZX0gU3RyZWFtPC90ZXh0Pgo8L3N2Zz4="
                        }
                        
                        # Replace {title} con nome stream
                        svg_data = detection_data["frame_url"].replace("{title}", stream_name.title())
                        detection_data["frame_url"] = svg_data
                        
                        # Invia update (thread-safe)
                        if self.connected_clients:
                            asyncio.run_coroutine_threadsafe(
                                self.broadcast_message({
                                    "type": "detection_update", 
                                    "data": detection_data
                                }),
                                self.loop
                            )
                    
                    time.sleep(3)  # Update ogni 3 secondi
                    
                except Exception as e:
                    logger.error(f"❌ Errore simulatore: {e}")
                    time.sleep(5)
            
            logger.info("🎭 Simulatore demo fermato")
            self.demo_running = False
        
        thread = threading.Thread(target=simulate, daemon=True)
        thread.start()
    
    # HTTP Handlers (se aiohttp disponibile)
    async def http_index(self, request):
        """Serve il file HTML principale"""
        try:
            with open('frontend_dashboard.html', 'r', encoding='utf-8') as f:
                content = f.read()
            return web.Response(text=content, content_type='text/html')
        except FileNotFoundError:
            return web.Response(text="Frontend dashboard non trovato", status=404)
    
    async def http_command(self, request):
        """Gestisce comandi HTTP"""
        try:
            data = await request.json()
            command = data.get('command', 'unknown')
            
            logger.info(f"📨 Comando HTTP ricevuto: {command}")
            
            # Invia anche ai client WebSocket
            await self.broadcast_message({
                "type": "command_response",
                "command": command,
                "success": True,
                "message": f"HTTP: Comando '{command}' eseguito",
                "params": data
            })
            
            return web.json_response({
                "success": True,
                "message": f"Comando '{command}' eseguito",
                "timestamp": int(time.time() * 1000)
            })
            
        except Exception as e:
            logger.error(f"❌ Errore comando HTTP: {e}")
            return web.json_response({"error": str(e)}, status=400)
    
    async def start_servers(self):
        """Avvia entrambi i server"""
        self.loop = asyncio.get_event_loop()
        
        tasks = []
        
        # 1. Avvia WebSocket server
        if WEBSOCKETS_AVAILABLE:
            logger.info(f"🚀 Avvio WebSocket server su ws://{self.host}:{self.ws_port}")
            
            ws_server = await serve(
                self.websocket_handler,
                self.host,
                self.ws_port
            )
            tasks.append(ws_server.wait_closed())
            
            logger.info(f"✅ WebSocket server avviato su porta {self.ws_port}")
        
        # 2. Avvia HTTP server 
        if AIOHTTP_AVAILABLE:
            app = web.Application()
            app.router.add_get('/', self.http_index)
            app.router.add_get('/frontend_dashboard.html', self.http_index)
            app.router.add_post('/api/command', self.http_command)
            
            # Serve file statici
            app.router.add_static('/', '.', show_index=True)
            
            runner = web.AppRunner(app)
            await runner.setup()
            
            site = web.TCPSite(runner, self.host, self.http_port)
            await site.start()
            
            logger.info(f"✅ HTTP server avviato su http://{self.host}:{self.http_port}")
            
            # Apri browser automaticamente
            url = f"http://{self.host}:{self.http_port}/frontend_dashboard.html"
            threading.Timer(2.0, lambda: webbrowser.open(url)).start()
            logger.info(f"🌐 Apertura automatica: {url}")
        
        else:
            # Fallback: solo istruzioni
            logger.warning("⚠️ aiohttp non disponibile, solo WebSocket attivo")
            logger.info("📁 Apri manualmente: frontend_dashboard.html")
        
        # Mantieni server attivi
        if tasks:
            await asyncio.gather(*tasks)
        else:
            await asyncio.Future()  # Run forever

# Server semplificato senza aiohttp
class SimpleHybridServer:
    """Versione semplificata usando solo librerie standard"""
    
    def __init__(self, port=8000):
        self.port = port
        
    async def start(self):
        """Avvia server semplificato"""
        logger.info("🚀 Avvio server semplificato...")
        
        # Avvia WebSocket se disponibile
        if WEBSOCKETS_AVAILABLE:
            server = HybridDashboardServer()
            await server.start_servers()
        else:
            logger.error("❌ WebSocket non disponibile")
            
            # Fallback: server HTTP basic
            import http.server
            import socketserver
            
            class Handler(http.server.SimpleHTTPRequestHandler):
                def end_headers(self):
                    self.send_header('Access-Control-Allow-Origin', '*')
                    super().end_headers()
            
            with socketserver.TCPServer(('', self.port), Handler) as httpd:
                logger.info(f"📁 Server HTTP basic su porta {self.port}")
                webbrowser.open(f"http://localhost:{self.port}/frontend_dashboard.html")
                httpd.serve_forever()

async def main():
    """Main function"""
    if not WEBSOCKETS_AVAILABLE:
        print("❌ websockets non installato")
        print("📦 Installa con: pip install websockets")
        print("📦 Opzionale: pip install aiohttp (per HTTP server)")
        return
    
    try:
        server = HybridDashboardServer()
        await server.start_servers()
        
    except KeyboardInterrupt:
        logger.info("👋 Server fermato dall'utente")
    except Exception as e:
        logger.error(f"❌ Errore server: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Arrivederci!")
