#!/usr/bin/env python3
"""
Multi-Stream Producer Controller
Gestisce 4 video stream simultanei per dashboard multi-card
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

import threading
import time
import json
import cv2
import boto3
from typing import Dict, Optional
from dataclasses import dataclass

# Import from src library
from lib.video import kinesis_producer
from lib.aws import aws_get_service

@dataclass
class StreamConfig:
    name: str
    kinesis_stream: str
    video_source: str  # path to video file or 'webcam'
    detection_classes: list = None  # ['person', 'car'] or None for all
    confidence_threshold: float = 0.5
    fps_limit: int = 10

class MultiStreamController:
    """
    Controller per gestire 4 stream video simultanei
    Ogni stream può avere configurazioni diverse
    """
    
    def __init__(self):
        self.streams: Dict[str, StreamConfig] = {}
        self.active_threads: Dict[str, threading.Thread] = {}
        self.stop_flags: Dict[str, bool] = {}
        
        # Setup AWS clients
        self.kinesis_client = boto3.client('kinesis', region_name='us-east-1')
        
        # Configurazioni predefinite per 4 stream
        self.setup_default_streams()
    
    def setup_default_streams(self):
        """Setup configurazioni predefinite per 4 stream"""
        self.streams = {
            "traffic": StreamConfig(
                name="traffic",
                kinesis_stream="cv2kinesis-traffic-stream",
                video_source="demo_videos/traffic.mp4",
                detection_classes=['car', 'truck', 'bus', 'motorcycle'],
                confidence_threshold=0.6,
                fps_limit=8
            ),
            "security": StreamConfig(
                name="security", 
                kinesis_stream="cv2kinesis-security-stream",
                video_source="demo_videos/security.mp4",
                detection_classes=['person'],
                confidence_threshold=0.7,
                fps_limit=10
            ),
            "people": StreamConfig(
                name="people",
                kinesis_stream="cv2kinesis-people-stream", 
                video_source="demo_videos/people.mp4",
                detection_classes=['person'],
                confidence_threshold=0.5,
                fps_limit=12
            ),
            "sports": StreamConfig(
                name="sports",
                kinesis_stream="cv2kinesis-sports-stream",
                video_source="demo_videos/sports.mp4",
                detection_classes=['person', 'sports ball'],
                confidence_threshold=0.4,
                fps_limit=15
            )
        }
    
    def start_stream(self, stream_name: str) -> bool:
        """Avvia un singolo stream"""
        if stream_name not in self.streams:
            print(f"❌ Stream '{stream_name}' non trovato")
            return False
            
        if stream_name in self.active_threads and self.active_threads[stream_name].is_alive():
            print(f"⚠️  Stream '{stream_name}' già attivo")
            return False
        
        config = self.streams[stream_name]
        self.stop_flags[stream_name] = False
        
        # Crea thread per questo stream
        thread = threading.Thread(
            target=self._stream_worker,
            args=(stream_name, config),
            name=f"Stream-{stream_name}"
        )
        
        self.active_threads[stream_name] = thread
        thread.start()
        
        print(f"✅ Stream '{stream_name}' avviato")
        return True
    
    def stop_stream(self, stream_name: str) -> bool:
        """Ferma un singolo stream"""
        if stream_name not in self.stop_flags:
            print(f"❌ Stream '{stream_name}' non trovato")
            return False
        
        self.stop_flags[stream_name] = True
        
        if stream_name in self.active_threads:
            thread = self.active_threads[stream_name]
            thread.join(timeout=3.0)  # Wait max 3 seconds
            
            if not thread.is_alive():
                print(f"✅ Stream '{stream_name}' fermato")
                del self.active_threads[stream_name]
                return True
            else:
                print(f"⚠️  Stream '{stream_name}' non si è fermato completamente")
                return False
        
        return True
    
    def switch_source(self, stream_name: str, new_source: str) -> bool:
        """Cambia sorgente di un stream (es. da video a webcam)"""
        if stream_name not in self.streams:
            return False
        
        # Ferma stream corrente
        was_running = stream_name in self.active_threads and self.active_threads[stream_name].is_alive()
        
        if was_running:
            self.stop_stream(stream_name)
            time.sleep(1)  # Brief pause
        
        # Aggiorna configurazione
        self.streams[stream_name].video_source = new_source
        
        # Riavvia se era attivo
        if was_running:
            return self.start_stream(stream_name)
        
        print(f"✅ Sorgente stream '{stream_name}' cambiata in '{new_source}'")
        return True
    
    def update_config(self, stream_name: str, **kwargs) -> bool:
        """Aggiorna configurazione di un stream"""
        if stream_name not in self.streams:
            return False
        
        config = self.streams[stream_name]
        
        # Aggiorna parametri
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
                print(f"✅ {stream_name}.{key} = {value}")
        
        return True
    
    def _stream_worker(self, stream_name: str, config: StreamConfig):
        """Worker thread per un singolo stream"""
        print(f"🎬 Avviando stream worker: {stream_name}")
        
        try:
            # Setup video capture
            if config.video_source == 'webcam':
                cap = cv2.VideoCapture(0)
            else:
                cap = cv2.VideoCapture(config.video_source)
            
            if not cap.isOpened():
                print(f"❌ Impossibile aprire sorgente: {config.video_source}")
                return
            
            frame_count = 0
            last_time = time.time()
            
            while not self.stop_flags.get(stream_name, False):
                ret, frame = cap.read()
                
                if not ret:
                    if config.video_source != 'webcam':
                        # Reset video file to loop
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    else:
                        print(f"❌ Errore lettura webcam per stream {stream_name}")
                        break
                
                # FPS limiting
                current_time = time.time()
                time_diff = current_time - last_time
                target_time = 1.0 / config.fps_limit
                
                if time_diff < target_time:
                    time.sleep(target_time - time_diff)
                
                # Send frame to Kinesis
                self._send_frame_to_kinesis(stream_name, frame, config)
                
                frame_count += 1
                last_time = time.time()
                
                # Log progress ogni 100 frame
                if frame_count % 100 == 0:
                    print(f"📡 {stream_name}: {frame_count} frames inviati")
            
            cap.release()
            print(f"🏁 Stream worker '{stream_name}' terminato")
            
        except Exception as e:
            print(f"❌ Errore in stream worker '{stream_name}': {e}")
    
    def _send_frame_to_kinesis(self, stream_name: str, frame, config: StreamConfig):
        """Invia frame a Kinesis con metadata"""
        try:
            # Resize frame per efficienza
            height, width = frame.shape[:2]
            if width > 640:
                scale = 640 / width
                new_width = 640
                new_height = int(height * scale)
                frame = cv2.resize(frame, (new_width, new_height))
            
            # Encode frame
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            frame_data = buffer.tobytes()
            
            # Metadata per il processing
            metadata = {
                'stream_name': stream_name,
                'detection_classes': config.detection_classes,
                'confidence_threshold': config.confidence_threshold,
                'timestamp': int(time.time() * 1000)
            }
            
            # Send to Kinesis
            response = self.kinesis_client.put_record(
                StreamName=config.kinesis_stream,
                Data=frame_data,
                PartitionKey=stream_name,
                ExplicitHashKey=None,
                SequenceNumberForOrdering=None
            )
            
            # Include metadata come record separato (opzionale)
            self.kinesis_client.put_record(
                StreamName=config.kinesis_stream,
                Data=json.dumps(metadata).encode('utf-8'),
                PartitionKey=f"{stream_name}-metadata"
            )
            
        except Exception as e:
            print(f"❌ Errore invio frame Kinesis per {stream_name}: {e}")
    
    def start_all_streams(self):
        """Avvia tutti e 4 gli stream"""
        print("🚀 Avviando tutti gli stream...")
        
        for stream_name in self.streams.keys():
            self.start_stream(stream_name)
            time.sleep(0.5)  # Piccola pausa tra avvii
        
        print("✅ Tutti gli stream avviati")
    
    def stop_all_streams(self):
        """Ferma tutti gli stream"""
        print("🛑 Fermando tutti gli stream...")
        
        for stream_name in list(self.active_threads.keys()):
            self.stop_stream(stream_name)
        
        print("✅ Tutti gli stream fermati")
    
    def get_status(self) -> dict:
        """Ritorna stato di tutti gli stream"""
        status = {}
        for stream_name, config in self.streams.items():
            status[stream_name] = {
                'config': {
                    'source': config.video_source,
                    'kinesis_stream': config.kinesis_stream,
                    'classes': config.detection_classes,
                    'confidence': config.confidence_threshold,
                    'fps_limit': config.fps_limit
                },
                'active': stream_name in self.active_threads and self.active_threads[stream_name].is_alive(),
                'thread_name': self.active_threads.get(stream_name, {}).name if stream_name in self.active_threads else None
            }
        return status

def main():
    """Demo del controller multi-stream"""
    controller = MultiStreamController()
    
    print("🎮 Multi-Stream Controller Demo")
    print("=" * 50)
    
    while True:
        print("\n📋 Comandi disponibili:")
        print("1. 🚀 Avvia tutti gli stream")
        print("2. 🛑 Ferma tutti gli stream") 
        print("3. 📊 Stato stream")
        print("4. 🎯 Avvia stream singolo")
        print("5. ⏹️  Ferma stream singolo")
        print("6. 🔄 Cambia sorgente stream")
        print("7. ⚙️  Aggiorna configurazione")
        print("0. ❌ Esci")
        
        choice = input("\n👉 Scegli opzione: ").strip()
        
        if choice == '0':
            controller.stop_all_streams()
            print("👋 Arrivederci!")
            break
            
        elif choice == '1':
            controller.start_all_streams()
            
        elif choice == '2':
            controller.stop_all_streams()
            
        elif choice == '3':
            status = controller.get_status()
            print("\n📊 Stato Stream:")
            for name, info in status.items():
                active = "🟢 ATTIVO" if info['active'] else "🔴 FERMO"
                print(f"  {name}: {active}")
                print(f"    📁 Source: {info['config']['source']}")
                print(f"    📡 Kinesis: {info['config']['kinesis_stream']}")
                print(f"    🎯 Classes: {info['config']['classes']}")
                
        elif choice == '4':
            stream_name = input("📌 Nome stream (traffic/security/people/sports): ")
            controller.start_stream(stream_name)
            
        elif choice == '5':
            stream_name = input("📌 Nome stream da fermare: ")
            controller.stop_stream(stream_name)
            
        elif choice == '6':
            stream_name = input("📌 Nome stream: ")
            new_source = input("📁 Nuova sorgente (path/video o 'webcam'): ")
            controller.switch_source(stream_name, new_source)
            
        elif choice == '7':
            stream_name = input("📌 Nome stream: ")
            print("⚙️  Parametri modificabili: confidence_threshold, fps_limit, detection_classes")
            param = input("📝 Parametro: ")
            value = input("🔢 Nuovo valore: ")
            
            # Convert value to appropriate type
            if param == 'confidence_threshold':
                value = float(value)
            elif param == 'fps_limit':
                value = int(value)
            elif param == 'detection_classes':
                value = value.split(',') if value else None
            
            controller.update_config(stream_name, **{param: value})
        
        else:
            print("❌ Opzione non valida")

if __name__ == "__main__":
    main()
