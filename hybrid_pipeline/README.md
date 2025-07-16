

# Hybrid Pipeline AWS - Image & Video Processing

## Obiettivo
Pipeline ibrida per processare **immagini** e **video** in modo completamente event-driven e serverless su AWS, sfruttando servizi gestiti per orchestrazione, scalabilità e monitoraggio.

---

## Architettura Completa

### Diagramma Generale
```mermaid
flowchart TD

    %% Image Pipeline
    User1([👤 Utente/Servizio]):::user
    S3Input([🗂️ ImageInputBucket]):::s3
    LambdaDispatcher([🦸‍♂️ ImageS3DispatcherLambda]):::lambda
    StepFunc([🔗 ImageProcessingStateMachine]):::stepfn
    ECSGray([🖥️ ECS Fargate: GrayscaleTask]):::ecs
    S3Output([🗂️ ImageOutputBucket]):::s3
    SQSImage([📨 SQS FIFO: image-processing-results]):::sqs

    User1 --Upload--> S3Input
    S3Input --Event--> LambdaDispatcher
    LambdaDispatcher --Trigger--> StepFunc
    StepFunc --Run ECS--> ECSGray
    ECSGray --Process--> S3Output
    ECSGray --Send Metrics--> SQSImage

    %% Video Pipeline
    User2([👤 Utente/Servizio]):::user
    S3VideoInput([🗂️ VideoInputBucket]):::s3
    Kinesis([🔀 Kinesis VideoFrameStream]):::kinesis
    ECSYolo([🖥️ ECS Fargate: YOLOTask]):::ecs
    S3Frames([🗂️ VideoFramesBucket]):::s3
    SQSVideo([📨 SQS FIFO: video-processing-results]):::sqs
    LB([🌐 Load Balancer]):::lb

    User2 --Upload--> S3VideoInput
    S3VideoInput --Frames--> Kinesis
    Kinesis --Stream--> ECSYolo
    ECSYolo --Save--> S3Frames
    ECSYolo --Send Results--> SQSVideo
    ECSYolo --Expose--> LB

    %% Consumer
    Consumer([👁️ Consumer]):::consumer
    SQSImage --Notify--> Consumer
    SQSVideo --Notify--> Consumer

    %% Legenda
    subgraph Legenda
        aws1([AWS Service]):::aws
        s31([S3 Bucket]):::s3
        lambda1([Lambda]):::lambda
        stepfn1([Step Functions]):::stepfn
        ecs1([ECS Fargate]):::ecs
        kinesis1([Kinesis]):::kinesis
        sqs1([SQS FIFO]):::sqs
        lb1([Load Balancer]):::lb
        user1([Utente/Servizio]):::user
        consumer1([Consumer]):::consumer
    end
```

---

### Image Processing Pipeline
```mermaid
sequenceDiagram
    participant User
    participant S3Input
    participant Lambda
    participant StepFunc
    participant ECSGray
    participant S3Output
    participant SQSImage
    User->>S3Input: Upload .jpg/.png
    S3Input->>Lambda: S3 Event
    Lambda->>StepFunc: Start Execution
    StepFunc->>ECSGray: Run Task (image_key, bucket)
    ECSGray->>S3Output: Save processed image
    ECSGray->>SQSImage: Send metrics/results
```

---

### Video Processing Pipeline
```mermaid
sequenceDiagram
    participant User
    participant S3VideoInput
    participant Kinesis
    participant ECSYolo
    participant S3Frames
    participant SQSVideo
    participant LB
    User->>S3VideoInput: Upload video
    S3VideoInput->>Kinesis: Extract frames
    Kinesis->>ECSYolo: Stream frames
    ECSYolo->>S3Frames: Save results
    ECSYolo->>SQSVideo: Send results
    ECSYolo->>LB: Expose HTTP API
```

---

## Componenti Principali

- **S3**: Bucket per input/output immagini e video
- **Lambda**: Dispatcher per trigger S3 → Step Functions
- **Step Functions**: Orchestrazione workflow (image)
- **ECS Fargate**: Container per grayscale (C/OpenMP) e YOLO (video)
- **Kinesis**: Streaming frame video
- **SQS FIFO**: Code per risultati (image/video)
- **ECR**: Repository immagini container
- **Load Balancer**: Accesso HTTP al servizio video

---

## Mapping tra CDK e Servizi Custom

- **Grayscale Service**: `services/grayscale_service/app_aws.py` (AWS), orchestrato da Step Functions, container ECS Fargate
- **YOLO Stream Service**: `services/stream_service/app_cloud.py` (AWS), container ECS Fargate, consuma da Kinesis, salva su S3/SQS, esposto via Load Balancer
- **Dispatcher Lambda**: `lambda/dispatcher/dispatcher.py`, trigger S3, avvia Step Functions

---

## Flussi di Interazione

### Image Pipeline
1. L’utente carica un’immagine su S3.
2. S3 genera un evento che attiva la Lambda dispatcher.
3. La Lambda avvia la Step Function.
4. Step Function esegue il task ECS Fargate (grayscale).
5. Il container processa l’immagine, la salva su S3 output e invia un messaggio su SQS FIFO.
6. Un consumer può leggere il messaggio SQS per trigger successivi o metriche.

### Video Pipeline
1. L’utente carica un video su S3.
2. I frame vengono estratti e inviati su Kinesis.
3. Il servizio ECS Fargate YOLO consuma i frame, processa, salva su S3 frames e invia risultati su SQS FIFO.
4. Il servizio è accessibile via HTTP tramite Load Balancer.

---

## Come Deployare e Testare

1. **Synth**: `cdk synth` per validare la definizione.
2. **Deploy**: `cdk deploy` per creare lo stack.
3. **Test**:
   - Upload immagini su S3 → verifica output su S3/SQS FIFO
   - Upload video → verifica stream frame, output YOLO su S3/SQS FIFO
   - Accesso HTTP al servizio video

---

## Stato Attuale

- Pipeline pronta per deploy e test.
- Tutti i servizi custom integrati e orchestrati tramite CDK.
- Struttura modulare, estendibile e robusta.
- Code SQS FIFO per risultati image/video.

---

## Note per il Team

- Tutti i flussi sono event-driven e serverless.
- I diagrammi mermaid sono renderizzabili su GitHub.
- Per test end-to-end, usa lo script `deploy_and_test.py`.
- Per estensioni, aggiungi nuovi step/servizi in CDK e aggiorna i container custom.

---

**Questa README ora include diagrammi, flussi e istruzioni chiare per il team.**
