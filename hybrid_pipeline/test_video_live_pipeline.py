"""
Test end-to-end VIDEO PIPELINE (live):
- Avvia producer webcam → Kinesis
- Mostra finestra live con video
- Apre browser sul servizio stream per vedere i frame processati
"""
import subprocess
import sys
import os
import time
import webbrowser

def run_producer():
    print("\n🎥 Avvio producer webcam → Kinesis...")
    # Avvia producer in un processo separato
    proc = subprocess.Popen([sys.executable, "producer.py"], cwd=os.path.join("..", "video-processing", "producer_and_consumer_examples"))
    return proc

def open_stream_service(url):
    print(f"\n🌐 Apro il servizio stream: {url}")
    webbrowser.open(url)

def main():
    print("\n=== TEST LIVE VIDEO PIPELINE ===")
    print("Questo test avvia il producer (webcam → Kinesis) e apre il browser sul servizio di stream per vedere i frame processati in tempo reale.")
    print("Premi Ctrl+C per terminare il test.")

    # URL del servizio stream (puoi modificarlo se necessario)
    stream_url = os.environ.get("VIDEO_STREAM_URL") or input("URL servizio stream (es. http://localhost:8080): ")

    # Avvia producer
    proc = run_producer()
    time.sleep(5)  # Attendi che il producer inizi a inviare

    # Apri browser sul servizio stream
    open_stream_service(stream_url)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Test terminato dall'utente. Chiudo producer...")
        proc.terminate()
        proc.wait()
        print("🔚 Producer chiuso. Test completato.")

if __name__ == "__main__":
    main()
