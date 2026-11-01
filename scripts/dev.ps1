param([switch]$SkipInstall)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $projectRoot
$occupiedPorts = @(Get-NetTCPConnection -LocalPort @(8000, 3100) -State Listen -ErrorAction SilentlyContinue)
if ($occupiedPorts.Count -gt 0) {
    $portList = ($occupiedPorts | Select-Object -ExpandProperty LocalPort -Unique) -join ', '
    throw "Portas ocupadas: $portList. Encerre a instância correspondente antes de iniciar o CryptoLab."
}
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    & python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Não foi possível criar o ambiente Python.' }
}
$pythonExe = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not $SkipInstall) {
    & $pythonExe -m pip install -r backend/requirements.lock.txt
    if ($LASTEXITCODE -ne 0) { throw 'Falha na instalação Python.' }
    & $pythonExe -m pip install --no-deps -e ./backend
    if ($LASTEXITCODE -ne 0) { throw 'Falha na instalação do pacote local.' }
    & npm ci
    if ($LASTEXITCODE -ne 0) { throw 'Falha na instalação npm.' }
}
$env:LIVE_TRADING_ENABLED = 'false'
$apiProcess = $null
$workerProcess = $null
try {
    $apiProcess = Start-Process -FilePath $pythonExe -ArgumentList @('-m','uvicorn','cryptolab.api:app','--host','127.0.0.1','--port','8000') -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru
    $workerProcess = Start-Process -FilePath $pythonExe -ArgumentList @('-m','cryptolab.worker') -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru
    Write-Host 'CryptoLab: http://127.0.0.1:3100 | API: http://127.0.0.1:8000/docs'
    Write-Host 'A coleta inicial pode levar alguns segundos. Ctrl+C encerra os processos iniciados aqui.'
    & npm run dev
} finally {
    foreach ($ownedProcess in @($apiProcess, $workerProcess)) {
        if ($ownedProcess -and -not $ownedProcess.HasExited) { Stop-Process -Id $ownedProcess.Id -ErrorAction SilentlyContinue }
    }
}
