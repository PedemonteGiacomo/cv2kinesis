# PowerShell script per inviare un job di test alla coda SQS come farebbe un frontend


# Recupera gli output dello stack (se non già fatto)
$stack = aws cloudformation describe-stacks --stack-name ImgPipeline | ConvertFrom-Json
$outs  = $stack.Stacks[0].Outputs

# Imposta l'algo_id desiderato qui
$algo_id = "processing_1"

# Trova la coda giusta per l'algo scelto
$env:REQ_Q = ($outs | Where-Object { $_.OutputKey -eq "ImageRequestsQueueUrl$algo_id" }).OutputValue
$env:RES_Q = ($outs | Where-Object { $_.OutputKey -like "*ImageResults*" }).OutputValue
$env:OUT_BUCKET = ($outs | Where-Object { $_.OutputKey -like "*Output*" }).OutputValue

Write-Host "REQ_Q      = $env:REQ_Q"
Write-Host "RES_Q      = $env:RES_Q"
Write-Host "OUT_BUCKET = $env:OUT_BUCKET"

# Crea un nuovo job id
$jobId = "job-{0}" -f ([guid]::NewGuid())

# Prepara il messaggio di richiesta processing (JSON valido)
$msg = @{
  job_id  = $jobId
  algo_id = $algo_id
  pacs    = @{
     study_id  = "liver1/phantomx_abdomen_pelvis_dataset/D55-01"
     series_id = "300/AiCE_BODY-SHARP_300_172938.900"
     image_id  = "IM-0135-0001.dcm"
     scope     = "image"
  }
  callback = @{ queue_url = $env:RES_Q }
} | ConvertTo-Json -Depth 4 -Compress

# Stampa il JSON che verrà inviato
Write-Host "JSON inviato:"
Write-Host $msg

# Invia il messaggio alla coda delle richieste
aws sqs send-message `
     --queue-url        $env:REQ_Q `
     --message-body     "$msg"   `
     --message-group-id $jobId

Write-Host "Messaggio inviato con job_id: $jobId"
