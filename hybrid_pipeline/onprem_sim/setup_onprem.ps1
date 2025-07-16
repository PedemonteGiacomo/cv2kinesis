<#
.DESCRIPTION
  1) Verifica Docker Desktop, AWS CLI e Python
  2) Avvia il NAS NFS via docker-compose
  3) Abilita client NFS Windows (se non c'è)
  4) Monta la share NFS su Z:
  5) Avvia in background il producer di immagini
#>

$ErrorActionPreference = 'Stop'
$repoRoot   = Split-Path -Parent $PSScriptRoot
$compose    = "$PSScriptRoot\docker-compose.yml"
$producer   = "$PSScriptRoot\tools\onprem_image_producer.py"

Write-Host "`n=== 1/5  Check prerequisiti ==="
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker Desktop non trovato. Installalo e riprova."
}
if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
    throw "AWS CLI non trovato. ➜ https://docs.aws.amazon.com/cli/"
}
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python 3 non trovato."
}

Write-Host "`n=== 2/5  Avvio NAS NFS (Docker) ==="
docker compose -f $compose up -d
Start-Sleep -Seconds 5

Write-Host "`n=== 3/5  Abilito client NFS & monto Z: ==="
# abilita feature NFS client se necessario
if (-not (Get-WindowsOptionalFeature -Online -FeatureName NFS-Client).State -eq 'Enabled') {
    Enable-WindowsOptionalFeature -Online -FeatureName NFS-Client -NoRestart
    Write-Host "➡️  Riavvia Windows e riesegui lo script" -ForegroundColor Yellow
    exit
}
# tenta mount
$ip  = "127.0.0.1"
& mount -o anon \\$ip\data Z:
Write-Host "✅ nfs share montata su Z:\""

Write-Host "`n=== 4/5  Installo Pillow (solo prima volta) ==="
python -m pip install --quiet pillow

Write-Host "`n=== 5/5  Avvio producer immagini (job in background) ==="
Start-Job -Name ImageProducer -ScriptBlock {
    param($script) python $script
} -ArgumentList $producer | Out-Null
Get-Job ImageProducer | Format-Table Id,State,HasMoreData -AutoSize

Write-Host "`n🎉  Ambiente on-prem pronto! (Unità Z:\ collegata)"
# Usage instructions
# PS> cd hybrid_pipeline\onprem_sim
# PS> .\setup_onprem.ps1

