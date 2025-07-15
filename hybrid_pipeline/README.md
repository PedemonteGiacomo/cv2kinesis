
# Hybrid Pipeline AWS - Image & Video Processing

## Obiettivo
Pipeline ibrida per processare **immagini** e **video** in modo completamente event-driven e serverless su AWS, sfruttando servizi gestiti per orchestrazione, scalabilità e monitoraggio.

## Architettura Completa

### 1. Image Processing Pipeline
**Flusso End-to-End:**
1. **Upload**: Un file `.jpg` o `.png` viene caricato su S3 (`ImageInputBucket`).
2. **Trigger**: L'evento S3 attiva la Lambda `ImageS3DispatcherLambda`.
3. **Dispatcher Lambda**: (`lambda/dispatcher/dispatcher.py`) riceve l'evento e avvia la State Machine Step Functions (`ImageProcessingStateMachine`).
4. **Step Functions**: Orchestrazione del workflow, che esegue un task ECS Fargate (`GrayscaleTaskDefinition`).
5. **Grayscale Service**: Il container custom (`services/grayscale_service/app_aws.py`) riceve i parametri (bucket/key), processa l'immagine in C/OpenMP, salva il risultato su S3 (`ImageOutputBucket`) e invia metriche su SQS (`ImageProcessingQueue`).
6. **Output**: Immagine processata su S3, messaggio su SQS.

**Componenti:**
- S3: `ImageInputBucket`, `ImageOutputBucket`
- Lambda: `ImageS3DispatcherLambda` (trigger S3)
- Step Functions: `ImageProcessingStateMachine` (workflow)
- ECS Fargate: `GrayscaleTaskDefinition` (container da `services/grayscale_service`)
- SQS: `ImageProcessingQueue` (output/metriche)

### 2. Video Processing Pipeline
**Flusso End-to-End:**
1. **Upload**: Un video viene caricato su S3 (`VideoInputBucket`).
2. **Frame Extraction**: I frame vengono inviati su Kinesis Data Streams (`VideoFrameStream`).
3. **ECS Fargate Service**: Il servizio ECS (`StreamTaskDefinition` + `ApplicationLoadBalancedFargateService`) esegue il container YOLO (`services/stream_service/app_cloud.py`).
4. **YOLO Service**: Il container consuma i frame da Kinesis, applica YOLO (object detection), salva i risultati su S3 (`VideoFramesBucket`) e invia i risultati su SQS FIFO (`VideoProcessingQueue`).
5. **Accesso**: Il servizio è esposto tramite Application Load Balancer (`VideoStreamServiceURL`).

**Componenti:**
- S3: `VideoInputBucket`, `VideoFramesBucket`
- Kinesis: `VideoFrameStream` (streaming frame)
- ECS Fargate: `StreamTaskDefinition` (container da `services/stream_service`)
- SQS: `VideoProcessingQueue` (risultati, FIFO)
- ECR: `StreamRepository` (immagine container YOLO)
- Load Balancer: `VideoStreamServiceURL` (accesso HTTP)

## Mapping tra CDK e Servizi Custom

- **Grayscale Service**:
  - Definito in `services/grayscale_service/app_aws.py` (per AWS) e `app.py` (per locale/minio).
  - Deployato come container su ECS Fargate tramite `GrayscaleTaskDefinition`.
  - Orchestrato da Step Functions (`ImageProcessingStateMachine`).

- **YOLO Stream Service**:
  - Definito in `services/stream_service/app_cloud.py` (per AWS) e `app.py` (per locale).
  - Deployato come container su ECS Fargate tramite `StreamTaskDefinition`.
  - Consuma frame da Kinesis, salva risultati su S3/SQS, esposto via Load Balancer.

- **Dispatcher Lambda**:
  - Codice in `lambda/dispatcher/dispatcher.py`.
  - Trigger S3, avvia Step Functions.

## Dettagli Tecnici

- **Event-driven**: Ogni step è attivato da un evento (upload, stream, messaggio).
- **Serverless**: Nessuna gestione server, tutto gestito da AWS.
- **Scalabilità**: ECS Fargate e Kinesis scalano automaticamente.
- **Estensibilità**: Facile aggiungere nuovi step/servizi.
- **Monitoraggio**: Step Functions, CloudWatch, SQS per tracing/debug.

## Output e Risorse Principali

- S3 bucket immagini input/output
- S3 bucket video input/frames
- SQS code per risultati
- Kinesis stream per frame video
- ECR repository per container
- URL servizio video via Load Balancer
- ARN State Machine Step Functions

## Come Deployare e Testare

1. **Synth**: `cdk synth` per validare la definizione.
2. **Deploy**: `cdk deploy` per creare lo stack.
3. **Test**:
   - Upload immagini su S3 → verifica output su S3/SQS
   - Upload video → verifica stream frame, output YOLO su S3/SQS
   - Accesso HTTP al servizio video

## Stato Attuale

- La pipeline è definita e pronta per deploy.
- Tutti i servizi custom sono integrati e orchestrati tramite CDK.
- La struttura è modulare e pronta per estensioni future.

---

**Questa README descrive in modo completo l'architettura, il flusso e l'integrazione tra CDK e servizi custom.**
