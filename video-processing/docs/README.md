# 📚 Documentazione CV2Kinesis

Questa cartella contiene tutte le guide per i team di sviluppo.

## 📋 Guide Disponibili

### Per il Team Infrastrutturale
- **[INFRASTRUCTURE_GUIDE.md](INFRASTRUCTURE_GUIDE.md)** - Deploy e gestione infrastruttura AWS

### Per il Team Frontend
- **[FRONTEND_INTEGRATION_GUIDE.md](FRONTEND_INTEGRATION_GUIDE.md)** - Integrazione completa frontend con la pipeline
- **[frontend-example.html](frontend-example.html)** - Demo HTML completo e funzionante

## 🎯 Overview Architettura

```
Frontend → Kinesis Data Stream → ECS Fargate (YOLOv8) → S3 + SQS → Consumer
```

- **Stream Kinesis**: `cv2kinesis`
- **SQS Queue**: `processing-results`
- **Region**: `eu-central-1`
