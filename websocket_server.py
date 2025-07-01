#!/usr/bin/env python3
"""
WebSocket Server per Dashboard Multi-Video
Collega frontend dashboard con multi-stream controller
"""

import asyncio
import json
import logging
import threading
import time
from datetime import datetime
from typing import Set, Dict, Any

# Import websockets con fallback
try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    print("⚠️ websockets non disponibile")

# Import demo simulator
try:
    from demo_video_simulator import DemoVideoSimulator
    SIMULATOR_AVAILABLE = True
except ImportError:
    SIMULATOR_AVAILABLE = False
    print("⚠️ Demo video simulator non disponibile")
try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    print("❌ websockets non disponibile. Installa con: pip install websockets")
    WEBSOCKETS_AVAILABLE = False

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DashboardWebSocketServer:
    """
    Server WebSocket per comunicazione real-time con frontend dashboard
    """
    
    def __init__(self, host="localhost", port=8080):
        self.host = host
        self.port = port
        self.connected_clients: Set[websockets.WebSocketServerProtocol] = set()
        self.stream_controller = None  # Riferimento al MultiStreamController
        
        # Demo video simulator
        self.demo_simulator = None
        if SIMULATOR_AVAILABLE:
            self.demo_simulator = DemoVideoSimulator(self)
        
        # Demo data per testing senza controller reale
        self.demo_mode = True
        self.demo_data = {
            "traffic": {"objects": 0, "confidence": 0, "fps": 0},
            "security": {"objects": 0, "confidence": 0, "fps": 0},
            "people": {"objects": 0, "confidence": 0, "fps": 0},
            "sports": {"objects": 0, "confidence": 0, "fps": 0}
        }
    
    def set_stream_controller(self, controller):
        """Collega il MultiStreamController"""
        self.stream_controller = controller
        self.demo_mode = False
        logger.info("✅ MultiStreamController collegato")
    
    async def register_client(self, websocket):
        """Registra nuovo client"""
        self.connected_clients.add(websocket)
        client_count = len(self.connected_clients)
        logger.info(f"✅ Nuovo client connesso (totale: {client_count})")
        
        # Invia stato iniziale
        await self.send_initial_status(websocket)
    
    async def unregister_client(self, websocket):
        """Rimuovi client disconnesso"""
        self.connected_clients.discard(websocket)
        client_count = len(self.connected_clients)
        logger.info(f"❌ Client disconnesso (totale: {client_count})")
    
    async def send_initial_status(self, websocket):
        """Invia stato iniziale al client"""
        try:
            if self.stream_controller:
                status = self.stream_controller.get_status()
                await websocket.send(json.dumps({
                    "type": "initial_status",
                    "data": status
                }))
            else:
                # Demo status
                await websocket.send(json.dumps({
                    "type": "initial_status", 
                    "data": {
                        "traffic": {"active": False},
                        "security": {"active": False},
                        "people": {"active": False},
                        "sports": {"active": False}
                    }
                }))
        except Exception as e:
            logger.error(f"❌ Errore invio status iniziale: {e}")
    
    async def broadcast_message(self, message: dict):
        """Invia messaggio a tutti i client connessi"""
        if not self.connected_clients:
            return
        
        message_str = json.dumps(message)
        disconnected_clients = set()
        
        for client in self.connected_clients:
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
    
    async def handle_client_message(self, websocket, message_str: str):
        """Gestisce messaggi dal client"""
        try:
            message = json.loads(message_str)
            command = message.get('command')
            
            logger.info(f"📨 Comando ricevuto: {command}")
            
            if command == 'start_all_streams':
                await self.handle_start_all_streams()
            
            elif command == 'stop_all_streams':
                await self.handle_stop_all_streams()
            
            elif command == 'switch_source':
                stream_name = message.get('stream_name')
                new_source = message.get('new_source')
                await self.handle_switch_source(stream_name, new_source)
            
            elif command == 'update_config':
                stream_name = message.get('stream_name')
                config = {k: v for k, v in message.items() if k not in ['command', 'stream_name']}
                await self.handle_update_config(stream_name, config)
            
            elif command == 'get_status':
                await self.handle_get_status()
            
            else:
                logger.warning(f"⚠️ Comando sconosciuto: {command}")
                
        except json.JSONDecodeError:
            logger.error("❌ Messaggio JSON non valido")
        except Exception as e:
            logger.error(f"❌ Errore gestione messaggio: {e}")
    
    async def handle_start_all_streams(self):
        """Avvia tutti gli stream"""
        if self.stream_controller:
            # Esegui in thread separato per non bloccare
            threading.Thread(target=self.stream_controller.start_all_streams).start()
            
            await self.broadcast_message({
                "type": "command_response",
                "command": "start_all_streams",
                "success": True,
                "message": "Avvio tutti gli stream..."
            })
        else:
            # Demo mode con video simulator
            if self.demo_simulator:
                asyncio.create_task(self.demo_simulator.start_simulation())
                
            await self.broadcast_message({
                "type": "command_response", 
                "command": "start_all_streams",
                "success": True,
                "message": "Demo: Video simulation avviata"
            })
    
    async def handle_stop_all_streams(self):
        """Ferma tutti gli stream"""
        if self.stream_controller:
            threading.Thread(target=self.stream_controller.stop_all_streams).start()
            
            await self.broadcast_message({
                "type": "command_response",
                "command": "stop_all_streams", 
                "success": True,
                "message": "Fermando tutti gli stream..."
            })
        else:
            # Demo mode con video simulator
            if self.demo_simulator:
                self.demo_simulator.stop_simulation()
                
            await self.broadcast_message({
                "type": "command_response",
                "command": "stop_all_streams",
                "success": True,
                "message": "Demo: Video simulation fermata"
            })
    
    async def handle_switch_source(self, stream_name: str, new_source: str):
        """Cambia sorgente stream"""
        if self.stream_controller:
            success = self.stream_controller.switch_source(stream_name, new_source)
            
            await self.broadcast_message({
                "type": "source_switched",
                "stream_name": stream_name,
                "new_source": new_source,
                "success": success
            })
        else:
            # Demo mode
            await self.broadcast_message({
                "type": "source_switched",
                "stream_name": stream_name,
                "new_source": new_source,
                "success": True
            })
    
    async def handle_update_config(self, stream_name: str, config: dict):
        """Aggiorna configurazione stream"""
        if self.stream_controller:
            success = self.stream_controller.update_config(stream_name, **config)
            
            await self.broadcast_message({
                "type": "config_updated",
                "stream_name": stream_name,
                "config": config,
                "success": success
            })
        else:
            # Demo mode
            await self.broadcast_message({
                "type": "config_updated",
                "stream_name": stream_name,
                "config": config,
                "success": True
            })
    
    async def handle_get_status(self):
        """Invia status corrente"""
        if self.stream_controller:
            status = self.stream_controller.get_status()
            await self.broadcast_message({
                "type": "status_update",
                "data": status
            })
        else:
            # Demo status
            await self.broadcast_message({
                "type": "status_update",
                "data": self.demo_data
            })
    
    async def client_handler(self, websocket, path):
        """Handler per ogni client WebSocket"""
        await self.register_client(websocket)
        
        try:
            async for message in websocket:
                await self.handle_client_message(websocket, message)
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logger.error(f"❌ Errore client handler: {e}")
        finally:
            await self.unregister_client(websocket)
    
    def start_demo_data_simulator(self):
        """Simula dati di detection per demo"""
        def simulate():
            import random
            streams = ['traffic', 'security', 'people', 'sports']
            
            while True:
                try:
                    for stream_name in streams:
                        # Simula detection data
                        detection_data = {
                            "stream_name": stream_name,
                            "object_count": random.randint(1, 15),
                            "avg_confidence": random.randint(60, 95),
                            "fps": random.randint(8, 20),
                            "timestamp": int(time.time() * 1000),
                            "frame_url": None  # No actual frame per demo
                        }
                        
                        # Invia ai client in modo sicuro
                        if self.connected_clients:
                            # Usa thread-safe call
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            loop.run_until_complete(self.broadcast_message({
                                "type": "detection_update",
                                "data": detection_data
                            }))
                            loop.close()
                    
                    time.sleep(2)  # Update ogni 2 secondi
                    
                except Exception as e:
                    logger.error(f"❌ Errore simulatore: {e}")
                    time.sleep(5)  # Pausa in caso di errore
        
        if self.demo_mode:
            logger.info("🎭 Avvio simulatore dati demo")
            thread = threading.Thread(target=simulate, daemon=True)
            thread.start()
    
    async def start_server(self):
        """Avvia il server WebSocket"""
        if not WEBSOCKETS_AVAILABLE:
            logger.error("❌ WebSocket non disponibile")
            return
            
        logger.info(f"🚀 Avvio WebSocket server su {self.host}:{self.port}")
        
        if self.demo_mode:
            self.start_demo_data_simulator()
        
        try:
            async with websockets.serve(self.client_handler, self.host, self.port):
                logger.info(f"✅ Server avviato! Frontend: http://localhost:{self.port}")
                logger.info("📱 Apri frontend_dashboard.html nel browser")
                
                # Mantieni server attivo
                await asyncio.Future()  # Run forever
                
        except Exception as e:
            logger.error(f"❌ Errore avvio server: {e}")

def main():
    """Avvia server WebSocket standalone"""
    if not WEBSOCKETS_AVAILABLE:
        print("❌ Impossibile avviare server: websockets non installato")
        print("📦 Installa con: pip install websockets")
        return
        
    server = DashboardWebSocketServer()
    
    try:
        asyncio.run(server.start_server())
    except KeyboardInterrupt:
        logger.info("👋 Server fermato dall'utente")
    except Exception as e:
        logger.error(f"❌ Errore server: {e}")

if __name__ == "__main__":
    main()
