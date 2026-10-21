[Setup]
AppId=SmartPDV-Agent-Win7
AppName=SmartPDV Agent Windows 7
AppVersion=0.1.3
DefaultDirName={localappdata}\Programs\SmartPDV-Agent-Win7
DefaultGroupName=SmartPDV Agent Win7
PrivilegesRequired=lowest
MinVersion=6.1sp1
OutputDir=dist
OutputBaseFilename=SmartPDV-Agent-Win7-Setup
Compression=lzma2
SolidCompression=yes
UninstallDisplayIcon={app}\SmartPDV-Agent-Win7.exe
[Files]
Source: "bin\Release\SmartPDV-Agent-Win7.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "bin\Release\SmartPDV-Agent-Win7.exe.config"; DestDir: "{app}"; Flags: ignoreversion
[Tasks]
Name: startup; Description: "Iniciar o Agent em segundo plano apos entrar no Windows"
[Icons]
Name: "{group}\Configurar PDV"; Filename: "{app}\SmartPDV-Agent-Win7.exe"; Parameters: "setup"
Name: "{group}\Iniciar Agent"; Filename: "{app}\SmartPDV-Agent-Win7.exe"
Name: "{userstartup}\SmartPDV Agent Win7"; Filename: "{app}\SmartPDV-Agent-Win7.exe"; Parameters: "--background"; Tasks: startup
[Run]
Filename: "{app}\SmartPDV-Agent-Win7.exe"; Parameters: "setup"; Description: "Cadastrar este PDV usando o pareamento da Central"; Flags: postinstall skipifsilent waituntilterminated; Check: NeedsPairing
Filename: "{app}\SmartPDV-Agent-Win7.exe"; Parameters: "--background"; Description: "Iniciar Agent"; Flags: postinstall skipifsilent nowait
[Code]
function NeedsPairing(): Boolean;
begin
  Result := not FileExists(ExpandConstant('{localappdata}\SmartPDV\agent\agent.json'));
end;

function InitializeSetup(): Boolean;
var Release: Cardinal;
begin
  Result := RegQueryDWordValue(HKLM32, 'SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full', 'Release', Release) and (Release >= 528040);
  if not Result then
    MsgBox('Instale o Microsoft .NET Framework 4.8 antes de continuar. Este Agent exige Windows 7 SP1 ou superior. O instalador nao baixa componentes da internet.', mbError, MB_OK);
end;
