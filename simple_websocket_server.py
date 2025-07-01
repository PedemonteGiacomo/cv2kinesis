#!/usr/bin/env python3
"""
Server WebSocket Semplice per Multi-Video Dashboard
Solo WebSocket senza HTTP server
"""

import asyncio
import json
import logging
import threading
import time
import base64
from typing import Set

# Import websockets con fallback
try:
    import websockets
    from websockets.asyncio.server import serve
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    print("❌ websockets non disponibile. Installa con: pip install websockets")
    WEBSOCKETS_AVAILABLE = False

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SimpleWebSocketServer:
    """Server WebSocket semplice per la dashboard"""
    
    def __init__(self, host="localhost", port=8080):
        self.host = host
        self.port = port
        self.connected_clients: Set = set()
        self.demo_running = False
        self.loop = None
        
    async def websocket_handler(self, websocket):
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
        logger.info(f"✅ Client connesso (totale: {client_count})")
        
        # Invia stato iniziale
        await self.send_initial_status(websocket)
        
        # Avvia simulatore se primo client
        if client_count == 1 and not self.demo_running:
            self.start_demo_simulator()
    
    async def unregister_client(self, websocket):
        """Rimuovi client disconnesso"""
        self.connected_clients.discard(websocket)
        client_count = len(self.connected_clients)
        logger.info(f"❌ Client disconnesso (totale: {client_count})")
        
        # Ferma simulatore se nessun client
        if client_count == 0:
            self.demo_running = False
    
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
            logger.info("📊 Status iniziale inviato al client")
        except Exception as e:
            logger.error(f"❌ Errore invio status iniziale: {e}")
    
    async def handle_client_message(self, websocket, message_str: str):
        """Gestisce messaggi dal client WebSocket"""
        try:
            message = json.loads(message_str)
            command = message.get('command')
            
            logger.info(f"📨 Comando ricevuto: {command}")
            
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
            self.connected_clients.discard(client)
    
    def create_demo_frame(self, stream_name: str, object_count: int) -> str:
        """Crea frame SVG demo per lo stream"""
        # Colori per ogni stream
        colors = {
            'traffic': '#ff6b6b',
            'security': '#4ecdc4', 
            'people': '#45b7d1',
            'sports': '#f9ca24'
        }
        
        # Emoji per ogni stream
        emojis = {
            'traffic': '🚗',
            'security': '👮',
            'people': '👥', 
            'sports': '⚽'
        }
        
        color = colors.get(stream_name, '#666')
        emoji = emojis.get(stream_name, '📹')
        
        # Crea SVG
        svg = f'''<svg width="320" height="240" xmlns="http://www.w3.org/2000/svg">
            <defs>
                <linearGradient id="grad{stream_name}" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style="stop-color:{color};stop-opacity:0.3" />
                    <stop offset="100%" style="stop-color:{color};stop-opacity:0.1" />
                </linearGradient>
            </defs>
            <rect width="100%" height="100%" fill="url(#grad{stream_name})"/>
            <rect x="0" y="0" width="100%" height="100%" fill="none" stroke="{color}" stroke-width="2"/>
            
            <text x="50%" y="30%" font-family="Arial, sans-serif" font-size="24" fill="{color}" text-anchor="middle" font-weight="bold">
                {emoji} {stream_name.title()} Stream
            </text>
            
            <text x="50%" y="50%" font-family="Arial, sans-serif" font-size="18" fill="{color}" text-anchor="middle">
                {object_count} oggetti rilevati
            </text>
            
            <text x="50%" y="70%" font-family="Arial, sans-serif" font-size="14" fill="{color}" text-anchor="middle" opacity="0.7">
                Demo Mode - Live Processing
            </text>
            
            <circle cx="30" cy="30" r="8" fill="{color}" opacity="0.8">
                <animate attributeName="opacity" values="0.3;1;0.3" dur="2s" repeatCount="indefinite"/>
            </circle>
        </svg>'''
        
        # Encode in base64
        svg_bytes = svg.encode('utf-8')
        svg_b64 = base64.b64encode(svg_bytes).decode('utf-8')
        return f"data:image/svg+xml;base64,{svg_b64}"
    
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
                        if not self.demo_running:
                            break
                            
                        # Simula detection data
                        object_count = random.randint(1, 15)
                        detection_data = {
                            "stream_name": stream_name,
                            "object_count": object_count,
                            "avg_confidence": random.randint(60, 95),
                            "fps": random.randint(8, 20),
                            "timestamp": int(time.time() * 1000),
                            "frame_url": self.create_demo_frame(stream_name, object_count)
                        }
                        
                        # Invia update (thread-safe)
                        if self.connected_clients and self.loop:
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
    
    async def start_server(self):
        """Avvia il server WebSocket"""
        if not WEBSOCKETS_AVAILABLE:
            logger.error("❌ WebSocket non disponibile")
            return
            
        self.loop = asyncio.get_event_loop()
        
        logger.info(f"🚀 Avvio WebSocket server su ws://{self.host}:{self.port}")
        
        async with serve(self.websocket_handler, self.host, self.port):
            logger.info(f"✅ Server WebSocket avviato!")
            logger.info(f"🌐 Apri: file:///path/to/frontend_dashboard.html")
            logger.info(f"📁 O usa server HTTP su porta diversa")
            
            # Mantieni server attivo
            await asyncio.Future()  # Run forever

async def main():
    """Main function"""
    if not WEBSOCKETS_AVAILABLE:
        print("❌ websockets non installato")
        print("📦 Installa con: pip install websockets")
        return
    
    try:
        server = SimpleWebSocketServer()
        await server.start_server()
        
    except KeyboardInterrupt:
        logger.info("👋 Server fermato dall'utente")
    except Exception as e:
        logger.error(f"❌ Errore server: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Arrivederci!")
