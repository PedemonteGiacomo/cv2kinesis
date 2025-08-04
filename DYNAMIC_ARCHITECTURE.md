# 🔧 Architettura Dinamica - Registro Algoritmi

Questo documento descrive la nuova architettura dinamica con registro DynamoDB per la gestione degli algoritmi.

## 🎯 Cosa è cambiato

### Prima (Architettura Statica)
- Algoritmi hardcoded nel CDK (`processing_1`, `processing_6`)
- Code SQS, TaskDefinition e Service ECS creati a priori
- Modifiche richiedevano redeploy CDK completo

### Dopo (Architettura Dinamica)
- ✅ **DynamoDB Registry** come source of truth
- ✅ **API Admin** per gestire algoritmi at runtime
- ✅ **Provisioner Lambda** per creare risorse on-demand
- ✅ **Dynamic Router** che legge dal registro
- ✅ **Supporto Python + OpenMP/nativi**

## 🏗️ Componenti Principali

### 1. Algorithm Registry (DynamoDB)
Tabella che memorizza:
```json
{
  "algorithm_id": "processing_1",
  "status": "ACTIVE",
  "image_uri": "123456789.dkr.ecr.us-east-1.amazonaws.com/mip-algos:processing_1", 
  "cpu": 1024,
  "memory": 2048,
  "desired_count": 1,
  "command": ["/app/worker.sh"],
  "env": {"EXTRA_DEBUG": "1"},
  "resource_status": {
    "queue_url": "https://sqs...",
    "task_definition": "arn:aws:ecs...",
    "service": "mip-processing_1"
  }
}
```

### 2. API Admin (Lambda)
Endpoint protetti con header `x-admin-key`:

```bash
# Registra nuovo algoritmo
POST /admin/algorithms
{
  "algo_id": "my_algo",
  "image_uri": "...",
  "cpu": 1024,
  "memory": 2048,
  "command": ["/app/adapter.py"]
}

# Lista algoritmi
GET /admin/algorithms

# Dettagli specifico algoritmo  
GET /admin/algorithms/{algo_id}

# Aggiorna algoritmo
PATCH /admin/algorithms/{algo_id}
{"cpu": 2048, "memory": 4096}

# Scale down (desired_count=0)
DELETE /admin/algorithms/{algo_id}

# Hard delete (rimuove servizio)
DELETE /admin/algorithms/{algo_id}?hard=true
```

### 3. Provisioner Lambda
Crea/aggiorna automaticamente:
- Coda SQS FIFO per l'algoritmo
- TaskDefinition ECS
- Service Fargate
- Permessi IAM
- Log groups CloudWatch

### 4. Dynamic Router
Sostituisce il router statico:
- Legge dal registry DynamoDB
- Verifica che l'algoritmo sia `ACTIVE`
- Mette il job nella coda giusta

## 🚀 Come usare

### Deploy iniziale
```powershell
cd infra
.\deploy-complete.ps1 -Region us-east-1 -Account 123456789
```

### Registrare algoritmo Python
```bash
curl -X POST "$API_BASE/admin/algorithms" \
  -H "Content-Type: application/json" \
  -H "x-admin-key: dev-admin" \
  -d '{
    "algo_id": "processing_1",
    "image_uri": "123456789.dkr.ecr.us-east-1.amazonaws.com/mip-algos:processing_1",
    "cpu": 1024,
    "memory": 2048,
    "command": ["/app/worker.sh"]
  }'
```

### Registrare algoritmo OpenMP
```bash
curl -X POST "$API_BASE/admin/algorithms" \
  -H "Content-Type: application/json" \
  -H "x-admin-key: dev-admin" \
  -d '{
    "algo_id": "grayscale_cpp", 
    "image_uri": "123456789.dkr.ecr.us-east-1.amazonaws.com/mip-algos:grayscale",
    "cpu": 2048,
    "memory": 4096,
    "command": ["/app/adapter.py"],
    "env": {"OMP_NUM_THREADS": "4"}
  }'
```

### Invocare algoritmo (invariato)
```bash
curl -X POST "$API_BASE/process/processing_1" \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "test-123",
    "client_id": "client-456", 
    "pacs": {
      "study_id": "study-1",
      "series_id": "series-1",
      "image_id": "image-1",
      "scope": "image"
    }
  }'
```

## 🐍 Algoritmi Python (Esistenti)

Continuano a funzionare senza modifiche:
- Usano immagine base `mip-base`
- Entry point: `["/app/worker.sh"]`
- Algoritmo in `src/medical_image_processing/processing/`

## ⚡ Algoritmi OpenMP/Nativi (Nuovi)

### Struttura del container
```dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y gcc g++ libgomp1
COPY adapter.py /app/adapter.py
COPY bin/my_openmp /app/bin/my_openmp
RUN pip install boto3 requests
ENTRYPOINT ["/app/adapter.py"]
```

### Adapter pattern
Il file `adapter.py` (vedi `containers/examples/openmp_adapter.py`):
1. Legge messaggi da SQS
2. Scarica input dal PACS
3. Esegue l'eseguibile nativo
4. Upload risultato su S3
5. Invia notifica sulla ResultsQueue

### Variabili d'ambiente (standard)
Tutti i container ricevono:
```bash
QUEUE_URL=https://sqs...        # Coda algoritmo
RESULT_QUEUE=https://sqs...     # Coda risultati
OUTPUT_BUCKET=mip-output-...    # S3 bucket
ALGO_ID=processing_1            # ID algoritmo
PACS_API_BASE=http://...        # PACS endpoint
PACS_API_KEY=devkey             # PACS auth
```

## 🔐 Sicurezza

- API Admin protetta con header `x-admin-key`
- Ruoli ECS con principio least-privilege
- Ogni algoritmo riceve permessi solo per la sua coda
- Log groups separati per algoritmo

## 📊 Monitoraggio

- CloudWatch Logs: `/ecs/mip-{algo_id}`
- Metriche SQS: `ApproximateNumberOfMessages`
- Lambda Insights sui Lambda
- ECS Service metrics

## 🧪 Testing

```powershell
# Test API admin
.\test\test-admin-api.ps1

# Deploy completo con test
.\deploy-complete.ps1 -TestOnly

# Frontend React
cd clients\react-app
npm start
```

## 🔄 Migrazione da architettura esistente

1. **Deploy nuova stack** - zero downtime
2. **Registra algoritmi esistenti** via API Admin
3. **Verifica funzionamento** 
4. **Rimuovi vecchi servizi** (quando pronto)

La nuova architettura è **backward compatible** - il client React continua a funzionare senza modifiche.

## 🚨 Troubleshooting

### Provisioner fails
- Controlla permessi IAM del Provisioner Lambda
- Verifica log CloudWatch `/aws/lambda/ImgPipeline-ProvisionerFn-...`

### Algoritmo non risponde
- Controlla status in DynamoDB Registry
- Verifica log ECS `/ecs/mip-{algo_id}`
- Controlla che l'immagine esista in ECR

### API Admin non autorizzato
- Verifica header `x-admin-key: dev-admin`
- Controlla che la chiave corrisponda a quella nel deploy

---

🎉 **La nuova architettura è pronta!** Ora puoi registrare algoritmi dinamicamente senza redeploy CDK.
