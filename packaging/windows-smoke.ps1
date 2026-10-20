$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$smoke = Join-Path $env:RUNNER_TEMP 'SmartPDV-native-smoke'
New-Item -ItemType Directory -Force -Path $smoke | Out-Null
foreach ($role in @('Central','Agent')) {
    $installer = Join-Path $root "dist\installers\SmartPDV-$role-Setup.exe"
    $destination = Join-Path $smoke $role
    $install = Start-Process -FilePath $installer -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',('/DIR="' + $destination + '"'),'/TASKS=""') -PassThru -Wait
    if ($install.ExitCode -ne 0) { throw "Instalacao $role falhou: $($install.ExitCode)" }
    $app = Join-Path $destination "SmartPDV-$role.exe"
    if (!(Test-Path $app)) { throw "Executavel $role ausente" }
    $bytes = [IO.File]::ReadAllBytes($app)
    $pe = [BitConverter]::ToInt32($bytes, 0x3c)
    $subsystem = [BitConverter]::ToUInt16($bytes, $pe + 24 + 68)
    if ($subsystem -ne 2) { throw "$role nao foi compilado como aplicativo Windows sem console" }
}
$env:SMARTPDV_SMOKE_DATA = Join-Path $smoke 'central-data'
& .\.venv\Scripts\python.exe -c 'import os; from pathlib import Path; from smartpdv.dev import initialize; initialize(Path(os.environ["SMARTPDV_SMOKE_DATA"]),port=18443)'
if ($LASTEXITCODE -ne 0) { throw 'Preparacao dos dados de teste falhou' }
$process = Start-Process -FilePath (Join-Path $smoke 'Central\SmartPDV-Central.exe') -ArgumentList @('--no-browser','--data',('"' + $env:SMARTPDV_SMOKE_DATA + '"')) -PassThru
try {
    & .\.venv\Scripts\python.exe tests\packaged_probe.py (Join-Path $env:SMARTPDV_SMOKE_DATA 'central.crt') 'https://127.0.0.1:18443'
    if ($LASTEXITCODE -ne 0) {
        $diagnostic = Join-Path $env:SMARTPDV_SMOKE_DATA 'startup-error.txt'
        if (Test-Path $diagnostic) {
            $detail = Get-Content $diagnostic -Raw
            Write-Host $detail
            Add-Content -Path $env:GITHUB_STEP_SUMMARY -Value $detail
            Write-Host ('::error title=Central startup::' + ($detail -replace '\r?\n', '%0A'))
        }
        if ($process.HasExited) { Write-Host 'Central exit code:' $process.ExitCode }
        throw 'Central instalada nao passou no teste HTTPS'
    }
} finally {
    if (!$process.HasExited) { Stop-Process -Id $process.Id -Force }
}
$agent = Start-Process -FilePath (Join-Path $smoke 'Agent\SmartPDV-Agent.exe') -ArgumentList @('--background','--data',('"' + (Join-Path $smoke 'agent-unconfigured') + '"')) -PassThru
if (!$agent.WaitForExit(20000)) { Stop-Process -Id $agent.Id -Force; throw 'Agent abriu wizard ou bloqueou inicializacao em segundo plano sem configuracao' }
if ($agent.ExitCode -ne 0) { throw 'Agent em segundo plano encerrou com erro' }
Write-Host 'PASS: dois instaladores executados, dois aplicativos GUI sem console, Central HTTPS funcional, Agent sem wizard no login.'
