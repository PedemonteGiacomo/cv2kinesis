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
  algo_id = "processing_1"  # Cambia se vuoi testare altri algoritmi
  pacs    = @{
     study_id  = "D53-03"   # Sostituisci con uno study_id valido
     series_id = "6_120_40_BODY-SHARP_AICE_170641.498"  # Sostituisci con una series valida
     image_id  = "IM-0856-0001.dcm"  # Sostituisci con un image valido
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
