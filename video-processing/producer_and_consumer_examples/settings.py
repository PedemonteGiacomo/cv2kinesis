import os
from pathlib import Path
from dotenv import load_dotenv

# Carica le variabili d'ambiente
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=BASE_DIR / '.env')

# Configurazione AWS
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.getenv('AWS_REGION', 'eu-central-1')

# Configurazione Kinesis
KINESIS_STREAM_NAME = 'cv2kinesis-hybrid'

# Configurazione Webcam
CAM_URI = 0  # Webcam predefinita
WIDTH = 640  # Larghezza frame per Kinesis

# Configurazione YOLO
YOLO_MODEL = "yolov8n.pt"
YOLO_CLASSES_TO_DETECT = ('bottle', 'cup', 'laptop', 'cell phone', 'person', 'book', 'chair')
THRESHOLD = 0.80
