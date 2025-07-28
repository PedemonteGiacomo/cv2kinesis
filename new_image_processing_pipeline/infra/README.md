# Deploy rapido con immagini ECR

## 1. Build & push immagini (solo la prima volta o quando cambi il codice)

Apri PowerShell nella root del progetto e lancia:

```powershell
.\ecr\push-algos.ps1 -Region eu-central-1 -Account 123456789012
.\ecr\push-pacs.ps1  -Region eu-central-1 -Account 123456789012
```

## 2. Deploy CDK (da `new_image_processing_pipeline/infra`)

```powershell
cd infra
cdk deploy ImgPipeline --require-approval never
cdk deploy PacsApiStack --require-approval never
```

> Ora CDK non ricostruisce più le immagini in locale, ma usa quelle già presenti in ECR. Il deploy sarà molto più veloce.

---

**Nota:**
- Modifica gli script PowerShell se cambi regione/account.
- Se aggiorni il codice delle immagini, ricostruisci e ripusha prima di ridistribuire con CDK.
