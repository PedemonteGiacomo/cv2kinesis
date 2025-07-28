# Frontend React di test per provisioning, PACS preview e processing

## Setup

1. Installa le dipendenze:
   ```bash
   npm ci --prefix infra/clients/react-app
   ```
2. Avvia il frontend:
   ```bash
   npm start --prefix infra/clients/react-app
   ```
3. Imposta le variabili in `src/index.jsx`:
   ```js
   const API_BASE   = '<YOUR_API_GATEWAY_BASE>';  // es: https://xyz.execute-api.eu-central-1.amazonaws.com/prod
   const PACS_BASE  = '<YOUR_PACS_API_BASE>';     // es: https://abc-123.eu-central-1.elb.amazonaws.com
   ```
4. Apri [http://localhost:3000](http://localhost:3000) nel browser.

## Flusso end-to-end

1. **Compila i parametri PACS**: Inserisci `study_id`, `series_id`, `image_id`, `scope` nel form.
2. **Carica anteprima**: Clicca "Carica Anteprima" per ottenere il presigned URL dal PACS API e visualizzare l'immagine originale.
3. **Provisiona la coda**: Clicca "Provisiona coda" per creare la coda SQS e la subscription SNS per il tuo client. Ricevi `client_id` e `queue_url`.
4. **Avvia processing**: Clicca "Avvia processing" per inviare il job con i parametri PACS e il tuo `client_id`.
5. **Polling risultati**: Il frontend pollerà `/proxy-sqs?queue=<queue_url>` finché arriva il risultato.
6. **Visualizza risultato**: Appare direttamente l'immagine processata.

### Esempio polling React
```js
async function pollResult(jid) {
  while(true) {
    const sqsRes = await fetch(
      `${API_BASE}/proxy-sqs?queue=${encodeURIComponent(queueUrl)}`
    );
    const msgs = await sqsRes.json();
    const found = msgs.find(m=>m.job_id===jid);
    if(found) {
      setResult(found);
      setStatus('done');
      return;
    }
    await new Promise(r=>setTimeout(r,2000));
  }
}
```

## Abilita CORS su PACS API

Nel tuo `app.py` FastAPI aggiungi:
```python
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```
Ricostruisci e ridistribuisci il container PACS API:
```bash
docker build -t mip-pacs-api -f pacs_api/Dockerfile .
# push su ECR e deploy PacsApiStack
```

## Deploy & test

1. Aggiorna PACS-API container & deploy:
   ```bash
   cd new_image_processing_pipeline
   docker build -t mip-pacs-api -f pacs_api/Dockerfile .
   # push su ECR e:
   cd infra
   cdk deploy PacsApiStack --require-approval never
   ```
2. Deploy pipeline e lambda:
   ```bash
   cd infra
   cdk deploy ImgPipeline --require-approval never
   ```
3. Frontend React:
   ```bash
   cd infra/clients/react-app
   npm ci
   npm start
   ```

## Flusso utente

- Compila i campi PACS e clicca Carica Anteprima → vedi l’immagine originale
- Provisiona coda → ottieni client_id e queue_url
- Avvia processing → parte il job su SQS/Fargate
- Vedi il loader “In attesa…” poi, al termine, appare direttamente l’immagine processata
