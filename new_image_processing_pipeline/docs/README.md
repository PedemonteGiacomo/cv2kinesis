# Esempi di chiamate PACS API per ottenere presigned URL

## Come ottenere il dominio del load balancer PACS API

Puoi recuperare il DNS del load balancer del PACS API direttamente dagli output dello stack CloudFormation con questo comando PowerShell:

```powershell
$stack = aws cloudformation describe-stacks --stack-name PacsApi | ConvertFrom-Json
$env:PACS_API_LB = ($stack.Stacks[0].Outputs | Where-Object { $_.OutputKey -like '*apiurl*' }).OutputValue
Write-Host "PACS_API_LB = $env:PACS_API_LB"
```

> Sostituisci `PacsApi` con il nome effettivo dello stack se diverso. L'output sarà il dominio da usare nelle chiamate curl qui sotto.

## Lista immagini di una serie

```
curl "http://$env:PACS_API_LB/studies/liver1/phantomx_abdomen_pelvis_dataset/D55-01/images?series_id=300/AiCE_BODY-SHARP_300_172938.900"
```

## Singola immagine (AiCE_BODY-SHARP)
```
curl "http://$env:PACS_API_LB/studies/liver1/phantomx_abdomen_pelvis_dataset/D55-01/images/300/AiCE_BODY-SHARP_300_172938.900/IM-0135-0001.dcm"
```

## Singola immagine (AIDR3D_FC08)
```
curl "http://$env:PACS_API_LB/studies/liver1/phantomx_abdomen_pelvis_dataset/D55-01/images/300/AIDR3D_FC08_300_171515.916/IM-0007-0001.dcm"
```

## Singola immagine (FBP_FC08)
```
curl "http://$env:PACS_API_LB/studies/liver1/phantomx_abdomen_pelvis_dataset/D55-01/images/300/FBP_FC08_300_171515.916/IM-0008-0001.dcm"
```

## Serie e immagini per liver2
```
curl "http://$env:PACS_API_LB/studies/liver2/phantomx_abdomen_lesion_dataset/D53-03/images?series_id=300/12_120_300_BODY-SHARP_AICE_175519.910"

curl "http://$env:PACS_API_LB/studies/liver2/phantomx_abdomen_lesion_dataset/D53-03/images/300/12_120_300_BODY-SHARP_AICE_175519.910/IM-0254-0001.dcm"
```

## Note
- Puoi cambiare i path per accedere a qualsiasi file DICOM presente nel bucket.
- La risposta sarà sempre un JSON con campo `url` (presigned) e, per la lista, anche `key`.

---

## Integrazione con la pipeline di processing
Le chiamate alle PACS API sono ora integrate nella pipeline tramite API Gateway e Lambda router. Per inviare job di processing, consulta la documentazione principale e gli script client in `infra/clients`.
