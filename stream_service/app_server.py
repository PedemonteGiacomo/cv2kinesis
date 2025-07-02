"""
WSGI wrapper: avvia il consumer EFO in un processo figlio
e offre /health a 8080 per l'ALB
"""
import multiprocessing as mp
from flask import Flask
from app import main as consumer_main   # <-- il tuo file consumer rimane "app.py"

# parte il consumer in background
p = mp.Process(target=consumer_main, daemon=True)
p.start()

# piccola app HTTP solo per health-check
flask_app = Flask(__name__)

@flask_app.route("/health")
def health():
    return "OK", 200
