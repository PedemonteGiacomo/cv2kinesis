# PowerShell script per inviare un job di test alla coda SQS come farebbe un frontend

# Recupera gli output dello stack (se non già fatto)
$stack = aws cloudformation describe-stacks --stack-name ImgPipeline | ConvertFrom-Json
$outs  = $stack.Stacks[0].Outputs

$env:REQ_Q      = ($outs | ? { $_.OutputKey -like "*ImageRequests*" }).OutputValue
$env:RES_Q      = ($outs | ? { $_.OutputKey -like "*ImageResults*" }).OutputValue
$env:OUT_BUCKET = ($outs | ? { $_.OutputKey -like "*Output*"       }).OutputValue

Write-Host "REQ_Q      = $env:REQ_Q"
Write-Host "RES_Q      = $env:RES_Q"
Write-Host "OUT_BUCKET = $env:OUT_BUCKET"

# Crea un nuovo job id
$jobId = "job-{0}" -f ([guid]::NewGuid())

# Prepara il messaggio di richiesta processing
$msg = @{
  job_id  = $jobId
  algo_id = "processing_6"
  pacs    = @{
     study_id  = "liver1/phantomx_abdomen_pelvis_dataset/D55-01"
     series_id = "300/AiCE_BODY-SHARP_300_172938.900"
     image_id  = "IM-0135-0001.dcm"
     scope     = "image"
  }
  callback = @{ queue_url = $env:RES_Q }
} | ConvertTo-Json -Depth 4

# Invia il messaggio alla coda delle richieste
aws sqs send-message `
     --queue-url        $env:REQ_Q `
     --message-body     "$msg"   `
     --message-group-id "jobs"

Write-Host "Messaggio inviato con job_id: $jobId"
