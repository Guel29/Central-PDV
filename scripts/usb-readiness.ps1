# Compatível com Windows PowerShell 2.0 / Windows 7 SP1.
# Somente leitura: não instala/captura USB, não abre portas e não lê cartões.
[CmdletBinding()]
param(
    [ValidateSet('Central', 'PDV')]
    [string]$Role = 'Central',
    [string]$ReaderInstanceId
)
$ErrorActionPreference = 'Stop'

$os = Get-WmiObject -Class Win32_OperatingSystem
Write-Output ('Papel: ' + $Role)
Write-Output ('Windows: ' + $os.Caption + '; versão: ' + $os.Version + '; arquitetura: ' + $os.OSArchitecture)
Write-Output ('Service Pack: ' + $os.ServicePackMajorVersion)
Write-Output 'Ponte USB: este inventário não verifica a instalação. Driver Windows 7 assinado e validação física são requisitos separados.'
Write-Output 'Este inventário não comprova assinatura de produção, transporte seguro ou compatibilidade VR.'

# Inventário PnP, não captura de Raw Input nem API de teclado.
$usb = @(Get-WmiObject -Class Win32_PnPEntity -Filter "PNPDeviceID LIKE 'USB%'" |
    Where-Object { $_.PNPDeviceID -match '^USB\\VID_[0-9A-F]{4}&PID_[0-9A-F]{4}\\' })
Write-Output 'Dispositivos USB físicos (um fabricante não identifica sozinho o modelo LS2208):'
foreach ($device in $usb) {
    $candidate = $device.PNPDeviceID -match '^USB\\VID_05E0&PID_[0-9A-F]{4}\\'
    New-Object PSObject -Property @{
        InstanceId = $device.PNPDeviceID
        Description = $device.Name
        PnpStatus = $device.Status
        PnpError = $device.ConfigManagerErrorCode
        SymbolMotorolaCandidate = $candidate
    } | Format-List
}

if ($ReaderInstanceId) {
    $match = @($usb | Where-Object { $_.PNPDeviceID -ieq $ReaderInstanceId })
    if ($match.Count -ne 1) { throw 'Identidade exata do leitor não encontrada. Nenhum dispositivo foi alterado.' }
    if ($match[0].PNPDeviceID -notmatch '^USB\\VID_05E0&PID_[0-9A-F]{4}\\') {
        throw 'Dispositivo fora do fabricante Symbol/Motorola esperado. Nenhum dispositivo foi alterado.'
    }
    Write-Output 'Identidade encontrada. Confirme o modelo na etiqueta física; nenhuma captura/associação foi feita.'
}

Write-Output 'Drivers USB/IP registrados (metadados WMI; IsSigned não substitui validação do catálogo):'
$drivers = @(Get-WmiObject -Class Win32_PnPSignedDriver |
    Where-Object { $_.DeviceName -match 'USB.?IP|VHCI' -or $_.DriverProviderName -match 'USB.?IP' })
if ($drivers.Count -eq 0) { Write-Output 'Nenhum driver USB/IP identificado no inventário.' }
foreach ($driver in $drivers) {
    New-Object PSObject -Property @{
        DeviceName = $driver.DeviceName
        Provider = $driver.DriverProviderName
        Version = $driver.DriverVersion
        InfName = $driver.InfName
        IsSigned = $driver.IsSigned
        Signer = $driver.Signer
    } | Format-List
}
Write-Output 'Fim do inventário. Sem alterações de driver, firewall, inicialização ou autorização VR.'
