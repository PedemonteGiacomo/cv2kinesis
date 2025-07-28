# Image Processing Pipeline

Questa repository contiene i container, la logica e l'infrastruttura per una pipeline di image processing event-driven su AWS.

## Architettura aggiornata

**Client → API Gateway → Lambda Router → SQS → Fargate → SNS → SQS Results → Proxy Lambda → Frontend**

Il client invia una richiesta HTTP POST a `/process/{algo_id}` su API Gateway. La Lambda "router" valida e inoltra il job sulla coda SQS corretta. I worker Fargate processano i job e pubblicano il risultato su SNS, che recapita solo al client giusto tramite SQS FIFO. Il frontend React polla la coda via Lambda proxy HTTP.

---

## Checklist End-to-End

### A. Preparazione ECR

1. Crea i repo ECR
   ```powershell
   cd infra/ecr
   .\create-ecr-repos.ps1 -Region us-east-1 -Account 544547773663
   .\push_algos.ps1 -Region us-east-1 -Account 544547773663
   .\push_pacs.ps1 -Region us-east-1 -Account 544547773663
   ```
1. Build & Push PACS‑API (IF NOT USING THE PUSH POWERHSELL SCRIPT)
   ```powershell
   cd ../../pacs_api
   docker build -t mip-pacs-api -f .
   docker tag mip-pacs-api 544547773663.dkr.ecr.eu-central-1.amazonaws.com/pacs-ecr:latest
   docker push    544547773663.dkr.ecr.eu-central-1.amazonaws.com/pacs-ecr:latest
   ```
3. Build & Push Algos
   ```powershell
   cd ..
   docker build -t mip-base:latest -f containers/base/Dockerfile .
   docker build -t mip-processing_1 -f containers/processing_1/Dockerfile .
   docker build -t mip-processing_6 -f containers/processing_6/Dockerfile .
   docker tag mip-processing_1  544547773663.dkr.ecr.eu-central-1.amazonaws.com/mip-algos:processing_1
   docker tag mip-processing_6  544547773663.dkr.ecr.eu-central-1.amazonaws.com/mip-algos:processing_6
   docker push 544547773663.dkr.ecr.eu-central-1.amazonaws.com/mip-algos:processing_1
   docker push 544547773663.dkr.ecr.eu-central-1.amazonaws.com/mip-algos:processing_6
   ```

### B. Deploy CDK

1. Installa le dipendenze CDK se serve
2. Deploy Imports + PACS‑API + ImagePipeline
   ```bash
    cd ..
    # assicurati di essere dentro /infra
    cdk deploy Imports      --require-approval never
    cdk deploy PacsApi      --require-approval never
    cdk deploy ImgPipeline  --require-approval never
    # oppure più semplicemente:
    cdk deploy --all
   ```
3. Al termine avrai:
   - DNS del PACS‑API LB (output PacsApi)
   - URL di tutte le code SQS (output ImgPipeline)
   - ARN del topic SNS “ImageResultsTopic”

4. Verifica variabili ambiente Lambda/container:
   - ProvisionFunction: `RESULTS_TOPIC_ARN`
   - RouterFunction: `QUEUE_URLS_JSON`, `RESULT_URLS_JSON`
   - Fargate: `PACS_API_BASE`, `PACS_API_KEY`

### C. Frontend React

1. Modifica in `infra/clients/react-app/src/index.jsx`:
   ```js
   const API_BASE  = '<YOUR_API_GATEWAY_BASE>';
   const PACS_BASE = 'http://<YOUR_PACS_LOAD_BALANCER_DNS>';
   ```
2. Installa e avvia:
   ```bash
   npm ci
   npm start
   ```
3. Apri [http://localhost:3000](http://localhost:3000)

### D. Flusso di prova

1. **Anteprima PACS**
   - Inserisci `study_id`, `series_id`, `image_id`, `scope=image`
   - Clicca “Carica Anteprima” → vedi l’immagine originale
2. **Provisiona la coda**
   - Clicca “Provisiona coda” → ottieni `client_id` e `queue_url`
3. **Avvia processing**
   - Clicca “Avvia processing” (invio `/process/processing_1` con payload PACS + callback.client_id)
   - Lambda router sposta su SQS → worker Fargate processa e pubblica su SNS con MessageAttribute.client_id
   - SNS recapita solo alla coda FIFO del client (filter policy)
   - Proxy-SQS Lambda espone `/proxy-sqs?queue=<url>`
   - Frontend fa polling → quando arriva il messaggio giusto, mostra l’url dell’immagine processata

---

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
