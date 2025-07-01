#!/usr/bin/env python3
"""
Demo Video Simulator
Simula stream video con frame reali per testare il dashboard
"""

import asyncio
import base64
import io
import time
import random
from PIL import Image, ImageDraw, ImageFont
import json

class DemoVideoSimulator:
    """
    Simula stream video con frame generati per testing dashboard
    """
    
    def __init__(self, websocket_server):
        self.websocket_server = websocket_server
        self.running = False
        
        # Configurazioni stream demo
        self.stream_configs = {
            "traffic": {
                "name": "Traffic Monitor",
                "objects": ["car", "truck", "bus", "motorcycle"],
                "colors": ["red", "blue", "green", "yellow", "white"],
                "max_objects": 8,
                "fps": 10
            },
            "security": {
                "name": "Security Monitor", 
                "objects": ["person"],
                "colors": ["black", "white", "gray"],
                "max_objects": 5,
                "fps": 12
            },
            "people": {
                "name": "People Counter",
                "objects": ["person"],
                "colors": ["red", "blue", "green", "purple"],
                "max_objects": 12,
                "fps": 8
            },
            "sports": {
                "name": "Sports Analysis",
                "objects": ["person", "sports ball"],
                "colors": ["white", "red", "blue"],
                "max_objects": 6,
                "fps": 15
            }
        }
    
    def generate_demo_frame(self, stream_name: str, width=320, height=240):
        """Genera frame demo con oggetti simulati"""
        config = self.stream_configs[stream_name]
        
        # Crea immagine base
        img = Image.new('RGB', (width, height), color='black')
        draw = ImageDraw.Draw(img)
        
        # Background pattern
        if stream_name == "traffic":
            # Strada grigia
            draw.rectangle([0, height//2, width, height], fill='darkgray')
            draw.line([0, height//2, width, height//2], fill='yellow', width=3)
        elif stream_name == "security":
            # Area sorveglianza
            draw.rectangle([50, 50, width-50, height-50], outline='red', width=2)
        elif stream_name == "people":
            # Marciapiede
            draw.rectangle([0, height-40, width, height], fill='lightgray')
        elif stream_name == "sports":
            # Campo sportivo
            draw.rectangle([0, 0, width, height], fill='darkgreen')
            draw.line([width//2, 0, width//2, height], fill='white', width=2)
        
        # Genera oggetti casuali
        num_objects = random.randint(1, config["max_objects"])
        detected_objects = []
        
        for i in range(num_objects):
            obj_type = random.choice(config["objects"])
            color = random.choice(config["colors"])
            
            # Posizione casuale
            x = random.randint(20, width-40)
            y = random.randint(20, height-40)
            
            # Disegna oggetto
            if obj_type == "car":
                draw.rectangle([x, y, x+30, y+15], fill=color, outline='white')
            elif obj_type == "truck":
                draw.rectangle([x, y, x+40, y+20], fill=color, outline='white')
            elif obj_type == "person":
                draw.ellipse([x, y, x+10, y+20], fill=color, outline='white')
            elif obj_type == "sports ball":
                draw.ellipse([x, y, x+8, y+8], fill='white', outline='black')
            else:
                draw.rectangle([x, y, x+15, y+15], fill=color, outline='white')
            
            # Aggiungi label
            try:
                draw.text((x, y-10), obj_type, fill='white')
            except:
                pass  # Font might not be available
            
            detected_objects.append({
                "type": obj_type,
                "confidence": random.uniform(0.6, 0.95),
                "bbox": [x, y, x+15, y+15]
            })
        
        # Timestamp
        timestamp = time.strftime("%H:%M:%S")
        try:
            draw.text((5, 5), f"{config['name']} - {timestamp}", fill='white')
        except:
            pass
        
        return img, detected_objects
    
    def image_to_base64(self, img):
        """Converte immagine PIL in base64 per web"""
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=85)
        img_str = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/jpeg;base64,{img_str}"
    
    async def simulate_stream(self, stream_name: str):
        """Simula stream per un singolo video"""
        config = self.stream_configs[stream_name]
        fps = config["fps"]
        interval = 1.0 / fps
        
        print(f"🎬 Avvio simulazione stream: {stream_name} ({fps} FPS)")
        
        while self.running:
            try:
                # Genera frame demo
                img, objects = self.generate_demo_frame(stream_name)
                frame_base64 = self.image_to_base64(img)
                
                # Calcola statistiche
                object_count = len(objects)
                avg_confidence = sum(obj["confidence"] for obj in objects) / max(1, object_count)
                avg_confidence = round(avg_confidence * 100)
                
                # Dati detection per frontend
                detection_data = {
                    "type": "detection_update",
                    "stream_name": stream_name,
                    "object_count": object_count,
                    "avg_confidence": avg_confidence,
                    "fps": fps,
                    "timestamp": int(time.time() * 1000),
                    "frame_url": frame_base64,
                    "objects": objects
                }
                
                # Invia ai client
                await self.websocket_server.broadcast_message(detection_data)
                
                # Aspetta prossimo frame
                await asyncio.sleep(interval)
                
            except Exception as e:
                print(f"❌ Errore simulazione {stream_name}: {e}")
                await asyncio.sleep(1)
    
    async def start_simulation(self):
        """Avvia simulazione per tutti gli stream"""
        print("🎭 Avvio simulazione video completa...")
        self.running = True
        
        # Avvia task per ogni stream
        tasks = []
        for stream_name in self.stream_configs.keys():
            task = asyncio.create_task(self.simulate_stream(stream_name))
            tasks.append(task)
        
        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            print(f"❌ Errore simulazione: {e}")
        finally:
            self.running = False
    
    def stop_simulation(self):
        """Ferma simulazione"""
        print("🛑 Fermando simulazione video...")
        self.running = False

# Test standalone
async def test_simulator():
    """Test del simulatore senza WebSocket"""
    print("🧪 Test Demo Video Simulator")
    
    class MockWebSocketServer:
        async def broadcast_message(self, message):
            print(f"📡 Broadcast: {message['stream_name']} - {message['object_count']} objects")
    
    mock_server = MockWebSocketServer()
    simulator = DemoVideoSimulator(mock_server)
    
    # Test per 10 secondi
    print("🎬 Test per 10 secondi...")
    try:
        task = asyncio.create_task(simulator.start_simulation())
        await asyncio.sleep(10)
        simulator.stop_simulation()
        await task
    except KeyboardInterrupt:
        simulator.stop_simulation()
    
    print("✅ Test completato")

if __name__ == "__main__":
    asyncio.run(test_simulator())
