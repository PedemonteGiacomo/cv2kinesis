#!/usr/bin/env python3
"""
Esempio di Integrazione Frontend Personalizzato
Dimostra come il tuo team può integrare un frontend custom con il backend processor
"""

import asyncio
import json
import logging
import time
import boto3
import glob
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

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

class BackendProcessorClient:
    """
    Client per comunicare con il backend processor esistente
    Legge messaggi SQS e fornisce accesso alle immagini S3
    """
    
    def __init__(self, sqs_queue_url: str, aws_region: str = 'eu-central-1'):
        self.sqs_queue_url = sqs_queue_url
        self.aws_region = aws_region
        
        # Client AWS
        self.sqs = boto3.client('sqs', region_name=aws_region)
        self.s3 = boto3.client('s3', region_name=aws_region)
        
        logger.info(f"Backend Processor Client inizializzato")
        logger.info(f"SQS Queue: {sqs_queue_url}")
        logger.info(f"AWS Region: {aws_region}")
        
        # Pulizia automatica file scaricati
        self.cleanup_downloaded_frames()
    
    def cleanup_downloaded_frames(self):
        """Pulizia automatica dei file downloaded_frame_*"""
        try:
            frame_files = glob.glob("downloaded_frame_*")
            if frame_files:
                logger.info(f"Pulizia {len(frame_files)} file scaricati...")
                for file in frame_files:
                    try:
                        os.remove(file)
                        logger.info(f"   Rimosso: {file}")
                    except Exception as e:
                        logger.warning(f"   Errore rimozione {file}: {e}")
        except Exception as e:
            logger.warning(f"Errore durante pulizia: {e}")
    
    def poll_detection_results(self, max_messages: int = 10, wait_time: int = 5) -> List[Dict[str, Any]]:
        """
        Legge nuovi risultati di detection dal backend processor
        
        Returns:
            Lista di messaggi di detection nel formato standard
        """
        try:
            response = self.sqs.receive_message(
                QueueUrl=self.sqs_queue_url,
                MaxNumberOfMessages=max_messages,
                WaitTimeSeconds=wait_time,
                MessageAttributeNames=['All']
            )
            
            messages = response.get('Messages', [])
            results = []
            
            for message in messages:
                try:
                    # Parse JSON dal backend processor
                    detection_data = json.loads(message['Body'])
                    
                    # Arricchisci con URL per l'immagine
                    if 'bucket' in detection_data and 'key' in detection_data:
                        detection_data['frame_url'] = self.get_frame_presigned_url(
                            detection_data['bucket'], 
                            detection_data['key']
                        )
                    
                    results.append(detection_data)
                    
                    # Cancella messaggio processato
                    self.sqs.delete_message(
                        QueueUrl=self.sqs_queue_url,
                        ReceiptHandle=message['ReceiptHandle']
                    )
                    
                    logger.info(f"✅ Processato messaggio: frame {detection_data.get('frame_index', 'N/A')}, "
                               f"{detection_data.get('detections_count', 0)} detection")
                    
                except json.JSONDecodeError as e:
                    logger.error(f"❌ Errore parsing JSON: {e}")
                except Exception as e:
                    logger.error(f"❌ Errore processing messaggio: {e}")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Errore polling SQS: {e}")
            return []
    
    def get_frame_presigned_url(self, bucket: str, key: str, expiration: int = 3600) -> str:
        """
        Genera URL firmato per accesso diretto alle immagini S3
        
        Args:
            bucket: Nome del bucket S3
            key: Chiave dell'oggetto S3
            expiration: Durata validità URL in secondi
            
        Returns:
            URL firmato per accesso diretto all'immagine
        """
        try:
            return self.s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket, 'Key': key},
                ExpiresIn=expiration
            )
        except Exception as e:
            logger.error(f"❌ Errore generazione URL firmato: {e}")
            return ""
    
    def download_frame_bytes(self, bucket: str, key: str) -> Optional[bytes]:
        """
        Scarica direttamente i bytes dell'immagine da S3
        
        Args:
            bucket: Nome del bucket S3
            key: Chiave dell'oggetto S3
            
        Returns:
            Bytes dell'immagine o None se errore
        """
        try:
            response = self.s3.get_object(Bucket=bucket, Key=key)
            return response['Body'].read()
        except Exception as e:
            logger.error(f"❌ Errore download immagine: {e}")
            return None

class CustomFrontendBridge:
    """
    Bridge WebSocket per frontend personalizzato
    Converte messaggi SQS in eventi WebSocket real-time
    """
    
    def __init__(self, backend_client: BackendProcessorClient):
        self.backend_client = backend_client
        self.connected_clients = set()
        self.running = False
        
    async def register_client(self, websocket):
        """Registra nuovo client frontend"""
        self.connected_clients.add(websocket)
        client_count = len(self.connected_clients)
        logger.info(f"✅ Frontend client connesso (totale: {client_count})")
        
        # Invia messaggio di benvenuto
        await self.send_to_client(websocket, {
            "type": "connection_established",
            "message": "Connesso al backend processor",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })
    
    async def unregister_client(self, websocket):
        """Rimuovi client disconnesso"""
        self.connected_clients.discard(websocket)
        client_count = len(self.connected_clients)
        logger.info(f"❌ Frontend client disconnesso (totale: {client_count})")
    
    async def send_to_client(self, websocket, message: dict):
        """Invia messaggio a un client specifico"""
        try:
            await websocket.send(json.dumps(message))
        except websockets.exceptions.ConnectionClosed:
            await self.unregister_client(websocket)
        except Exception as e:
            logger.error(f"❌ Errore invio a client: {e}")
    
    async def broadcast_message(self, message: dict):
        """Invia messaggio a tutti i client connessi"""
        if not self.connected_clients:
            return
        
        disconnected_clients = set()
        
        for client in self.connected_clients.copy():
            try:
                await client.send(json.dumps(message))
            except websockets.exceptions.ConnectionClosed:
                disconnected_clients.add(client)
            except Exception as e:
                logger.error(f"❌ Errore broadcast a client: {e}")
                disconnected_clients.add(client)
        
        # Rimuovi client disconnessi
        for client in disconnected_clients:
            await self.unregister_client(client)
    
    async def poll_and_broadcast_loop(self):
        """Loop principale: polling SQS e broadcast ai client"""
        logger.info("🔄 Avvio loop polling backend processor...")
        
        while self.running:
            try:
                # Leggi nuovi risultati dal backend processor
                detection_results = self.backend_client.poll_detection_results()
                
                for result in detection_results:
                    # Prepara messaggio per frontend
                    frontend_message = {
                        "type": "detection_update",
                        "data": {
                            "stream_name": result.get('stream_name', 'unknown'),
                            "frame_index": result.get('frame_index', 0),
                            "detections_count": result.get('detections_count', 0),
                            "objects": result.get('summary', []),
                            "timestamp": result.get('timestamp', ''),
                            "frame_url": result.get('frame_url', ''),
                            "s3_location": {
                                "bucket": result.get('bucket', ''),
                                "key": result.get('key', '')
                            }
                        }
                    }
                    
                    # Broadcast a tutti i client frontend
                    await self.broadcast_message(frontend_message)
                    
                    logger.info(f"📡 Broadcast detection: frame {result.get('frame_index')}, "
                               f"{result.get('detections_count', 0)} oggetti, "
                               f"{len(self.connected_clients)} client")
                
                # Pausa tra polling
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"❌ Errore nel loop polling: {e}")
                await asyncio.sleep(5)
    
    async def websocket_handler(self, websocket):
        """Handler per connessioni WebSocket"""
        await self.register_client(websocket)
        
        try:
            # Avvia polling se primo client
            if len(self.connected_clients) == 1 and not self.running:
                self.running = True
                asyncio.create_task(self.poll_and_broadcast_loop())
            
            # Ascolta messaggi dal client
            async for message in websocket:
                await self.handle_frontend_command(websocket, message)
                
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logger.error(f"❌ Errore WebSocket handler: {e}")
        finally:
            await self.unregister_client(websocket)
            
            # Ferma polling se nessun client
            if len(self.connected_clients) == 0:
                self.running = False
    
    async def handle_frontend_command(self, websocket, message_str: str):
        """Gestisce comandi dal frontend"""
        try:
            command = json.loads(message_str)
            command_type = command.get('command')
            
            logger.info(f"📨 Comando frontend: {command_type}")
            
            if command_type == 'get_status':
                # Restituisci stato del sistema
                await self.send_to_client(websocket, {
                    "type": "status_response",
                    "data": {
                        "connected_clients": len(self.connected_clients),
                        "polling_active": self.running,
                        "backend_queue": self.backend_client.sqs_queue_url,
                        "timestamp": datetime.utcnow().isoformat() + "Z"
                    }
                })
            
            elif command_type == 'request_latest':
                # Richiesta dati più recenti
                recent_results = self.backend_client.poll_detection_results(max_messages=5, wait_time=1)
                for result in recent_results:
                    frontend_message = {
                        "type": "detection_update",
                        "data": {
                            "stream_name": result.get('stream_name', 'unknown'),
                            "frame_index": result.get('frame_index', 0),
                            "detections_count": result.get('detections_count', 0),
                            "objects": result.get('summary', []),
                            "timestamp": result.get('timestamp', ''),
                            "frame_url": result.get('frame_url', '')
                        }
                    }
                    await self.send_to_client(websocket, frontend_message)
            
            else:
                # Comando non riconosciuto
                await self.send_to_client(websocket, {
                    "type": "error",
                    "message": f"Comando non riconosciuto: {command_type}"
                })
                
        except json.JSONDecodeError:
            logger.error("❌ Comando JSON non valido dal frontend")
        except Exception as e:
            logger.error(f"❌ Errore gestione comando: {e}")

class CustomFrontendIntegrationExample:
    """
    Esempio completo di integrazione frontend personalizzato
    """
    
    def __init__(self, sqs_queue_url: str, websocket_port: int = 8080):
        self.sqs_queue_url = sqs_queue_url
        self.websocket_port = websocket_port
        
        # Inizializza client backend
        self.backend_client = BackendProcessorClient(sqs_queue_url)
        
        # Inizializza bridge WebSocket
        self.websocket_bridge = CustomFrontendBridge(self.backend_client)
    
    async def start_websocket_server(self):
        """Avvia server WebSocket per frontend"""
        if not WEBSOCKETS_AVAILABLE:
            logger.error("❌ websockets non disponibile. Installa con: pip install websockets")
            return
        
        logger.info(f"🌐 Avvio WebSocket server su porta {self.websocket_port}")
        logger.info(f"🔗 Frontend può connettersi a: ws://localhost:{self.websocket_port}")
        
        # Avvia server WebSocket
        await serve(
            self.websocket_bridge.websocket_handler,
            "localhost",
            self.websocket_port
        )
        
        logger.info("✅ WebSocket server avviato")
        logger.info("📱 Pronto per connessioni frontend personalizzate")
    
    def test_direct_polling(self):
        """Test polling diretto senza WebSocket"""
        logger.info("🧪 Test polling diretto del backend processor...")
        
        for i in range(5):
            logger.info(f"📡 Polling #{i+1}...")
            
            results = self.backend_client.poll_detection_results(max_messages=3, wait_time=2)
            
            if results:
                for result in results:
                    logger.info(f"✅ Ricevuto: frame {result.get('frame_index')}, "
                               f"{result.get('detections_count', 0)} detection, "
                               f"stream {result.get('stream_name')}")
                    
                    # Mostra alcuni dettagli delle detection
                    objects = result.get('summary', [])
                    for obj in objects[:3]:  # Prime 3 detection
                        logger.info(f"   🎯 {obj.get('class')} "
                                   f"(confidence: {obj.get('conf', 0):.2f})")
            else:
                logger.info("⏳ Nessun nuovo risultato")
            
            time.sleep(3)
        
        logger.info("🧪 Test completato")

async def main():
    """
    Esempio di utilizzo principale
    """
    # Configurazione (usa gli output del tuo CDK stack)
    SQS_QUEUE_URL = "https://sqs.eu-central-1.amazonaws.com/544547773663/processing-results"
    WEBSOCKET_PORT = 8080
    
    logger.info("Avvio esempio integrazione frontend personalizzato")
    logger.info("="*80)
    
    # Crea istanza esempio
    integration = CustomFrontendIntegrationExample(SQS_QUEUE_URL, WEBSOCKET_PORT)
    
    print("\nOpzioni disponibili:")
    print("1. Test polling diretto (senza WebSocket)")
    print("2. Avvia WebSocket server per frontend")
    print("3. Entrambi (test + server)")
    
    try:
        choice = input("\nScegli opzione (1/2/3): ").strip()
        
        if choice == "1":
            logger.info("Modalita: Test polling diretto")
            integration.test_direct_polling()
            
        elif choice == "2":
            logger.info("Modalita: WebSocket server")
            await integration.start_websocket_server()
            
            # Mantieni server attivo
            logger.info("Server in ascolto... Premi Ctrl+C per fermare")
            await asyncio.Event().wait()  # Wait forever
            
        elif choice == "3":
            logger.info("Modalita: Test + WebSocket server")
            
            # Test veloce
            logger.info("Test rapido...")
            integration.test_direct_polling()
            
            logger.info("\nAvvio WebSocket server...")
            await integration.start_websocket_server()
            
            # Mantieni server attivo
            logger.info("Server in ascolto... Premi Ctrl+C per fermare")
            await asyncio.Event().wait()
            
        else:
            logger.error("Scelta non valida")
    
    except KeyboardInterrupt:
        logger.info("\nEsempio interrotto dall'utente")
    except Exception as e:
        logger.error(f"Errore: {e}")

if __name__ == "__main__":
    print("ESEMPIO INTEGRAZIONE FRONTEND PERSONALIZZATO")
    print("="*60)
    print("Questo script dimostra come il tuo team puo integrare")
    print("    un frontend personalizzato con il backend processor")
    print("Legge messaggi SQS dal processor ECS Fargate esistente")
    print("Fornisce WebSocket server per frontend real-time")
    print("="*60)
    
    asyncio.run(main())
