#ifndef AppRole
  #define AppRole "Central"
#endif
[Setup]
AppId=SmartPDV-{#AppRole}
AppName=Smart PDV {#AppRole}
AppVersion=1.0.7
MinVersion=10.0
DefaultDirName={localappdata}\Programs\SmartPDV-{#AppRole}
DefaultGroupName=Smart PDV {#AppRole}
OutputDir=..\dist\installers
OutputBaseFilename=SmartPDV-{#AppRole}-Setup
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2
SolidCompression=yes
UninstallDisplayIcon={app}\SmartPDV-{#AppRole}.exe
[Files]
Source: "..\dist\SmartPDV-{#AppRole}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
[Tasks]
#if AppRole == "Agent"
Name: "autostart"; Description: "Iniciar Agent em segundo plano ao entrar no Windows"
#else
Name: "autostart"; Description: "Iniciar ao entrar no Windows"; Flags: unchecked
#endif
[Icons]
Name: "{group}\SmartPDV {#AppRole}"; Filename: "{app}\SmartPDV-{#AppRole}.exe"
Name: "{group}\Configuração inicial"; Filename: "{app}\SmartPDV-{#AppRole}.exe"; Parameters: "setup"
#if AppRole == "Central"
Name: "{group}\Confiar no certificado local"; Filename: "{app}\SmartPDV-Central.exe"; Parameters: "trust-certificate"
Name: "{group}\Cadastrar PDV"; Filename: "{app}\SmartPDV-Central.exe"; Parameters: "add-pdv"
#endif
#if AppRole == "Agent"
Name: "{userstartup}\SmartPDV Agent"; Filename: "{app}\SmartPDV-Agent.exe"; Parameters: "--background"; Tasks: autostart
#else
Name: "{userstartup}\SmartPDV Central"; Filename: "{app}\SmartPDV-Central.exe"; Tasks: autostart
#endif
[Run]
Filename: "{app}\SmartPDV-{#AppRole}.exe"; Parameters: "setup"; Description: "Configurar {#AppRole}"; Flags: postinstall skipifsilent; Check: NeedsConfiguration

#if AppRole == "Central"
Filename: "{app}\SmartPDV-Central.exe"; Parameters: "trust-certificate"; Description: "Configurar confiança no certificado HTTPS local"; Flags: postinstall skipifsilent unchecked
Filename: "{app}\SmartPDV-Central.exe"; Description: "Abrir Central"; Flags: postinstall skipifsilent unchecked
#endif

[Code]
function NeedsConfiguration(): Boolean;
begin
  Result := not FileExists(ExpandConstant('{localappdata}\SmartPDV\{#AppRole}\{#AppRole}.json'));
end;
