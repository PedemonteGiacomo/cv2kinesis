# PowerShell script per leggere la coda dei risultati e scaricare il DICOM processato

# Recupera un messaggio dalla coda dei risultati
$msg = aws sqs receive-message `
    --queue-url $env:RES_Q `
    --max-number-of-messages 1 `
    --wait-time-seconds 10 `
    --output json | ConvertFrom-Json

if ($msg.Messages) {
    $body = $msg.Messages[0].Body | ConvertFrom-Json
    Write-Host "Messaggio ricevuto:"
    $body | ConvertTo-Json -Depth 5 | Write-Host

    # Se presente, usa direttamente l'URL firmato
    if ($body.dicom.url) {
        $url = $body.dicom.url
        Write-Host "Scarico DICOM da URL firmato: $url"
        Invoke-WebRequest -Uri $url -OutFile "processed_$($body.job_id).dcm"
        Write-Host "File salvato come processed_$($body.job_id).dcm"
    } else {
        # Altrimenti genera un presigned URL manualmente
        $bucket = $body.dicom.bucket
        $key    = $body.dicom.key
        $url = aws s3 presign "s3://$bucket/$key" --expires-in 3600
        Write-Host "Scarico DICOM da presigned URL: $url"
        Invoke-WebRequest -Uri $url -OutFile "processed_$($body.job_id).dcm"
        Write-Host "File salvato come processed_$($body.job_id).dcm"
    }

    # Cancella il messaggio dalla coda
    $receipt = $msg.Messages[0].ReceiptHandle
    aws sqs delete-message --queue-url $env:RES_Q --receipt-handle $receipt
    Write-Host "Messaggio cancellato dalla coda."
} else {
    Write-Host "Nessun messaggio trovato nella coda dei risultati."
}
