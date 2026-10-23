# Verificação somente de leitura. Não instala e não confere aprovação de uso.
# Requer SignTool oficial do SDK/WDK no host Windows de verificação.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Package,
    [Parameter(Mandatory=$true)][string]$SignTool,
    [ValidateSet('PDV','Central')][string]$Role = 'PDV'
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath $Package).Path
if (-not (Test-Path -LiteralPath $SignTool -PathType Leaf)) { throw 'SignTool oficial não encontrado.' }
$name = 'usbip_vhci'
if ($Role -eq 'Central') { $name = 'usbip_stub' }
$sys = Join-Path $root ($name + '.sys')
$cat = Join-Path $root ($name + '.cat')
$inf = Join-Path $root ($name + '.inf')
foreach ($file in @($sys, $cat, $inf, (Join-Path $root 'usbip.exe'))) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw ('Pacote incompleto: ' + $file) }
}
# /kp aplica política de kernel; /o exige considerar Windows 7 SP1.
# /c exige que o SYS seja membro do catálogo assinado, não apenas um CAT qualquer.
& $SignTool verify /kp /o '2:6.1.7601' /v /c $cat $sys
if ($LASTEXITCODE -ne 0) { throw 'Assinatura kernel/catálogo não aceita. Instalação bloqueada.' }
& $SignTool verify /kp /o '2:6.1.7601' /v /c $cat $inf
if ($LASTEXITCODE -ne 0) { throw 'INF não validado no catálogo. Instalação bloqueada.' }
Write-Output 'Verificação SignTool aprovada no host. Não equivale a homologação no Windows 7 físico.'
Write-Output 'Pacote não instalado; validar arquitetura, cadeia de confiança e carregamento no Windows 7 de destino.'
