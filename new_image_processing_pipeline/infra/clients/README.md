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
