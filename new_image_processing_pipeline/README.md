## 🏗️ Architettura

```
Client → API REST → SQS Requests → Fargate → SQS Results.fifo → Lambda ResultPush → WebSocket API → Client
```

- **Client**: invia job via HTTP
- **API Gateway**: espone endpoint REST
- **Lambda Router**: valida e smista i job
- **SQS Requests**: code FIFO per ogni algoritmo
- **Fargate Workers**: processano i job
- **SQS Results.fifo**: coda FIFO unica per tutti i risultati
- **Lambda ResultPush**: invia i risultati via WebSocket
- **WebSocket API**: notifiche push dei risultati ai client
- **Frontend React**: provisioning, invio job, ricezione risultati real-time

---

## 5️⃣ Flusso utente end‑to‑end

1. **Anteprima PACS**
   - Inserisci `study_id`, `series_id`, `image_id`, `scope=image`
   - Clicca _Carica Anteprima_ → visualizzi l’immagine originale
2. **Provision client**
   - Clicca _Provisiona client_ → ricevi solo `client_id`
3. **Avvio processing**
   - Clicca _Avvia processing_ → invia POST a `$API_BASE/process/processing_1` con payload PACS + `client_id`
   - Lambda Router mette il job su SQS Requests
   - Fargate Worker elabora e pubblica su ResultsQueue.fifo
   - Lambda ResultPush invia il risultato via WebSocket al client giusto
4. **Ricezione risultati (push)**
   - Il frontend apre una WebSocket a `wss://.../prod?client_id=...`
   - Quando arriva il messaggio (`job_id`), vedi l’immagine processata

---

## Output deploy

- DNS PACS API LB (`PacsApiLB`)
- API Gateway endpoint (`ProcessingApiEndpoint`)
- URL SQS Requests per ogni algoritmo
- WebSocket endpoint (`WebSocketEndpoint`)
- ResultsQueueUrl (`ResultsQueueUrl`)

**Variabili disponibili:**
- `$Env:API_BASE`         → API Gateway
- `$Env:PACS_API_BASE`    → DNS PACS API
- `$Env:WS_ENDPOINT`      → WebSocket endpoint
- `$Env:RESULTS_QUEUE_URL`→ ResultsQueueUrl

---

## Flusso architetturale (aggiornato)

```mermaid
graph LR
    subgraph Frontend
        FE[Frontend]
    end
    subgraph API
        APIPACS[PacsApi (LoadBalancer + Service)]
    end
    subgraph Imports
        PACSB[Pacs S3 Bucket (esistente)]
    end
    subgraph Pipeline[Image Processing Pipeline]
        PIPE[ImgPipeline (ECS Cluster + Tasks)]
        ALGOS[AlgosRepo (ECR)]
        OUTPUT[Output S3 Bucket]
        ROUTER[RouterFunction (Lambda)]
        PROVISION[ProvisionFunction (Lambda)]
        PROCAPI[ProcessingApi (API Gateway)]
        WSAPI[WebSocket API]
        RESULTSQ[ResultsQueue.fifo]
        RESULTPUSH[ResultPushFn (Lambda)]
    end

    FE-->|Richiesta immagine/processamento|APIPACS
    APIPACS-->|Recupera da|PACSB
    APIPACS-->|Invoca pipeline|PIPE
    PIPE-->|Scarica algoritmi|ALGOS
    PIPE-->|Scrive risultati|OUTPUT
    PIPE-->|Invoca|PROCAPI
    PROCAPI-->|Gestisce routing|ROUTER
    PROCAPI-->|Provisioning|PROVISION
    ROUTER-->|Smista richieste|PIPE
    PROVISION-->|Provisiona risorse|PIPE
    PIPE-->|Scrive su|RESULTSQ
    RESULTSQ-->|Trigger|RESULTPUSH
    RESULTPUSH-->|Push via WS|WSAPI
    WSAPI-->|Notifica|FE
```

---

## Best practice e monitoraggio

- Lambda on_disconnect: fail fast (retry 0), return 200 se nessun item trovato.
- Lambda result_push: logging avanzato e metriche CloudWatch EMF per push, failure e disconnect.
- Lambda push: batch/concurrency SQS, Lambda Insights, retention log 1 giorno.
- Frontend: reconnessione WebSocket automatica, ping ogni 5 min, fallback toast se non parte.
- Monitoring: ApproximateAgeOfOldestMessage su ResultsQueue, allarmi su PushFailures/Disconnected.