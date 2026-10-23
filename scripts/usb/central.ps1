# Windows 10/11, PowerShell 5.1, executar como administrador.
[CmdletBinding()]
param(
 [ValidateSet('Prepare','Remove')][string]$Action='Prepare',
 [Parameter(Mandatory=$true)][string]$ReaderInstanceId,
 [string[]]$PdvAddresses=@(),
 [ValidateRange(1,65535)][int]$CentralPort=8443
)
$ErrorActionPreference='Stop'
$principal=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Executar como administrador.'}
if($ReaderInstanceId -notmatch '^USB\\VID_05E0&PID_[0-9A-F]{4}\\[^\\]+$'){throw 'Identidade Symbol/Motorola exata obrigatória. Não selecionar teclado genérico.'}
$exe=Join-Path $env:ProgramFiles 'usbipd-win\usbipd.exe'
if(-not(Test-Path -LiteralPath $exe)){throw 'Instale usbipd-win do projeto oficial antes: https://github.com/dorssel/usbipd-win/releases'}
$raw=& $exe state
if($LASTEXITCODE -ne 0){throw 'usbipd state falhou.'}
$devices=($raw | ConvertFrom-Json).Devices
$d=@($devices | Where-Object {$_.InstanceId -eq $ReaderInstanceId})
if($d.Count -ne 1){throw 'Identidade exata não encontrada no serviço USB.'}
if($Action -eq 'Remove'){
 if($d[0].ClientIPAddress){throw 'Desconecte o leitor no Smart Controle antes de remover.'}
 if($d[0].PersistedGuid){
  & $exe unbind --guid $d[0].PersistedGuid
 }elseif($d[0].BusId){
  & $exe unbind --busid $d[0].BusId
 }else{throw 'Compartilhamento do leitor não encontrado.'}
 if($LASTEXITCODE -ne 0){throw 'Falha ao liberar driver do leitor.'}
 # Keep raw USB/IP blocked while any other share exists; never remove user shares.
 $raw=& $exe state
 if($LASTEXITCODE -ne 0){throw 'Não foi possível confirmar dispositivos compartilhados; bloqueio mantido.'}
 if(@(($raw|ConvertFrom-Json).Devices | Where-Object {$_.PersistedGuid}).Count){
  throw 'Há outros compartilhamentos USB/IP. Bloqueio bruto mantido para não expô-los.'
 }
 Get-NetFirewallRule -Name SmartPDV-USB-LAN -ErrorAction SilentlyContinue | Remove-NetFirewallRule
 Get-NetFirewallRule -Name SmartPDV-USB-Raw-Block -ErrorAction SilentlyContinue | Remove-NetFirewallRule
 Write-Output 'Leitor liberado e regras próprias removidas. Remova usbipd-win por Aplicativos se não houver outro uso.'
 return
}
if(-not $d[0].BusId){throw 'Conecte fisicamente o leitor exato para preparar.'}
if($d[0].ClientIPAddress){throw 'Dispositivo já está em uso.'}
if($PdvAddresses.Count -eq 0){throw 'Informe somente os IPs LAN dos PDVs autorizados.'}
foreach($address in $PdvAddresses){
 $ip=[Net.IPAddress]::Parse($address);$b=$ip.GetAddressBytes()
 if($b.Length -ne 4 -or -not($b[0] -eq 10 -or ($b[0] -eq 172 -and $b[1] -ge 16 -and $b[1] -le 31) -or ($b[0] -eq 192 -and $b[1] -eq 168))){throw 'Somente IPv4 LAN privado exato é permitido.'}
}
if((Get-NetFirewallProfile | Where-Object {-not $_.Enabled}).Count){throw 'Ative o Firewall do Windows em todos os perfis antes de compartilhar.'}
# Block wins over the vendor's broad inbound allow rule; loopback is not a LAN route.
Get-NetFirewallRule -Name SmartPDV-USB-Raw-Block -ErrorAction SilentlyContinue | Remove-NetFirewallRule
New-NetFirewallRule -Name SmartPDV-USB-Raw-Block -DisplayName 'SmartPDV bloqueio USBIP bruto' -Direction Inbound -Action Block -Protocol TCP -LocalPort 3240 -Profile Any | Out-Null
Get-NetFirewallRule -Name SmartPDV-USB-LAN -ErrorAction SilentlyContinue | Remove-NetFirewallRule
New-NetFirewallRule -Name SmartPDV-USB-LAN -DisplayName 'SmartPDV TLS PDVs autorizados' -Direction Inbound -Action Allow -Protocol TCP -LocalPort $CentralPort -RemoteAddress $PdvAddresses -Profile Private,Domain | Out-Null
& $exe bind --busid $d[0].BusId
if($LASTEXITCODE -ne 0){throw 'Falha ao preparar leitor. Bloqueio da porta bruta foi mantido.'}
Write-Output 'Somente este leitor foi preparado. Confirme a etiqueta LS2208 e selecione sua identidade no painel.'
Write-Output 'Não abrir TCP 3240 na LAN. Pareamento/USB usam a porta TLS existente da Central.'
