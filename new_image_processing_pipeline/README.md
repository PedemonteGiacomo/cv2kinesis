
# Image Processing Pipeline

Questa repository contiene i container, la logica e l'infrastruttura per una pipeline di image processing event-driven su AWS.

## Architettura aggiornata

**Client → API Gateway → Lambda Router → SQS → Fargate → SQS Results**

Il client invia una richiesta HTTP POST a `/process/{algo_id}` su API Gateway. La Lambda "router" valida e inoltra il job sulla coda SQS corretta. I worker Fargate processano i job e scrivono i risultati su SQS.

### Esempio di richiesta

```http
POST https://<api_id>.execute-api.<region>.amazonaws.com/prod/process/processing_6
Content-Type: application/json

{
  "job_id": "uuid4",
  "pacs": {"study_id": "1.2.3", "series_id": "4.5.6", "image_id": "7.8.9", "scope": "image"},
  "callback": {"queue_url": "https://sqs.eu-central-1.amazonaws.com/123456/ImageResults.fifo"}
}
```

Risposta:

```json
{
  "message": "Enqueued",
  "sqs_message_id": "..."
}
```

## Build & Deploy

Consulta `infra/README.md` per la procedura aggiornata di build, push su ECR e deploy CDK.

## Script client di esempio

Vedi `infra/clients/send-http-job.ps1` per inviare job via PowerShell.

## PACS simulator

```bash
docker build -t pacs-sim pacs_api_sim
docker run -p 8000:8000 -e AWS_ACCESS_KEY_ID=... -e AWS_SECRET_ACCESS_KEY=... pacs-sim
```

## Note
- I worker Fargate non leggono più direttamente da SQS, ma ricevono job inoltrati dalla Lambda router.
- Per estendere la pipeline o aggiungere algoritmi, consulta `src/medical_image_processing/README.md`.
