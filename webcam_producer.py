#!/usr/bin/env python3
"""
Producer semplificato per test del pipeline
Invia video dalla webcam al sistema AWS
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from lib.video import kinesis_producer
from settings import STREAM_NAME

def main():
    print("📹 PRODUCER SEMPLIFICATO")
    print("=" * 50)
    print("Invio video al pipeline AWS...")
    print("Premi Ctrl+C per fermare")
    print()
    
    try:
        # Usa webcam (source=0) per 60 secondi
        kinesis_producer(
            stream_name=STREAM_NAME,
            source=0,  # Webcam
            duration=60  # 60 secondi
        )
    except KeyboardInterrupt:
        print("\n[STOP] Producer fermato dall'utente")
    except Exception as e:
        print(f"[ERROR] Errore nel producer: {e}")

if __name__ == "__main__":
    main()
