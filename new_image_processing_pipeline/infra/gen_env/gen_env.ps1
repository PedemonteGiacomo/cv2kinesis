# Genera env.ps1 con nuovi output WebSocket e ResultsQueue
$ws   = Get-OutputValue $imgOutputs "WebSocketEndpoint"
$resultsQ = Get-OutputValue $imgOutputs "ResultsQueueUrl"
...
$Env:WS_ENDPOINT      = $ws
$Env:RESULTS_QUEUE_URL= $resultsQ
