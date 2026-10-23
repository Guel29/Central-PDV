# Build do aplicativo/Agent. Não compila nem assina o driver de terceiros.
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$MSBuild,[string]$InnoSetup)
$ErrorActionPreference='Stop'
$root=Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Push-Location $root
try{
 & $MSBuild legacy-agent/SmartPDV-Agent-Win7.csproj /p:Configuration=Release
 if($LASTEXITCODE -ne 0){throw 'Build Agent Win7 falhou.'}
 # Compile a no-desktop/no-driver binary transport probe using the same managed client.
 $csc=Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe'
 & $csc /nologo /platform:x86 /out:legacy-agent/bin/Release/UsbTransportProbe.exe /main:SmartPDV.Legacy.UsbTransportProbe /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:System.Web.Extensions.dll /reference:System.Security.dll /reference:System.Management.dll legacy-agent/Agent.cs legacy-agent/UsbReader.cs legacy-agent/ScanKeyboard.cs legacy-agent/TimedKeys.cs tests/UsbTransportProbe.cs
 if($LASTEXITCODE -ne 0){throw 'Build do probe de transporte falhou.'}
 if($InnoSetup){
  & $InnoSetup legacy-agent/setup.iss
  if($LASTEXITCODE -ne 0){throw 'Instalador Agent falhou.'}
 }
 Write-Output 'Aplicativo compilado. Driver, sua assinatura e teste físico continuam sendo requisitos separados.'
}finally{Pop-Location}
