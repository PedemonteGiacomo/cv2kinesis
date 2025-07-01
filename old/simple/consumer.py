"""
Consumer: Legge frames da Kinesis e fa object detection con YOLO
Mostra log dettagliati delle detection trovate
"""
import logging
import cv2 as cv
import numpy as np
import time

# Patch per PyTorch weights_only issue
import torch
original_load = torch.load
def patched_load(f, map_location=None, pickle_module=None, weights_only=None, **kwargs):
    return original_load(f, map_location=map_location, pickle_module=pickle_module, weights_only=False, **kwargs)
torch.load = patched_load

from ultralytics import YOLO
from aws_service import get_kinesis_client
from settings import KINESIS_STREAM_NAME, YOLO_MODEL, THRESHOLD, YOLO_CLASSES_TO_DETECT

# Configurazione logging
logging.getLogger("ultralytics").setLevel(logging.WARNING)
logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(message)s',
    level='INFO',
    datefmt='%d/%m/%Y %X'
)
logger = logging.getLogger(__name__)

def run_consumer():
    """Avvia il consumer che legge da Kinesis e fa detection"""
    logger.info(f"🔍 Avvio Consumer: Kinesis={KINESIS_STREAM_NAME} → YOLO Detection")
    logger.info(f"🎯 Oggetti da rilevare: {', '.join(YOLO_CLASSES_TO_DETECT)}")
    logger.info(f"📊 Soglia confidenza: {THRESHOLD}")
    
    # Inizializza servizi
    kinesis = get_kinesis_client()
    model = YOLO(YOLO_MODEL)
    logger.info("✅ Modello YOLO caricato con successo")
    
    # Ottieni informazioni sullo stream
    response = kinesis.describe_stream(StreamName=KINESIS_STREAM_NAME)
    shard_id = response['StreamDescription']['Shards'][0]['ShardId']
    logger.info(f"📡 Connesso allo stream Kinesis (Shard: {shard_id})")
    
    frame_count = 0
    detection_count = 0
    
    try:
        while True:
            # Leggi records da Kinesis
            shard_iterator_response = kinesis.get_shard_iterator(
                StreamName=KINESIS_STREAM_NAME,
                ShardId=shard_id,
                ShardIteratorType='LATEST'
            )
            shard_iterator = shard_iterator_response['ShardIterator']
            response = kinesis.get_records(
                ShardIterator=shard_iterator,
                Limit=10
            )
            
            if response['Records']:
                logger.info(f"📥 Ricevuti {len(response['Records'])} frames da Kinesis")
            
            # Processa ogni frame
            for record in response['Records']:
                frame_count += 1
                image_data = record['Data']
                frame = cv.imdecode(np.frombuffer(image_data, np.uint8), cv.IMREAD_COLOR)
                
                if frame is not None:
                    # Fai detection con YOLO
                    results = model.predict(frame, verbose=False)
                    
                    # Analizza i risultati
                    frame_detections = []
                    for result in results:
                        if result.boxes is not None:
                            for box in result.boxes:
                                class_id = result.names[box.cls[0].item()]
                                probability = round(box.conf[0].item(), 2)
                                
                                # Controlla se è un oggetto che stiamo cercando
                                if probability > THRESHOLD and class_id in YOLO_CLASSES_TO_DETECT:
                                    detection_count += 1
                                    frame_detections.append(f"{class_id} ({round(probability * 100)}%)")
                    
                    # Log delle detection
                    if frame_detections:
                        logger.info(f"🎯 DETECTED in frame {frame_count}: {', '.join(frame_detections)}")
                    
                else:
                    logger.error(f"❌ Errore nel decodificare frame {frame_count}")
            
            # Piccola pausa per non sovraccaricare
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        logger.info("🛑 Interrotto dall'utente (Ctrl+C)")
    except Exception as e:
        logger.error(f"❌ Errore: {e}")
    finally:
        logger.info(f"📊 Statistiche finali:")
        logger.info(f"   - Frame processati: {frame_count}")
        logger.info(f"   - Detection totali: {detection_count}")
        logger.info("🔚 Consumer terminato")

if __name__ == '__main__':
    run_consumer()
