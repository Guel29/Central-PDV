# Execute somente no computador de BUILD Windows, não no caixa Windows 7.
# Não instala drivers/certificados, não muda boot nem configura rede.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Source,
    [ValidateSet('x64','x86')][string]$Architecture = 'x64',
    [Parameter(Mandatory=$true)][string]$MSBuild
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath $Source).Path
$manifest = Get-Content -LiteralPath (Join-Path $root 'smartpdv-source.json') -Raw | ConvertFrom-Json
if ($manifest.commit -ne '44063583a5c3e20ec459bddadc9aae37f73bda10') { throw 'Revisão não aprovada.' }
# Verificar antes de executar qualquer projeto MSBuild da fonte externa.
foreach ($entry in $manifest.sha256.PSObject.Properties) {
    $path = Join-Path $root $entry.Name
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value) {
        throw ('Fonte alterada: ' + $entry.Name)
    }
}
if (-not (Test-Path -LiteralPath $MSBuild -PathType Leaf)) { throw 'MSBuild.exe não encontrado.' }
# Release não é assinatura de produção. A saída fica explicitamente bloqueada.
$marker = Join-Path $root 'NOT-FOR-INSTALLATION.txt'
Set-Content -LiteralPath $marker -Value 'UNSIGNED / NOT VALIDATED FOR PRODUCTION. Do not install on a PDV.'
Push-Location $root
try {
    & $MSBuild 'usbip_win.sln' '/t:Rebuild' '/m:2' '/p:Configuration=Release' "/p:Platform=$Architecture" '/p:TargetVersion=Windows7' '/p:WindowsTargetPlatformVersion=10.0.18362.0' '/p:SignMode=Off' '/p:DriverSignMode=Off'
    if ($LASTEXITCODE -ne 0) { throw 'Build falhou; não há pacote liberado.' }
    Write-Output 'Build terminou. Saída NÃO assinada nem liberada para instalação.'
    Write-Output 'Assinatura de produção, verificação de catálogo/kernel e testes Windows 7 continuam pendentes.'
} finally {
    Pop-Location
}
