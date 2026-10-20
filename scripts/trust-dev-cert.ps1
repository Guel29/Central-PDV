$ErrorActionPreference = 'Stop'
# Consultar o próprio Python: instalações Microsoft Store redirecionam AppData.
$python = Join-Path (Split-Path $PSScriptRoot -Parent) '.venv\Scripts\python.exe'
$resolvedDirectory = & $python -m smartpdv.dev --print-data-directory
if ($LASTEXITCODE -ne 0) { throw 'Não foi possível localizar os dados físicos do laboratório.' }
$directory = ($resolvedDirectory | Select-Object -Last 1).Trim()
$config = Get-Content (Join-Path $directory 'central.json') -Raw | ConvertFrom-Json
if (!$config.development_only -or $config.host -ne '127.0.0.1') { throw 'Não é um certificado de laboratório loopback.' }
$certPath = Join-Path $directory 'central.crt'
$certificate = [System.Security.Cryptography.X509Certificates.X509Certificate2]::new($certPath)
$sha = [System.Security.Cryptography.SHA256]::Create()
try { $actual = ([BitConverter]::ToString($sha.ComputeHash($certificate.RawData))).Replace('-','').ToLowerInvariant() }
finally { $sha.Dispose() }
if ($actual -ne $config.fingerprint) { throw 'Fingerprint diferente da configuração local. Certificado não importado.' }
Write-Host 'Confiando no certificado TLS do laboratório local para o usuário Windows atual:' $actual
Import-Certificate -FilePath $certPath -CertStoreLocation Cert:\CurrentUser\Root | Out-Null
Write-Host 'Para remover após os testes: certmgr.msc > Autoridades de Certificação Raiz Confiáveis > certificado 127.0.0.1 com este fingerprint.'
