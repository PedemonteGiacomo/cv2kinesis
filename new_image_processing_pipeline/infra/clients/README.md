# Flusso completo client: ricezione risultati via SNS + SQS

## 1. Deploy della coda SQS del client e subscription SNS

Modifica `infra/client_stack.py` per creare la tua coda SQS e sottoscriverla al topic SNS con filter policy su `client_id`.

Esempio:
```python
from aws_cdk import (
    Stack,
    aws_sqs as sqs,
    aws_sns as sns,
    aws_sns_subscriptions as subs,
)
from constructs import Construct

class ClientResultsStack(Stack):
    def __init__(self, scope: Construct, id: str, client_id: str, topic_arn: str, **kw):
        super().__init__(scope, id, **kw)
        topic = sns.Topic.from_topic_arn(self, "ImageResultsTopic", topic_arn)
        queue = sqs.Queue(self, "ClientResultsQueue",
            queue_name=f"{client_id}Results.fifo",
            fifo=True,
            content_based_deduplication=True
        )
        topic.add_subscription(subs.SqsSubscription(
            queue,
            filter_policy={
                "client_id": sns.SubscriptionFilter.string_filter(allowlist=[client_id])
            }
        ))
        from aws_cdk import CfnOutput
        CfnOutput(self, "ClientResultsQueueUrl", value=queue.queue_url)
        CfnOutput(self, "ClientResultsQueueArn", value=queue.queue_arn)
```

## Come lanciare lo stack client e testare il flusso

### 1. Deploy della coda SQS del client e subscription SNS

Apri un terminale nella cartella `infra/clients` e lancia:

```powershell
cd infra/clients
cdk deploy --app "python app.py my-client-123 arn:aws:sns:eu-central-1:123456789012:ImageResultsTopic" --require-approval never
```

- Sostituisci `my-client-123` con il tuo client_id.
- Sostituisci l'ARN con quello reale del topic SNS (lo trovi negli output CloudFormation del deploy principale).

Negli output troverai l'URL della tua coda SQS dedicata.

---

### 2. Invio job HTTP con client_id

Usa lo script PowerShell `send-http-job.ps1`:

```powershell
cd infra/clients
.\send-http-job.ps1 -Region eu-central-1 -ApiEndpoint https://<api_id>.execute-api.eu-central-1.amazonaws.com/prod -ClientId my-client-123
```

Il campo `callback.client_id` identifica la tua coda per la ricezione del risultato.

---

### 3. Ricezione risultati

### Opzione 1: AWS CLI

Leggi i messaggi dalla tua coda SQS (es: `my-client-123Results.fifo`):

```powershell
aws sqs receive-message --queue-url <ClientResultsQueueUrl> --max-number-of-messages 1
```

### Opzione 2: HTTP via Lambda proxy-sqs (consigliato per frontend)

Chiama l'endpoint HTTP del tuo API Gateway:

```http
GET https://<api_id>.execute-api.eu-central-1.amazonaws.com/prod/proxy-sqs?queue=<ClientResultsQueueUrl>
```

Risposta: array di messaggi (già cancellati dalla coda).

Esempio in React:
```js
const res = await fetch(`${API_BASE}/proxy-sqs?queue=${encodeURIComponent(queueUrl)}`);
const msgs = await res.json();
```

Ogni messaggio contiene:
- `job_id`, `algo_id`, `dicom` (bucket, key, url)

Solo i job con il tuo `client_id` arrivano sulla tua coda, in ordine FIFO per job.

---

**Vantaggi:**
- Ogni client riceve solo i propri risultati.
- Nessun rischio di consumare job altrui.
- Scalabilità e isolamento garantiti.
- Accesso HTTP puro, ideale per frontend/browser.

## 2. Invio job HTTP con client_id

Usa lo script PowerShell `send-http-job.ps1`:

```powershell
param(
  [string] $Region = "eu-central-1",
  [string] $ApiEndpoint,  # es: https://xyz.execute-api.eu-central-1.amazonaws.com/prod
  [string] $ClientId      # es: my-client-123
)

$algo = "processing_1"
$body = @{
  job_id = [guid]::NewGuid().ToString()
  pacs = @{
    study_id  = "liver1/phantomx_abdomen_pelvis_dataset/D55-01"
    series_id = "300/AiCE_BODY-SHARP_300_172938.900"
    image_id  = "IM-0135-0001.dcm"
    scope     = "image"
  }
  callback = @{ client_id = $ClientId }
} | ConvertTo-Json -Depth 4

Invoke-RestMethod -Uri "$ApiEndpoint/process/$algo" `
  -Method POST `
  -Body $body `
  -ContentType "application/json"
```

## 3. Ricezione risultati

Leggi i messaggi dalla tua coda SQS (es: `my-client-123Results.fifo`).

Ogni messaggio contiene:
- `job_id`, `algo_id`, `dicom` (bucket, key, url)

Solo i job con il tuo `client_id` arrivano sulla tua coda, in ordine FIFO per job.

---

**Vantaggi:**
- Ogni client riceve solo i propri risultati.
- Nessun rischio di consumare job altrui.
- Scalabilità e isolamento garantiti.
