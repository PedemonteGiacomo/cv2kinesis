"""
Producer: Cattura video dalla webcam e lo invia a Kinesis Data Stream
Mostra una finestra live con il video della webcam
usato in DEPLOY_AND_TEST per testare il pipeline
"""
import logging
import cv2 as cv

# Patch per PyTorch weights_only issue
import torch
original_load = torch.load
def patched_load(f, map_location=None, pickle_module=None, weights_only=None, **kwargs):
    return original_load(f, map_location=map_location, pickle_module=pickle_module, weights_only=False, **kwargs)
torch.load = patched_load

from aws_service import get_kinesis_client
from settings import CAM_URI, WIDTH
import os

# Configurazione logging
logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(message)s',
    level='INFO',
    datefmt='%d/%m/%Y %X'
)
logger = logging.getLogger(__name__)

def run_producer():
    """Avvia il producer che cattura dalla webcam e invia a Kinesis"""
    # Stream name da variabile d'ambiente o default
    kinesis_stream_name = os.environ.get('KINESIS_STREAM_NAME', 'cv2kinesis')
    
    logger.info(f"🎥 Avvio Producer: webcam={CAM_URI} → Kinesis={kinesis_stream_name}")
    
    # Inizializza servizi
    kinesis = get_kinesis_client()
    print(f"✅ Connesso a Kinesis Data Stream: {kinesis_stream_name}, regione={kinesis.meta.region_name}")
    cap = cv.VideoCapture(CAM_URI)
    
    if not cap.isOpened():
        logger.error("❌ Impossibile aprire la webcam")
        return
    
    logger.info("✅ Webcam aperta con successo")
    logger.info("📺 Finestra video aperta - Premi 'q' per uscire")
    
    try:
        frame_count = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                logger.error("❌ Errore nella lettura del frame dalla webcam")
                break
            
            frame_count += 1
            
            # Ridimensiona il frame per Kinesis
            scale = WIDTH / frame.shape[1]
            height = int(frame.shape[0] * scale)
            scaled_frame = cv.resize(frame, (WIDTH, height))
            
            # Mostra il frame live
            cv.imshow("🎥 Producer - Webcam Live (Premi 'q' per uscire)", frame)
            
            # Codifica e invia a Kinesis
            _, img_encoded = cv.imencode('.jpg', scaled_frame)
            kinesis.put_record(
                StreamName=kinesis_stream_name,
                Data=img_encoded.tobytes(),
                PartitionKey='1'
            )
            
            if frame_count % 30 == 0:  # Log ogni 30 frames (circa 1 secondo)
                logger.info(f"📤 Frame {frame_count} inviato a Kinesis")
            
            # Esci con 'q'
            if cv.waitKey(1) & 0xFF == ord('q'):
                logger.info("🛑 Uscita richiesta dall'utente")
                break
                
    except KeyboardInterrupt:
        logger.info("🛑 Interrotto dall'utente (Ctrl+C)")
    except Exception as e:
        logger.error(f"❌ Errore: {e}")
    finally:
        cap.release()
        cv.destroyAllWindows()
        logger.info("🔚 Producer terminato")

if __name__ == '__main__':
    run_producer()
