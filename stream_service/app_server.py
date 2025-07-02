"""
WSGI wrapper:
  • avvia il consumer EFO in un processo figlio (NON daemonic)
  • espone /health per l’ALB
"""
import multiprocessing as mp
import signal, sys
from flask import Flask
from app import main as consumer_main          # il tuo consumer resta in app.py

# usiamo lo spawn esplicito per compatibilità cross-OS
ctx = mp.get_context("spawn")
consumer_proc = ctx.Process(target=consumer_main)   # ← niente daemon
consumer_proc.start()

# terminazione pulita quando Docker invia SIGTERM
def _shutdown(*_):
    if consumer_proc.is_alive():
        consumer_proc.terminate()
        consumer_proc.join()
    sys.exit(0)

for sig in (signal.SIGINT, signal.SIGTERM):
    signal.signal(sig, _shutdown)

flask_app = Flask(__name__)

@flask_app.route("/health")
def health():
    return "OK", 200
