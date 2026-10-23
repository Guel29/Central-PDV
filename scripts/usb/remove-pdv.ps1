# Windows 7 SP1; PowerShell 2.0/.NET 4.8. Administrador.
# DevCon é ferramenta oficial WDK, arquitetura correspondente ao computador.
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$DevCon)
$ErrorActionPreference='Stop'
$principal=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Executar como administrador.'}
if(Get-Process -Name SmartPDV-Agent-Win7 -ErrorAction SilentlyContinue){throw 'Encerre o Agent Win7 antes de remover.'}
$signature=Get-AuthenticodeSignature -LiteralPath $DevCon
if($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Microsoft'){throw 'DevCon oficial assinado pela Microsoft obrigatório.'}
$dest=Join-Path $env:ProgramData 'SmartPDV-USB\Client'
Add-Type -AssemblyName System.Web.Extensions
$serializer=New-Object System.Web.Script.Serialization.JavaScriptSerializer
$approved=$serializer.DeserializeObject([IO.File]::ReadAllText((Join-Path $dest 'approved.json')))
$id=[string]$approved['driver_id'];$inf=[string]$approved['inf_name']
if($id -notmatch '^ROOT\\(?:SYSTEM|USBIP|USBIP_VHCI)\\[0-9]+$' -or $inf -notmatch '^oem[0-9]+\.inf$'){throw 'Identidade de instalação não reconhecida; não remover driver arbitrário.'}
$driver=@(Get-WmiObject Win32_PnPSignedDriver | Where-Object {$_.DeviceID -eq $id -and $_.InfName -eq $inf -and $_.HardWareID -ieq 'ROOT\USBIP_VHCI'})
if($driver.Count -ne 1){throw 'Driver instalado mudou. Verifique no Gerenciador de Dispositivos; nenhum driver foi removido.'}
& $DevCon remove ('@'+$id)
if($LASTEXITCODE -ne 0){throw 'Remoção do dispositivo falhou ou exige reinício; reinicie antes de continuar.'}
& pnputil.exe -d $inf
if($LASTEXITCODE -ne 0){throw 'Dispositivo removido, pacote INF ainda presente. Não apagar manualmente o DriverStore.'}
Remove-Item -LiteralPath (Join-Path $dest 'approved.json')
# Leave binaries/license in place for inspection; never recursively remove unknown files.
Write-Output 'Driver e aprovação removidos. Nenhuma regra de firewall foi criada/removida neste PDV.'
Write-Output 'Pode remover a pasta ProgramData\SmartPDV-USB\Client após conferir arquivos próprios.'
Write-Output 'Remova Agent Win7 por Programas e Recursos somente se também quiser remover o acesso remoto.'
