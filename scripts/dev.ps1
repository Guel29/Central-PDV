param([switch]$TrustLocalCertificate)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (!(Test-Path '.venv\Scripts\python.exe')) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Instale Python 3.12 x64 antes de continuar.' }
}
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Não foi possível preparar as dependências.' }
& .\.venv\Scripts\python.exe -m smartpdv.dev --prepare
if ($LASTEXITCODE -ne 0) { throw 'Configuração do laboratório falhou.' }
if ($TrustLocalCertificate) { & "$PSScriptRoot\trust-dev-cert.ps1" }
& .\.venv\Scripts\python.exe -m smartpdv.dev --open
if ($LASTEXITCODE -ne 0) { throw 'O laboratório encerrou com erro.' }
