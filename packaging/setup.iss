#ifndef AppRole
  #define AppRole "Central"
#endif
[Setup]
AppId=SmartPDV-{#AppRole}
AppName=Smart PDV {#AppRole}
AppVersion=1.0.0
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
Name: "autostart"; Description: "Iniciar ao entrar no Windows"; Flags: unchecked
[Icons]
Name: "{group}\SmartPDV {#AppRole}"; Filename: "{app}\SmartPDV-{#AppRole}.exe"
Name: "{group}\Configuração inicial"; Filename: "{app}\SmartPDV-{#AppRole}.exe"; Parameters: "setup"
#if AppRole == "Central"
Name: "{group}\Cadastrar supervisor"; Filename: "{app}\SmartPDV-Central.exe"; Parameters: "add-supervisor"
Name: "{group}\Cadastrar PDV"; Filename: "{app}\SmartPDV-Central.exe"; Parameters: "add-pdv"
#endif
Name: "{userstartup}\SmartPDV {#AppRole}"; Filename: "{app}\SmartPDV-{#AppRole}.exe"; Tasks: autostart
[Run]
Filename: "{app}\SmartPDV-{#AppRole}.exe"; Parameters: "setup"; Description: "Configurar {#AppRole}"; Flags: postinstall skipifsilent
