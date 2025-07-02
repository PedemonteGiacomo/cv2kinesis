# 🚀 Guida al Deployment e Testing Integrato

## 📋 Panoramica

Il sistema ora supporta un **workflow completamente integrato** per deployment e testing, con gestione automatica dei suffix per environment multipli. Tutto è orchestrato tramite `deploy_and_test.py`.

## 🎯 Menu Principale

Eseguendo `python deploy_and_test.py` otterrai:

```
=== DEPLOY E TEST INFRASTRUTTURA CLOUD COMPLETA ===
🏗️ Architettura: Webcam → Kinesis → ECS → S3 → SQS → Consumer

Scegli operazione:
1. 🚀 Build e deploy completo (con configurazione)
2. 🔨 Solo build e push immagine Docker
3. ☁️  Solo deploy CDK stack  
4. 🎥 Test producer (webcam → Kinesis)
5. 📨 Test consumer (SQS → Console)
6. 🔄 Test completo (producer + consumer)
7. 📋 Lista stack deployati
```

## 🔧 Opzioni di Deployment

### 1. 🚀 Build e Deploy Completo

**Cosa fa:**
- Richiede configurazione (suffix, stack name, image tag)
- Build e push dell'immagine Docker
- Deploy del CDK stack
- Verifica automatica del deployment
- Health check completo

**Esempio di utilizzo:**
```
Suffix: -dev
Nome stack: VideoPipelineStackDev  
Tag immagine: latest

🎯 Risorse create:
- Kinesis Stream: cv2kinesis-dev
- S3 Bucket: processedframes-544547773663-eu-central-1-dev
- SQS Queue: processing-results-dev
- EFO Consumer: ecs-consumer-dev
```

### 2. 🔨 Solo Build e Push

Per aggiornare solo l'immagine Docker senza rideploy del CDK.

### 3. ☁️ Solo Deploy CDK

Per deploy solo dell'infrastruttura (se l'immagine è già pronta).

## � Testing Integrato

### 4. 🎥 Test Producer 

**Configurazione automatica:**
```
🎥 CONFIGURAZIONE PRODUCER
🏷️ Environment suffix da utilizzare:
   Suffix: -dev

📡 Connecting to Kinesis Stream: cv2kinesis-dev
✅ Stream found with status: ACTIVE
```

**Il sistema:**
- Verifica che lo stream Kinesis esista
- Configura automaticamente il producer
- Avvia la webcam e mostra il feed live
- Invia frames al stream corretto

### 5. 📨 Test Consumer

**Due modalità disponibili:**

**Modalità 1: URL Manuale**
```
1. Inserire manualmente SQS Queue URL
Enter SQS Queue URL: https://sqs.eu-central-1.amazonaws.com/544547773663/processing-results-dev
```

**Modalità 2: Selezione Automatica**
```
2. Selezionare da stack deployati

Stack disponibili:
1. VideoPipelineStack (Status: CREATE_COMPLETE)
2. VideoPipelineStackDev (Status: CREATE_COMPLETE)
3. VideoPipelineStackTest (Status: CREATE_COMPLETE)

Seleziona stack (numero): 2
✅ Using SQS Queue: https://sqs.eu-central-1.amazonaws.com/544547773663/processing-results-dev
```

### 6. 🔄 Test Completo

**Orchestrazione automatica:**
- Seleziona stack esistente o inserisci configurazione manuale
- Avvia consumer in background
- Avvia producer in foreground
- Coordina entrambi i processi

**Esempio:**
```
🚀 TEST COMPLETO (PRODUCER + CONSUMER)

Come vuoi configurare il test?
1. Inserire manualmente SQS Queue URL e suffix
2. Selezionare da stack deployati automaticamente

Opzione: 2

Stack disponibili:
1. VideoPipelineStack
2. VideoPipelineStackDev

Seleziona stack: 2

✅ Selected stack: VideoPipelineStackDev
✅ Using suffix: '-dev'
✅ SQS Queue: https://sqs.eu-central-1.amazonaws.com/544547773663/processing-results-dev

📡 Kinesis Stream: cv2kinesis-dev
📨 SQS Queue: https://sqs.eu-central-1.amazonaws.com/544547773663/processing-results-dev
🎥 Producer will start first, then consumer
📹 Make sure your webcam is working!
```

### 7. 📋 Lista Stack Deployati

**Overview completo:**
```
📋 STACK DEPLOYATI

🔍 Trovati 3 stack:
   ✅ VideoPipelineStack
      Status: CREATE_COMPLETE
      Created: 2025-07-02 10:30:00+00:00
      🎯 Resources:
         📡 Kinesis: cv2kinesis
         📦 S3: processedframes-544547773663-eu-central-1
         🌐 LB: http://alb-1234567890.eu-central-1.elb.amazonaws.com

   ✅ VideoPipelineStackDev (suffix: -dev)
      Status: CREATE_COMPLETE
      Created: 2025-07-02 11:15:00+00:00
      🎯 Resources:
         📡 Kinesis: cv2kinesis-dev
         📦 S3: processedframes-544547773663-eu-central-1-dev
         🌐 LB: http://alb-0987654321.eu-central-1.elb.amazonaws.com
```

## 🔄 Workflow Tipico

### Scenario 1: Primo Setup
```bash
python deploy_and_test.py
# Opzione 1: Build e deploy completo
# Suffix: (vuoto per produzione)
# Tag: production

# Poi testa:
# Opzione 6: Test completo
```

### Scenario 2: Ambiente di Sviluppo
```bash
python deploy_and_test.py
# Opzione 1: Build e deploy completo  
# Suffix: -dev
# Tag: latest

# Sviluppo iterativo:
# Opzione 2: Solo build (quando cambi codice)
# Opzione 4: Test producer (per debug)
```

### Scenario 3: Test di una Feature
```bash
python deploy_and_test.py
# Opzione 1: Deploy
# Suffix: -feat-new-yolo
# Tag: feat-v2

# Test immediato:
# Opzione 6: Test completo
```

## � Modifiche Tecniche

### Producer Dinamico
Il producer ora usa `KINESIS_STREAM_NAME` da variabile d'ambiente invece di `settings.py`:

```python
# Prima (hardcoded):
KINESIS_STREAM_NAME = 'cv2kinesis'

# Ora (dinamico):
kinesis_stream_name = os.environ.get('KINESIS_STREAM_NAME', 'cv2kinesis')
```

### Stack Selection Intelligence
Il sistema può:
- Estrarre il suffix dal nome dello stack
- Mappare automaticamente le risorse correlate
- Validare l'esistenza dei componenti prima del test

### Verifica Pre-Test
Prima di avviare producer/consumer:
- ✅ Verifica esistenza Kinesis Stream
- ✅ Verifica stato (deve essere ACTIVE)
- ✅ Conferma configurazione all'utente

## � Troubleshooting

### Problema: Stream non trovato
```
❌ Kinesis stream 'cv2kinesis-dev' not found!
💡 Make sure to deploy the stack with suffix '-dev' first
```
**Soluzione:** Deploy prima lo stack con il suffix corretto.

### Problema: Stack non listato
```
❌ Nessun VideoPipelineStack trovato
```
**Soluzione:** Usa opzione 1 o 3 per deployare un ambiente.

### Problema: Consumer non riceve messaggi
**Verifica:**
1. Producer sta inviando? (log ogni 30 frame)
2. ECS service è healthy? (opzione 7 per check)
3. SQS queue corretta? (verifica output stack)

## 📚 Best Practices

### 1. Naming degli Ambienti
- **Produzione**: nessun suffix (`VideoPipelineStack`)
- **Sviluppo**: `-dev` (`VideoPipelineStackDev`)
- **Test**: `-test` (`VideoPipelineStackTest`)
- **Feature**: `-feat-{nome}` (`VideoPipelineStackFeatNewYolo`)

### 2. Tag delle Immagini
- **Produzione**: `production`, `v1.0.0`
- **Sviluppo**: `latest`, `dev`
- **Feature**: `feat-{nome}`, `pr-123`

### 3. Workflow di Test
1. **Opzione 7**: Lista stack esistenti
2. **Opzione 4**: Test producer isolato (debug)
3. **Opzione 5**: Test consumer isolato (debug)
4. **Opzione 6**: Test completo (integration test)

Questo approccio integrato rende molto più semplice gestire environment multipli e testare il pipeline end-to-end! 🎉
