# 🚀 Image Processing Pipeline

Questa repository contiene i container, la logica e l’infrastruttura per una pipeline di _image processing_ event‑driven su AWS.

---

## 🏗️ Architettura

```
Client → API Gateway → Lambda Router → SQS Requests → Fargate Workers → SNS Results → SQS per client → Lambda Proxy‑SQS → Frontend React
```

- **Client**: invia job via HTTP
- **API Gateway**: espone endpoint REST
- **Lambda Router**: valida e smista i job
- **SQS Requests**: code FIFO per ogni algoritmo
- **Fargate Workers**: processano i job
- **SNS Results**: fan-out dei risultati
- **SQS per client**: coda FIFO isolata per ogni client
- **Lambda Proxy-SQS**: polling HTTP per frontend
- **Frontend React**: provisioning, invio job, polling risultati

---

## 📁 Struttura del progetto

```
new_image_processing_pipeline/
├── README.md ← questo file
├── gen_env/
│   └── gen_env.ps1           # script per raccogliere gli output CDK
├── infra/
│   ├── clients/
│   ├── ecr/
│   ├── lambda/
│   └── stacks/
├── pacs_api/
├── containers/
├── docs/
└── src/
```

---

## 🛠️ Prerequisiti

- AWS CLI configurato (CloudFormation, ECR, ECS, SQS, SNS, Lambda, IAM)
- AWS CDK v2
- Docker
- PowerShell (Windows) o Bash (Linux/macOS)
- Node.js + npm (per il frontend React)

---

## 1️⃣ Preparazione ECR

**Crea i repository e push delle immagini**

```powershell
cd infra/ecr
./create-ecr-repos.ps1 -Region <REGION> -Account <ACCOUNT_ID>
docker build --no-cache -t mip-base:latest -f containers/base/Dockerfile . #se si vuole ripartire alla base senza cache
./push-algos.ps1 -Region <REGION> -Account <ACCOUNT_ID>
./push-pacs.ps1 -Region <REGION> -Account <ACCOUNT_ID>
```

> _Nota: <REGION> es. eu-central-1 o us-east-1; <ACCOUNT_ID> es. 544547773663._

---

## 2️⃣ Deploy infrastruttura con CDK

```bash
cd infra
npm install   # solo se ci sono dipendenze node
cdk deploy Imports --require-approval never
cdk deploy PacsApiStack --require-approval never
cdk deploy ImgPipeline --require-approval never
# oppure
cdk deploy --all --require-approval never
```

**Output deploy:**
- DNS PACS API LB (`PacsApiLB`)
- API Gateway endpoint (`ProcessingApiEndpoint`)
- URL SQS Requests/Results per ogni algoritmo
- SNS Topic ARN (`ImageResultsTopicArn`)

---

## 3️⃣ Generazione variabili d’ambiente

Script PowerShell per raccogliere gli output CDK:

```powershell
./gen_env/gen_env.ps1 -ImgStack "ImgPipeline" -PacsStack "PacsApiStack"
. ./infra/env.ps1   # importa le variabili in sessione
```

**Variabili disponibili:**
- `$Env:API_BASE`         → API Gateway
- `$Env:PACS_API_BASE`    → DNS PACS API
- `$Env:RESULTS_TOPIC_ARN`
- `$Env:REQ1_QUEUE`, `$Env:RES1_QUEUE`, ...

---

## 4️⃣ Frontend React

```bash
cd infra/clients/react-app
npm ci
npm start
```

Nel file `src/index.jsx`:
```js
const API_BASE  = process.env.API_BASE    || '<YOUR_API_GATEWAY_BASE>';
const PACS_BASE = process.env.PACS_API_BASE || '<YOUR_PACS_API_BASE>';
```
Apri il browser su [http://localhost:3000](http://localhost:3000).

---

## 5️⃣ Flusso utente end‑to‑end

1. **Anteprima PACS**
   - Inserisci `study_id`, `series_id`, `image_id`, `scope=image`
   - Clicca _Carica Anteprima_ → visualizzi l’immagine originale
2. **Provision coda client**
   - Clicca _Provisiona coda_ → ricevi `client_id` e `queue_url`
3. **Avvio processing**
   - Clicca _Avvia processing_ → invia POST a `$API_BASE/process/processing_1` con payload PACS + callback.client_id
   - Lambda Router mette il job su SQS Requests
   - Fargate Worker elabora e pubblica su SNS con attributo client_id
   - SNS recapita solo alla tua coda FIFO client
4. **Polling risultati**
   - Il frontend chiama in loop `GET $API_BASE/proxy-sqs?queue=<queue_url>`
   - Quando arriva il messaggio corretto (`job_id`), vedi l’immagine processata

---

## 6️⃣ Script client di esempio

Vedi `infra/clients/send-http-job.ps1` per inviare un job via PowerShell.

Per simulare il PACS‑API in locale, consulta la documentazione in `docs/`.

---

## 7️⃣ Cleanup

Per rimuovere tutto:
```bash
cd infra
cdk destroy --all --force
```

---

## 📚 Note
- I worker Fargate non leggono direttamente da SQS, ma ricevono job inoltrati dalla Lambda router.
- Per estendere la pipeline o aggiungere algoritmi, consulta `src/medical_image_processing/README.md`.

---

# Flusso architetturale: richiesta immagine da frontend a PACS e processing

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
        PROXYSIG[ProxySigFunction (Lambda)]
        PROCAPI[ProcessingApi (API Gateway)]
    end

    FE-->|Richiesta immagine/processamento|APIPACS
    APIPACS-->|Recupera da|PACSB
    APIPACS-->|Invoca pipeline|PIPE
    PIPE-->|Scarica algoritmi|ALGOS
    PIPE-->|Scrive risultati|OUTPUT
    PIPE-->|Invoca|PROCAPI
    PROCAPI-->|Gestisce routing|ROUTER
    PROCAPI-->|Provisioning|PROVISION
    PROCAPI-->|Proxy firma|PROXYSIG
    ROUTER-->|Smista richieste|PIPE
    PROVISION-->|Provisiona risorse|PIPE
    PROXYSIG-->|Proxy firma|PIPE
    FE-->|Riceve risultato|FE
```

## Descrizione step-by-step
1. **Frontend** invia una richiesta di immagine/processamento.
2. La richiesta arriva al **PacsApi** (LoadBalancer + Service).
3. **PacsApi** recupera l’immagine dal bucket S3 PACS esistente.
4. **PacsApi** invoca la **ImgPipeline** (cluster ECS) per processare l’immagine.
5. La pipeline scarica gli algoritmi da **AlgosRepo** (ECR) e processa l’immagine.
6. I risultati vengono scritti su **Output S3 Bucket**.
7. La pipeline interagisce con **ProcessingApi** (API Gateway) per gestire routing, provisioning e firma tramite Lambda:
   - **RouterFunction** smista le richieste ai task giusti.
   - **ProvisionFunction** gestisce il provisioning delle risorse necessarie.
   - **ProxySigFunction** si occupa della firma dei risultati.
8. Il **Frontend** riceve il risultato finale.

> Ogni componente è rappresentato da uno stack o risorsa CDK nella cartella `infra`.