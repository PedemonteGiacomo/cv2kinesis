param(
  [string] $Region = "eu-central-1",
  [string] $ApiEndpoint  # e.g. https://xyz.execute-api.eu-central-1.amazonaws.com/prod
)

$algo = "processing_1"
$body = @{
  job_id = [guid]::NewGuid().ToString()
param(
  [string] $Region = "eu-central-1",
  [string] $ApiEndpoint,  # es: https://xyz.execute-api.eu-central-1.amazonaws.com/prod
  [string] $ClientId      # es: my-client-123
)

$algo = "processing_1"
$body = @{
  job_id = [guid]::NewGuid().ToString()
  pacs = @{
    study_id  = "liver1/phantomx_abdomen_pelvis_dataset/D55-01"
    series_id = "300/AiCE_BODY-SHARP_300_172938.900"
    image_id  = "IM-0135-0001.dcm"
    scope     = "image"
  }
  callback = @{ client_id = $ClientId }
} | ConvertTo-Json -Depth 4

Invoke-RestMethod -Uri "$ApiEndpoint/process/$algo" `
  -Method POST `
  -Body $body `
  -ContentType "application/json"
