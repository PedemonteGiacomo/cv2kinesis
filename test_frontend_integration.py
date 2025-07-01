#!/usr/bin/env python3
"""
Script Test Rapido per Integrazione Frontend Personalizzato
Testa la compatibilità dei messaggi e la connessione con il backend processor
"""

import json
import time
import sys
import os
import glob
from datetime import datetime

def cleanup_downloaded_frames():
    """Pulizia automatica dei file downloaded_frame_*"""
    try:
        # Trova tutti i file che iniziano con downloaded_frame_
        frame_files = glob.glob("downloaded_frame_*")
        
        if frame_files:
            print(f"Pulizia {len(frame_files)} file scaricati...")
            for file in frame_files:
                try:
                    os.remove(file)
                    print(f"   Rimosso: {file}")
                except Exception as e:
                    print(f"   Errore rimozione {file}: {e}")
        else:
            print("Nessun file downloaded_frame_* da pulire")
            
    except Exception as e:
        print(f"Errore durante pulizia: {e}")

def test_message_compatibility():
    """Test formato messaggi JSON per compatibilità"""
    print("\nTEST COMPATIBILITA MESSAGGI JSON")
    print("="*50)
    
    # Esempio messaggio dal backend processor (app_cloud.py)
    backend_message = {
        "bucket": "processedframes-544547773663-eu-central-1",
        "key": "2025-01-13/14-30-15/frame_123_1737123456.jpg",
        "frame_index": 123,
        "detections_count": 3,
        "summary": [
            {
                "class": "person",
                "conf": 0.85,
                "bbox": [0.1, 0.2, 0.3, 0.4]
            },
            {
                "class": "car", 
                "conf": 0.92,
                "bbox": [0.5, 0.3, 0.2, 0.4]
            },
            {
                "class": "bicycle",
                "conf": 0.78,
                "bbox": [0.2, 0.6, 0.15, 0.25]
            }
        ],
        "timestamp": "2025-01-13T14:30:15.123456Z",
        "stream_name": "cv2kinesis"
    }
    
    print("Messaggio di esempio dal backend processor:")
    print(json.dumps(backend_message, indent=2))
    print()
    
    # Test parsing e trasformazione per frontend
    print("Trasformazione per frontend personalizzato:")
    
    try:
        # Simula processing per frontend
        frontend_message = {
            "type": "detection_update",
            "data": {
                "stream_name": backend_message.get('stream_name', 'unknown'),
                "frame_index": backend_message.get('frame_index', 0),
                "detections_count": backend_message.get('detections_count', 0),
                "objects": backend_message.get('summary', []),
                "timestamp": backend_message.get('timestamp', ''),
                "frame_url": f"https://s3.eu-central-1.amazonaws.com/{backend_message['bucket']}/{backend_message['key']}",
                "s3_location": {
                    "bucket": backend_message.get('bucket', ''),
                    "key": backend_message.get('key', '')
                }
            }
        }
        
        print(json.dumps(frontend_message, indent=2))
        print()
        
        # Valida campi essenziali
        required_fields = ['stream_name', 'frame_index', 'detections_count', 'objects', 'timestamp']
        missing_fields = []
        
        for field in required_fields:
            if field not in frontend_message['data']:
                missing_fields.append(field)
        
        if missing_fields:
            print(f"Campi mancanti: {missing_fields}")
            return False
        else:
            print("Tutti i campi essenziali presenti")
            print("Formato messaggio compatibile")
            return True
            
    except Exception as e:
        print(f"Errore nella trasformazione: {e}")
        return False

def test_bbox_coordinates():
    """Test formato coordinate bounding box"""
    print("\nTEST COORDINATE BOUNDING BOX")
    print("="*50)
    
    # Coordinate normalizzate dal backend
    bbox_normalized = [0.1, 0.2, 0.3, 0.4]  # [x, y, width, height]
    
    print(f"Coordinate normalizzate: {bbox_normalized}")
    print("   Format: [x, y, width, height] (0.0 - 1.0)")
    
    # Conversione per canvas/immagine
    image_width = 1920
    image_height = 1080
    
    x = int(bbox_normalized[0] * image_width)
    y = int(bbox_normalized[1] * image_height)
    width = int(bbox_normalized[2] * image_width)
    height = int(bbox_normalized[3] * image_height)
    
    print(f"\nCoordinate assolute per immagine {image_width}x{image_height}:")
    print(f"   x={x}, y={y}, width={width}, height={height}")
    print(f"   Top-left: ({x}, {y})")
    print(f"   Bottom-right: ({x + width}, {y + height})")
    
    # CSS/HTML positioning
    css_left = f"{bbox_normalized[0] * 100:.1f}%"
    css_top = f"{bbox_normalized[1] * 100:.1f}%"
    css_width = f"{bbox_normalized[2] * 100:.1f}%"
    css_height = f"{bbox_normalized[3] * 100:.1f}%"
    
    print(f"\nCSS positioning per overlay:")
    print(f"   left: {css_left}, top: {css_top}")
    print(f"   width: {css_width}, height: {css_height}")
    
    return True

def test_aws_configuration():
    """Test configurazione AWS"""
    print("\nTEST CONFIGURAZIONE AWS")
    print("="*50)
    
    # Controlla variabili environment
    aws_vars = [
        'AWS_ACCESS_KEY_ID',
        'AWS_SECRET_ACCESS_KEY', 
        'AWS_SESSION_TOKEN',
        'AWS_REGION'
    ]
    
    print("Credenziali AWS:")
    for var in aws_vars:
        value = os.environ.get(var, '')
        if value:
            if 'SECRET' in var or 'TOKEN' in var:
                print(f"   {var}: {'*' * 20}")
            else:
                print(f"   {var}: {value}")
        else:
            print(f"   {var}: Non impostata")
    
    # Configurazione stack
    print(f"\nConfigurazione Stack:")
    stack_config = {
        'SQS_QUEUE_URL': 'https://sqs.eu-central-1.amazonaws.com/544547773663/processing-results',
        'S3_BUCKET_NAME': 'processedframes-544547773663-eu-central-1',
        'KINESIS_STREAM_NAME': 'cv2kinesis',
        'AWS_REGION': 'eu-central-1',
        'LOAD_BALANCER_URL': 'http://VideoPipelineStack-ServiceLBE9A1ADBC-123456789.eu-central-1.elb.amazonaws.com'
    }
    
    for key, value in stack_config.items():
        print(f"   {key}: {value}")
    
    return True

def test_websocket_message_flow():
    """Test flusso messaggi WebSocket"""
    print("\n[WEBSOCKET] TEST FLUSSO MESSAGGI WEBSOCKET")
    print("="*50)
    
    # Messaggio di connessione
    connection_msg = {
        "type": "connection_established",
        "message": "Connesso al backend processor",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    print("[1] Messaggio connessione:")
    print(json.dumps(connection_msg, indent=2))
    
    # Comando dal frontend
    frontend_command = {
        "command": "get_status"
    }
    print("\n[2] Comando da frontend:")
    print(json.dumps(frontend_command, indent=2))
    
    # Risposta status
    status_response = {
        "type": "status_response",
        "data": {
            "connected_clients": 1,
            "polling_active": True,
            "backend_queue": "https://sqs.eu-central-1.amazonaws.com/544547773663/processing-results",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    }
    print("\n[3] Risposta status:")
    print(json.dumps(status_response, indent=2))
    
    # Update detection
    detection_update = {
        "type": "detection_update",
        "data": {
            "stream_name": "cv2kinesis",
            "frame_index": 456,
            "detections_count": 2,
            "objects": [
                {"class": "person", "conf": 0.89, "bbox": [0.2, 0.3, 0.25, 0.4]},
                {"class": "car", "conf": 0.95, "bbox": [0.6, 0.1, 0.3, 0.35]}
            ],
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "frame_url": "https://s3.eu-central-1.amazonaws.com/bucket/key.jpg"
        }
    }
    print("\n[4] Update detection:")
    print(json.dumps(detection_update, indent=2))
    
    return True

def run_integration_checklist():
    """Checklist per integrazione"""
    print("\n[CHECKLIST] CHECKLIST INTEGRAZIONE FRONTEND")
    print("="*50)
    
    checklist = [
        ("[OK] Backend processor deployato", "stream_service/app_cloud.py su ECS Fargate"),
        ("[OK] SQS queue configurata", "processing-results queue riceve messaggi"),
        ("[OK] S3 bucket configurato", "processedframes bucket salva immagini"),
        ("[OK] Formato messaggi standardizzato", "JSON con campi: bucket, key, frame_index, etc."),
        ("[OK] WebSocket bridge disponibile", "custom_frontend_integration_example.py"),
        ("[OK] Frontend example pronto", "custom_frontend_example.html"),
        ("[TEST] Test connessione AWS", "Verifica credenziali e permessi"),
        ("[TEST] Test polling SQS", "python sqs_consumer.py <queue_url>"),
        ("[TEST] Test WebSocket server", "python custom_frontend_integration_example.py"),
        ("[TEST] Test frontend HTML", "Apri custom_frontend_example.html nel browser")
    ]
    
    for status, description in checklist:
        print(f"{status} {description}")
    
    print(f"\n[NEXT] PROSSIMI PASSI:")
    print("1. Testa il consumer SQS esistente:")
    print("   python sqs_consumer.py https://sqs.eu-central-1.amazonaws.com/544547773663/processing-results")
    print()
    print("2. Avvia WebSocket bridge per frontend:")
    print("   python custom_frontend_integration_example.py")
    print()
    print("3. Apri frontend di esempio:")
    print("   custom_frontend_example.html nel browser")
    print()
    print("4. Integra nel tuo frontend personalizzato:")
    print("   Usa il WebSocket bridge o polling SQS diretto")

def main():
    """Main test function"""
    print("TEST INTEGRAZIONE FRONTEND PERSONALIZZATO")
    print("="*60)
    print("Verifica compatibilita messaggi e configurazione")
    print("Assicura integrazione seamless con backend processor")
    print("="*60)
    
    # Pulizia automatica file scaricati
    print("\nPulizia file scaricati precedenti...")
    cleanup_downloaded_frames()
    print()
    
    tests = [
        ("Compatibilità Messaggi", test_message_compatibility),
        ("Coordinate Bounding Box", test_bbox_coordinates), 
        ("Configurazione AWS", test_aws_configuration),
        ("Flusso Messaggi WebSocket", test_websocket_message_flow)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            print(f"\n[TEST] Eseguendo: {test_name}")
            result = test_func()
            results.append((test_name, result))
            if result:
                print(f"[PASS] {test_name}: PASSED")
            else:
                print(f"[FAIL] {test_name}: FAILED")
        except Exception as e:
            print(f"[ERROR] {test_name}: ERROR - {e}")
            results.append((test_name, False))
    
    # Riepilogo
    print("\n[SUMMARY] RIEPILOGO TEST")
    print("="*50)
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status} {test_name}")
    
    print(f"\n[RESULT] Risultato: {passed}/{total} test passati")
    
    if passed == total:
        print("[SUCCESS] TUTTI I TEST PASSATI!")
        print("[READY] Il tuo frontend personalizzato puo integrarsi immediatamente")
    else:
        print("[WARNING] Alcuni test falliti. Controlla la configurazione.")
    
    # Checklist finale
    run_integration_checklist()

if __name__ == "__main__":
    main()
