# Template per creare un nuovo algoritmo per MIP

Questo template ti guida nella creazione di un nuovo algoritmo per l'architettura MIP dinamica.

## 🎯 Scelta del tipo di algoritmo

### Algoritmo Python (più semplice)
Se il tuo algoritmo è implementato in Python, usa il framework esistente:

```
containers/
└── my_python_algo/
    ├── Dockerfile              # FROM mip-base
    └── algorithm.py             # Implementa Processor interface
```

### Algoritmo OpenMP/Nativo (prestazioni)
Se hai un eseguibile compilato (C/C++, Rust, Go):

```
containers/
└── my_openmp_algo/
    ├── Dockerfile
    ├── adapter.py               # Bridge Python->Nativo
    ├── requirements.txt
    └── src/                     # Codice sorgente nativo
        ├── Makefile
        ├── main.c
        └── algorithm.c
```

## 📋 Checklist per nuovo algoritmo

### 1. Struttura directory
```bash
mkdir containers/my_algo
cd containers/my_algo
```

### 2. Definisci input/output
- Input: DICOM, PNG, JPEG?
- Output: DICOM modificato, nuova immagine?
- Parametri: threads, iterazioni, soglie?

### 3. Implementa algoritmo
- [Python] Estendi `BaseProcessor`
- [OpenMP] Crea `adapter.py` + binario

### 4. Testa localmente
```bash
docker build -t my-algo .
docker run --rm my-algo --help
```

### 5. Integra con MIP
- Build e push ECR
- Registra via Admin API
- Test end-to-end

## 🔧 Template per algoritmo Python

### `containers/my_python_algo/algorithm.py`
```python
from medical_image_processing.processing.base import BaseProcessor
import numpy as np

class MyAlgorithmProcessor(BaseProcessor):
    def __init__(self):
        super().__init__()
        self.name = "my_algorithm"
    
    def process_image(self, image_data, metadata=None, **kwargs):
        """
        Processa un'immagine DICOM
        
        Args:
            image_data: numpy array dell'immagine
            metadata: metadati DICOM (opzionale)
            **kwargs: parametri aggiuntivi dal job
            
        Returns:
            numpy array dell'immagine processata
        """
        # Tua implementazione qui
        processed = self._my_algorithm(image_data, **kwargs)
        return processed
    
    def _my_algorithm(self, image, threshold=0.5, iterations=10):
        # Esempio: applica filtro
        result = image.copy()
        # ... tua logica ...
        return result
```

### `containers/my_python_algo/Dockerfile`
```dockerfile
FROM 544547773663.dkr.ecr.us-east-1.amazonaws.com/mip-base:latest

# Installa dipendenze specifiche
RUN pip install --no-cache-dir opencv-python scikit-image

# Copia algoritmo
COPY algorithm.py /app/src/medical_image_processing/processing/my_algorithm.py

# Comando standard (usa worker.sh esistente)
CMD ["/app/worker.sh"]
```

## ⚡ Template per algoritmo OpenMP

### `containers/my_openmp_algo/adapter.py`
```python
#!/usr/bin/env python3
import os, json, subprocess, tempfile
import boto3, requests
from pathlib import Path

# Copia la struttura da containers/grayscale/adapter.py
# e modifica solo:
binary_path = "/app/bin/my_algorithm"
algo_name = "my_algorithm"

def process_with_binary(input_file, output_file, **params):
    """Esegui il tuo binario"""
    cmd = [binary_path, str(input_file), str(output_file)]
    
    # Aggiungi parametri specifici
    if 'threshold' in params:
        cmd.extend(['--threshold', str(params['threshold'])])
    
    # Esegui con OpenMP
    env = os.environ.copy()
    env['OMP_NUM_THREADS'] = str(params.get('threads', 2))
    
    subprocess.run(cmd, check=True, env=env)

# ... resto uguale a grayscale/adapter.py
```

### `containers/my_openmp_algo/src/main.c`
```c
#include <stdio.h>
#include <stdlib.h>
#include <omp.h>

int main(int argc, char *argv[]) {
    if (argc < 3) {
        fprintf(stderr, "Usage: %s <input> <output> [options]\n", argv[0]);
        return 1;
    }
    
    printf("[my_algorithm] Processing with %d threads\n", omp_get_max_threads());
    
    // Tua implementazione
    process_image(argv[1], argv[2]);
    
    printf("[my_algorithm] Completed\n");
    return 0;
}
```

### `containers/my_openmp_algo/Dockerfile`
```dockerfile
FROM python:3.11-slim

# Build environment
RUN apt-get update && apt-get install -y gcc g++ make libgomp1

# AWS CLI + tools
RUN curl -sSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip \
    && unzip -q /tmp/awscliv2.zip -d /tmp \
    && /tmp/aws/install \
    && rm -rf /tmp/aws*

WORKDIR /app

# Compila algoritmo
COPY src/ /app/src/
WORKDIR /app/src
RUN make && mv my_algorithm ../bin/

WORKDIR /app
COPY adapter.py requirements.txt ./
RUN pip install -r requirements.txt && chmod +x adapter.py

ENTRYPOINT ["/app/adapter.py"]
```

## 🚀 Script di deploy automatico

Crea `containers/my_algo/deploy.ps1`:

```powershell
param([string]$AlgoName, [string]$Account="544547773663", [string]$Region="us-east-1")

$repo = "$Account.dkr.ecr.$Region.amazonaws.com/mip-algos"

# Build
docker build -t "mip-$AlgoName" .
docker tag "mip-$AlgoName" "${repo}:${AlgoName}"

# Push
aws ecr get-login-password --region $Region | docker login --username AWS --password-stdin "$Account.dkr.ecr.$Region.amazonaws.com"
docker push "${repo}:${AlgoName}"

# Register
$spec = @{
    algo_id = $AlgoName
    image_uri = "${repo}:${AlgoName}"
    cpu = 1024
    memory = 2048
    command = @("/app/worker.sh")  # o "/app/adapter.py"
}

Invoke-RestMethod -Uri "$env:API_BASE/admin/algorithms" -Method POST -Headers @{
    'Content-Type' = 'application/json'
    'x-admin-key' = 'dev-admin'
} -Body ($spec | ConvertTo-Json)

Write-Host "✅ Algorithm $AlgoName deployed and registered!"
```

## 📋 Variabili d'ambiente standard

Tutti gli algoritmi ricevono automaticamente:

```bash
QUEUE_URL=https://sqs...         # Coda SQS algoritmo
RESULT_QUEUE=https://sqs...      # Coda risultati globale
OUTPUT_BUCKET=mip-output-...     # S3 bucket output
ALGO_ID=my_algorithm             # ID algoritmo
PACS_API_BASE=http://...         # Endpoint PACS
PACS_API_KEY=devkey              # Chiave PACS
```

Variabili personalizzate (tramite Admin API):
```bash
OMP_NUM_THREADS=4                # Thread OpenMP
MY_THRESHOLD=0.8                 # Parametri algoritmo
MY_ITERATIONS=10
```

## 🧪 Test del nuovo algoritmo

```bash
# 1. Build locale
docker build -t my-algo .

# 2. Test locale (mock)
docker run --rm -e ALGO_ID=test my-algo

# 3. Deploy e registra
.\deploy.ps1 -AlgoName my_algorithm

# 4. Test completo
curl -X POST "$API_BASE/process/my_algorithm" \
  -H "Content-Type: application/json" \
  -d '{"job_id":"test","client_id":"test","pacs":{...}}'
```

## 🔍 Debug e troubleshooting

### Log algoritmo
```bash
aws logs tail /ecs/mip-my_algorithm --follow
```

### Stato algoritmo
```bash
curl -H "x-admin-key: dev-admin" "$API_BASE/admin/algorithms/my_algorithm"
```

### Metriche coda
```bash
aws sqs get-queue-attributes --queue-url "..." --attribute-names All
```

---

Seguendo questo template, puoi integrare qualsiasi algoritmo nella piattaforma MIP in pochi passi! 🎯
