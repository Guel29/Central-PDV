# Windows 7 SP1, .NET 4.8, PowerShell 2.0. Administrador.
# Requer pacote LEGÍTIMO previamente assinado e SignTool oficial compatível com o host.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$Package,
 [Parameter(Mandatory=$true)][string]$SignTool,
 [Parameter(Mandatory=$true)][string]$DevCon,
 [Parameter(Mandatory=$true)][ValidatePattern('^[a-fA-F0-9]{64}$')][string]$ExpectedExeSha256
)
$ErrorActionPreference='Stop'
$principal=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Executar como administrador.'}
$root=(Resolve-Path -LiteralPath $Package).Path
$dest=Join-Path $env:ProgramData 'SmartPDV-USB\Client'
if(Test-Path -LiteralPath $dest){throw 'Pasta já existe; não sobrescrever instalação anterior. Remova-a pelo procedimento documentado.'}
foreach($name in @('usbip.exe','usbip_vhci.inf','usbip_vhci.sys','usbip_vhci.cat','usb.ids','LICENSE')){
 if(-not(Test-Path -LiteralPath (Join-Path $root $name) -PathType Leaf)){throw ('Pacote incompleto: '+$name)}
}
if(-not(Test-Path -LiteralPath $SignTool -PathType Leaf)){throw 'SignTool oficial ausente.'}
foreach($name in @('usbip_vhci.sys','usbip_vhci.inf')){
 & $SignTool verify /kp /o '2:6.1.7601' /v /c (Join-Path $root 'usbip_vhci.cat') (Join-Path $root $name)
 if($LASTEXITCODE -ne 0){throw 'Assinatura kernel/catálogo não aceita; instalação cancelada.'}
}
$sha=[Security.Cryptography.SHA256]::Create()
try{
 $stream=[IO.File]::OpenRead((Join-Path $root 'usbip.exe'))
 try{$actual=[BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-','')}finally{$stream.Dispose()}
}finally{$sha.Dispose()}
if($actual -ine $ExpectedExeSha256){throw 'Hash do executável diferente do build revisado.'}
$signature=Get-AuthenticodeSignature -LiteralPath $DevCon
if($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Microsoft'){throw 'DevCon oficial assinado Microsoft obrigatório.'}
$existing=@(Get-WmiObject Win32_PnPSignedDriver | Where-Object {$_.HardWareID -ieq 'ROOT\USBIP_VHCI'})
if($existing.Count){throw 'Controlador USBIP já existente; não será substituído silenciosamente.'}
New-Item -ItemType Directory -Path $dest | Out-Null
# Administradores/SYSTEM gravam; usuários podem somente ler/executar.
& icacls.exe $dest /grant:r '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-545:(OI)(CI)RX' | Out-Null
if($LASTEXITCODE -ne 0){throw 'Falha ao proteger pasta; instalação não iniciada.'}
& icacls.exe $dest /inheritance:r | Out-Null
if($LASTEXITCODE -ne 0){throw 'Falha ao remover herança; instalação não iniciada.'}
foreach($name in @('usbip.exe','usbip_vhci.inf','usbip_vhci.sys','usbip_vhci.cat','usb.ids','LICENSE')){
 Copy-Item -LiteralPath (Join-Path $root $name) -Destination (Join-Path $dest $name)
}
Push-Location $dest
try{
 foreach($name in @('usbip_vhci.sys','usbip_vhci.inf')){
  & $SignTool verify /kp /o '2:6.1.7601' /v /c (Join-Path $dest 'usbip_vhci.cat') (Join-Path $dest $name)
  if($LASTEXITCODE -ne 0){throw 'Pacote copiado não passou verificação. Nada será executado.'}
 }
 $sha=[Security.Cryptography.SHA256]::Create();$stream=[IO.File]::OpenRead((Join-Path $dest 'usbip.exe'))
 try{$copied=[BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-','')}finally{$stream.Dispose();$sha.Dispose()}
 if($copied -ine $ExpectedExeSha256){throw 'Executável copiado não confere com build revisado.'}
 & $DevCon install (Join-Path $dest 'usbip_vhci.inf') 'root\usbip_vhci'
 if($LASTEXITCODE -ne 0){throw 'Instalação do controlador retornou falha. Componente não habilitado.'}
 $driver=@(Get-WmiObject Win32_PnPSignedDriver | Where-Object {$_.HardWareID -ieq 'ROOT\USBIP_VHCI' -and $_.IsSigned})
 if($driver.Count -ne 1){throw 'Driver assinado instalado não confirmado; componente não habilitado.'}
 # No secret: marker and executable hash are readable; only admin can change them.
 Add-Type -AssemblyName System.Web.Extensions
 $serializer=New-Object System.Web.Script.Serialization.JavaScriptSerializer
 $approval=$serializer.Serialize(@{backend='cezanne-v0.1.0';exe_sha256=$actual;driver_id=$driver[0].DeviceID;inf_name=$driver[0].InfName})
 [IO.File]::WriteAllText((Join-Path $dest 'approved.json'),$approval,[Text.Encoding]::UTF8)
}finally{Pop-Location}
Write-Output 'Cliente preparado. Instale/atualize o Agent Win7, preserve o pareamento e reinicie-o.'
Write-Output 'Este passo não confirma o LS2208 nem o VR. Nenhuma regra de firewall foi criada no PDV.'
