param([switch]$Remove, [switch]$StartNow)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$startup = [Environment]::GetFolderPath('Startup')
$linkPath = Join-Path $startup 'SmartPDV Agent - Python.lnk'
$shell = New-Object -ComObject WScript.Shell
$marker = 'SmartPDV Agent (LAN) - Python startup'
if (Test-Path $linkPath) {
    $existing = $shell.CreateShortcut($linkPath)
    if ($existing.Description -ne $marker) { throw 'Atalho existente nao reconhecido; nenhuma alteracao realizada.' }
}
if ($Remove) {
    if (Test-Path $linkPath) { Remove-Item -LiteralPath $linkPath }
    Write-Host 'Inicializacao automatica removida. O Agent em execucao nao foi encerrado.'
    exit 0
}
$python = Join-Path $root '.venv\Scripts\python.exe'
$pythonw = Join-Path $root '.venv\Scripts\pythonw.exe'
if (!(Test-Path $python) -or !(Test-Path $pythonw)) { throw 'Prepare .venv e configure o Agent neste usuario Windows primeiro.' }
# Verificar cadastro e DPAPI com o mesmo Python/usuario, inclusive Microsoft Store.
& $python -m smartpdv agent check-config
if ($LASTEXITCODE -ne 0) { throw 'Configure primeiro: .\.venv\Scripts\python.exe -m smartpdv agent setup' }
$link = $shell.CreateShortcut($linkPath)
$link.TargetPath = $pythonw
$link.Arguments = '-m smartpdv agent'
$link.WorkingDirectory = $root
$link.Description = $marker
$link.Save()
Write-Host 'Agent configurado para iniciar sem console ao entrar neste usuario Windows.'
Write-Host 'Mantenha esta pasta e .venv no mesmo local. Nao execute o laboratorio para testar o desktop real.'
if ($StartNow) {
    Start-Process -FilePath $pythonw -ArgumentList '-m','smartpdv','agent' -WorkingDirectory $root
    Write-Host 'Agent iniciado em segundo plano. Verifique o card na Central.'
}
