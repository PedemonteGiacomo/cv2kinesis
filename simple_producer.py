#!/usr/bin/env python3
"""
Simple Stream Producer
Invia video alla pipeline per test rapido
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

import logging
from lib.video import kinesis_producer

# Configurazione logging
logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(message)s',
    level=logging.INFO,
    datefmt='%d/%m/%Y %X'
)

def main():
    """
    Avvia producer semplice per test
    """
    print("=" * 60)
    print("        SIMPLE STREAM PRODUCER")  
    print("=" * 60)
    print("Invia video dalla webcam al pipeline")
    print("Stream: cv2kinesis")
    print("Risoluzione: 640px")
    print("Press 'q' nella finestra video per uscire")
    print("=" * 60)
    
    try:
        # Usa i parametri standard del sistema
        kinesis_producer(
            kinesis_stream_name='cv2kinesis',
            cam_uri=0,  # Webcam
            width=640
        )
    except KeyboardInterrupt:
        print("\n[STOP] Fermato dall'utente")
    except Exception as e:
        print(f"[ERROR] Errore: {e}")
        
    print("[DONE] Producer terminato")

if __name__ == "__main__":
    main()
