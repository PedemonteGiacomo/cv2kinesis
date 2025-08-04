# Medical Image Processing (MIP) - Dynamic Architecture

## 🏗️ Panoramica dell'Architettura

Questa versione completamente rinnovata della piattaforma MIP introduce un'architettura dinamica basata su registry per sostituire l'approccio precedente con algoritmi hardcoded. Il sistema ora supporta la registrazione, gestione e deployment di algoritmi tramite API senza richiedere rideploy dell'infrastruttura.

### 🔄 Evoluzione Architetturale

**Prima (Architettura Statica):**
- Algoritmi hardcoded nel codice CDK
- Rideploy infrastrutturale per ogni nuovo algoritmo
- Gestione manuale di code SQS e servizi ECS
- Scaling limitato e workflow di sviluppo complessi

**Dopo (Architettura Dinamica):**
- Registry centralizzato DynamoDB per algoritmi
- API di amministrazione per gestione algoritmi
- Provisioning automatico di risorse AWS
- Supporto nativo per algoritmi Python e OpenMP/C++
- Tooling avanzato per sviluppatori

## 🧩 Componenti Principali

### 1. **Registry degli Algoritmi (DynamoDB)**
- **Tabella**: `mip-algorithms`
- **Chiave**: `algorithm_name` (string)
- **Attributi**: 
  - `status` (active/inactive/failed)
  - `image_uri` (ECR repository)
  - `algorithm_type` (python/openmp)
  - `cpu/memory` (risorse richieste)
  - `parameters` (configurazione)
  - `created_at/updated_at` (timestamp)

### 2. **Lambda Functions**

#### Admin API (`algos_admin.py`)
```
Endpoint: POST /algorithms
Funzione: Registrazione nuovi algoritmi
Autenticazione: x-admin-key header
Trigger: API Gateway REST
```

#### Provisioner (`provisioner.py`)
```
Funzione: Creazione automatica SQS queue + ECS service
Trigger: Invocazione da Admin API
Timeout: 5 minuti per setup completo
```

#### Dynamic Router (`dynamic_router.py`)
```
Endpoint: POST /process/{algorithm_name}
Funzione: Routing intelligente richieste processing
Input: Job metadata + PACS info
Output: SQS message verso algoritmo specifico
```

### 3. **Container Registry (ECR)**
```
Repository Pattern: mip-{algorithm_name}
Tag Strategy: latest, v{version}
Multi-arch: linux/amd64, linux/arm64 (dove supportato)
```

### 4. **ECS Cluster (`mip-cluster`)**
```
Task Definition Pattern: mip-{algorithm_name}
Service Pattern: mip-{algorithm_name}
Networking: awsvpc mode con security groups
Auto Scaling: Target tracking su CPU/Memory
```

### 5. **Code SQS FIFO**
```
Pattern: mip-{algorithm_name}-requests.fifo
Visibility Timeout: 900s (15 min)
Message Retention: 14 giorni
DLQ: Attiva dopo 3 tentativi
```

## 🛠️ Tipi di Algoritmi Supportati

### Python Algorithms
```python
# Struttura base
class MyProcessor(BaseProcessor):
    def process_image(self, image_data, parameters):
        # Implementazione algoritmo
        return processed_image
```

**File richiesti:**
- `algorithm.py` - Implementazione principale
- `Dockerfile` - Container definition
- `requirements.txt` - Dipendenze Python
- `metadata.json` - Configurazione algoritmo

### OpenMP/C++ Algorithms
```c
// Core computation con parallelizzazione
#pragma omp parallel for
for (int i = 0; i < height; i++) {
    // Processing parallelo
}
```

**File richiesti:**
- `src/main.c` - Implementazione C/OpenMP
- `src/Makefile` - Build configuration
- `adapter.py` - Bridge Python per AWS integration
- `Dockerfile` - Container con toolchain C
- `metadata.json` - Configurazione algoritmo

## 🚀 Workflow di Sviluppo

### 1. Creazione Nuovo Algoritmo
```powershell
# Genera template completo
.\scripts\new-algorithm.ps1 -Name liver-segmentation -Type openmp

# Oppure per algoritmo Python
.\scripts\new-algorithm.ps1 -Name threshold-filter -Type python
```

### 2. Sviluppo e Testing
```powershell
# Validazione algoritmo
.\scripts\validate-algorithm.ps1 -AlgorithmPath .\containers\liver-segmentation -Fix

# Build e test locale
cd containers\liver-segmentation
docker build -t liver-segmentation .
docker run --rm liver-segmentation
```

### 3. Deployment
```powershell
# Deploy singolo algoritmo
cd containers\liver-segmentation
.\deploy.ps1

# Oppure deploy tutto da root
.\deploy-complete.ps1
```

### 4. Gestione Post-Deployment
```powershell
# Lista algoritmi attivi
.\scripts\manage-mip.ps1 -Action list-algorithms

# Registrazione via API
.\scripts\manage-mip.ps1 -Action register-algorithm -AlgorithmName liver-segmentation -AlgorithmPath .\containers\liver-segmentation

# Scaling
.\scripts\manage-mip.ps1 -Action scale -AlgorithmName liver-segmentation -DesiredCount 3

# Health check
.\scripts\manage-mip.ps1 -Action check-health

# Logs
.\scripts\manage-mip.ps1 -Action logs -Hours 2
```

## 📁 Struttura Progetto Aggiornata

```
cv2kinesis/
├── infra/                          # Infrastruttura CDK
│   ├── lambda/                     # Lambda functions
│   │   ├── algos_admin.py         # API amministrazione
│   │   ├── provisioner.py         # Provisioning automatico
│   │   └── dynamic_router.py      # Router dinamico
│   ├── stacks/
│   │   └── image_pipeline.py      # Stack principale (rinnovato)
│   └── clients/react-app/          # Frontend web
├── containers/                     # Algoritmi containerizzati
│   ├── examples/                   # Template e esempi
│   │   ├── python-simple/         # Esempio Python base
│   │   ├── python-advanced/       # Esempio Python avanzato
│   │   └── openmp-template/       # Template OpenMP
│   └── grayscale/                  # Algoritmo OpenMP reale
├── scripts/                        # Tooling sviluppatori
│   ├── new-algorithm.ps1          # Generatore algoritmi
│   ├── validate-algorithm.ps1     # Validatore
│   └── manage-mip.ps1             # Gestione post-deploy
├── pacs_api/                       # PACS integration
├── deploy-complete.ps1             # Deploy completo
└── README.md                       # Questa documentazione
```

## 🔗 API Reference

### Admin API

#### Registrazione Algoritmo
```bash
POST /algorithms
Headers: 
  x-admin-key: your-admin-key
  Content-Type: application/json

Body:
{
  "name": "liver-segmentation",
  "image_uri": "123456789.dkr.ecr.us-east-1.amazonaws.com/mip-liver-segmentation:latest",
  "algorithm_type": "openmp", 
  "description": "Liver segmentation with OpenMP acceleration",
  "cpu": 2048,
  "memory": 4096,
  "parameters": {
    "threshold": {"type": "float", "default": 0.5},
    "iterations": {"type": "int", "default": 100}
  }
}
```

#### Lista Algoritmi
```bash
GET /algorithms
Headers:
  x-admin-key: your-admin-key
```

#### Aggiornamento Algoritmo
```bash
PATCH /algorithms/{name}
Headers:
  x-admin-key: your-admin-key
  Content-Type: application/json

Body:
{
  "status": "active",
  "description": "Updated description",
  "cpu": 4096
}
```

#### Eliminazione Algoritmo
```bash
DELETE /algorithms/{name}
Headers:
  x-admin-key: your-admin-key
```

### Processing API

#### Invio Job Processing
```bash
POST /process/{algorithm_name}
Headers:
  Content-Type: application/json

Body:
{
  "job_id": "unique-job-id",
  "client_id": "client-identifier", 
  "pacs": {
    "study_uid": "1.2.3.4.5",
    "series_uid": "1.2.3.4.5.6",
    "instance_uid": "1.2.3.4.5.6.7"
  },
  "parameters": {
    "threshold": 0.7,
    "iterations": 150
  },
  "callback_url": "https://client.example.com/results"
}
```

#### Health Check
```bash
GET /health
Response: {"status": "healthy", "timestamp": "2024-01-31T10:00:00Z"}
```

## 🔧 Configurazione e Setup

### Prerequisiti
- AWS CLI configurato
- AWS CDK v2 installato (`npm install -g aws-cdk`)
- Docker Desktop
- PowerShell 5.1+ (Windows) o PowerShell Core (cross-platform)
- Python 3.11+
- Node.js 18+ (per CDK)

### Setup Iniziale
```powershell
# 1. Clone repository
git clone <repository-url>
cd cv2kinesis

# 2. Deploy completo (prima volta)
.\deploy-complete.ps1

# 3. Configura admin key
$adminKey = aws ssm get-parameter --name "/mip/admin/key" --with-decryption --query "Parameter.Value" --output text
$env:MIP_ADMIN_KEY = $adminKey
```

### Variabili Ambiente
```powershell
# Admin API key
$env:MIP_ADMIN_KEY = "your-admin-key"

# AWS Configuration
$env:AWS_DEFAULT_REGION = "us-east-1"
$env:AWS_PROFILE = "your-profile"

# Development options
$env:VALIDATE_BUILD = "true"    # Validate Docker builds in CI
$env:MIP_DEBUG = "true"         # Enable debug logging
```

## 📊 Monitoring e Troubleshooting

### CloudWatch Log Groups
```
/aws/lambda/mip-algos-admin      # Admin API logs
/aws/lambda/mip-provisioner      # Provisioning logs  
/aws/lambda/mip-dynamic-router   # Router logs
/ecs/mip-algorithms              # Container execution logs
```

### Metriche Principali
- **API Gateway**: Request latency, error rates
- **Lambda**: Duration, errors, concurrent executions
- **ECS**: CPU/Memory utilization, task failures
- **SQS**: Message age, DLQ messages
- **DynamoDB**: Read/write capacity, throttling

### Troubleshooting Comune

#### 1. Algoritmo non riceve messaggi
```powershell
# Verifica registrazione
.\scripts\manage-mip.ps1 -Action list-algorithms

# Verifica coda SQS
aws sqs get-queue-attributes --queue-url https://sqs.region.amazonaws.com/account/mip-algorithm-requests.fifo

# Verifica servizio ECS
aws ecs describe-services --cluster mip-cluster --services mip-algorithm-name
```

#### 2. Errori di build container
```powershell
# Validazione locale
.\scripts\validate-algorithm.ps1 -AlgorithmPath .\containers\my-algorithm -Verbose

# Build debug
cd containers\my-algorithm  
docker build -t debug-algo . --progress=plain
```

#### 3. Problemi di performance
```powershell
# Scaling manuale
.\scripts\manage-mip.ps1 -Action scale -AlgorithmName my-algorithm -DesiredCount 5

# Monitor resource usage
aws ecs describe-services --cluster mip-cluster --services mip-my-algorithm --include-tags
```

## 🔄 Workflow CI/CD Suggerito

### GitHub Actions Example
```yaml
name: Deploy MIP Algorithm
on:
  push:
    paths: ['containers/**']

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Configure AWS
        run: |
          aws configure set aws_access_key_id ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws configure set aws_secret_access_key ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws configure set region us-east-1
      
      - name: Validate Algorithm
        run: |
          ./scripts/validate-algorithm.ps1 -AlgorithmPath ./containers/my-algorithm
      
      - name: Deploy Algorithm  
        run: |
          cd containers/my-algorithm
          ./deploy.ps1
      
      - name: Register with API
        run: |
          ./scripts/manage-mip.ps1 -Action register-algorithm -AlgorithmName my-algorithm -AlgorithmPath ./containers/my-algorithm
```

## 🎯 Roadmap Futura

### Prossime Release
- [ ] **Multi-region deployment**: Support per deployment cross-region
- [ ] **GPU algorithm support**: Integrazione CUDA/OpenCL algorithms  
- [ ] **Workflow orchestration**: Support per algoritmi multi-step
- [ ] **Real-time processing**: WebSocket support per risultati immediati
- [ ] **Algorithm versioning**: Gestione versioni multiple simultane
- [ ] **Cost optimization**: Auto-scaling intelligente basato su coda
- [ ] **ML integration**: Support nativo per TensorFlow/PyTorch models

### Miglioramenti Infrastrutturali
- [ ] **Service mesh**: Istio/AWS App Mesh per comunicazione sicura
- [ ] **Secrets management**: Integrazione completa AWS Secrets Manager
- [ ] **Compliance**: HIPAA/GDPR compliance per dati medicali
- [ ] **Disaster recovery**: Backup automatico e cross-region replication

## 📞 Supporto

Per problemi, domande o contributi:

1. **Issues**: Aprire issue su repository GitHub
2. **Documentation**: Consultare file README specifici in ogni cartella
3. **Logs**: Utilizzare `manage-mip.ps1 -Action logs` per debugging
4. **Health checks**: Utilizzare `manage-mip.ps1 -Action check-health`

---

*Documentazione aggiornata per MIP Dynamic Architecture v2.0*
*Ultimo aggiornamento: Gennaio 2024*
