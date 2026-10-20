$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
py -3.12 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 necessário no computador de build' }
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw 'Instalação falhou' }
foreach ($role in @('Central', 'Agent')) {
    $entry = 'packaging/' + $role.ToLower() + '_entry.py'
    $windowMode = '--windowed'
    & .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onedir $windowMode --paths . --hidden-import smartpdv.desktop_entry --hidden-import smartpdv.__main__ --collect-all aiohttp --collect-all cryptography --collect-all PIL --add-data 'smartpdv/web;smartpdv/web' --name "SmartPDV-$role" $entry
    if ($LASTEXITCODE -ne 0) { throw "Build $role falhou" }
    & "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" "/DAppRole=$role" packaging\setup.iss
    if ($LASTEXITCODE -ne 0) { throw "Instalador $role falhou" }
}
