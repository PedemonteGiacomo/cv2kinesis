#!/usr/bin/env python3
"""
SQS Consumer con Timeout per Test Rapidi
Versione limitata nel tempo per testing
"""

import boto3
import json
import time
import logging
import signal
import sys
from typing import Dict, Any

logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(message)s',
    level=logging.INFO,
    datefmt='%d/%m/%Y %X'
)
logger = logging.getLogger(__name__)

class TimeoutSQSConsumer:
    def __init__(self, queue_url: str, region: str = 'eu-central-1', timeout_seconds: int = 30):
        self.queue_url = queue_url
        self.region = region
        self.timeout_seconds = timeout_seconds
        self.sqs = boto3.client('sqs', region_name=region)
        self.start_time = time.time()
        self.message_count = 0
        self.running = True
        
        # Setup signal handler for Ctrl+C
        signal.signal(signal.SIGINT, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully"""
        logger.info("\nInterrotto dall'utente")
        self.running = False
    
    def is_timeout_reached(self):
        """Check if timeout is reached"""
        elapsed = time.time() - self.start_time
        return elapsed >= self.timeout_seconds
    
    def poll_messages_with_timeout(self):
        """Poll SQS for messages with timeout"""
        logger.info(f"Polling SQS queue per {self.timeout_seconds} secondi...")
        logger.info(f"Queue: {self.queue_url}")
        logger.info("Premi Ctrl+C per interrompere in anticipo\n")
        
        while self.running and not self.is_timeout_reached():
            try:
                elapsed = time.time() - self.start_time
                remaining = self.timeout_seconds - elapsed
                
                if remaining <= 0:
                    break
                
                # Use shorter wait time if close to timeout
                wait_time = min(5, int(remaining))
                
                response = self.sqs.receive_message(
                    QueueUrl=self.queue_url,
                    MaxNumberOfMessages=3,  # Fewer messages per batch
                    WaitTimeSeconds=wait_time,
                    MessageAttributeNames=['All']
                )
                
                messages = response.get('Messages', [])
                
                if not messages:
                    logger.info(f"Nessun messaggio ricevuto (tempo rimanente: {remaining:.1f}s)")
                    continue
                
                logger.info(f"Ricevuti {len(messages)} messaggi")
                
                for message in messages:
                    self.process_message(message)
                    self.message_count += 1
                    
                    if not self.running or self.is_timeout_reached():
                        break
                        
            except Exception as e:
                logger.error(f"Errore polling SQS: {e}")
                time.sleep(2)
        
        # Final summary
        elapsed = time.time() - self.start_time
        logger.info(f"\n" + "="*60)
        logger.info(f"TEST COMPLETATO")
        logger.info(f"="*60)
        logger.info(f"Tempo totale: {elapsed:.1f} secondi")
        logger.info(f"Messaggi processati: {self.message_count}")
        
        if self.message_count > 0:
            logger.info(f"SUCCESSO: Backend processor sta funzionando!")
            logger.info(f"Il tuo frontend ricevera questi messaggi JSON via SQS")
        else:
            logger.info(f"Nessun messaggio ricevuto. Possibili cause:")
            logger.info(f"- Nessun video in streaming al momento")
            logger.info(f"- Backend processor non attivo")
            logger.info(f"- Credenziali AWS non configurate")

    def process_message(self, message: Dict[str, Any]):
        """Process a single SQS message"""
        try:
            body = json.loads(message['Body'])
            receipt_handle = message['ReceiptHandle']
            
            logger.info("\n" + "-"*50)
            logger.info("MESSAGGIO DAL BACKEND PROCESSOR")
            logger.info("-"*50)
            
            # Log key info only
            logger.info(f"Frame: {body.get('frame_index', 'N/A')}")
            logger.info(f"Detections: {body.get('detections_count', 0)}")
            logger.info(f"Stream: {body.get('stream_name', 'N/A')}")
            logger.info(f"Timestamp: {body.get('timestamp', 'N/A')}")
            
            # Log first few detections
            summary = body.get('summary', [])
            if summary:
                logger.info(f"Oggetti rilevati:")
                for i, detection in enumerate(summary[:3], 1):  # Show only first 3
                    logger.info(f"  {i}. {detection.get('class', 'unknown')} "
                              f"(conf: {detection.get('conf', 0):.2f})")
                if len(summary) > 3:
                    logger.info(f"  ... e altri {len(summary) - 3} oggetti")
            
            # Delete message from queue
            self.sqs.delete_message(
                QueueUrl=self.queue_url,
                ReceiptHandle=receipt_handle
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Errore parsing JSON: {e}")
        except Exception as e:
            logger.error(f"Errore processing messaggio: {e}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python quick_sqs_test.py <SQS_QUEUE_URL> [timeout_seconds]")
        print("\nExample:")
        print("python quick_sqs_test.py https://sqs.eu-central-1.amazonaws.com/123456789/processing-results 30")
        sys.exit(1)
    
    queue_url = sys.argv[1]
    timeout_seconds = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    
    logger.info("QUICK SQS TEST PER FRONTEND INTEGRATION")
    logger.info("="*50)
    
    consumer = TimeoutSQSConsumer(queue_url, timeout_seconds=timeout_seconds)
    
    try:
        consumer.poll_messages_with_timeout()
    except Exception as e:
        logger.error(f"Errore fatale: {e}")

if __name__ == "__main__":
    main()
