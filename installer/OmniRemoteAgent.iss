[Setup]
AppName=Omni Remote Agent
AppVersion=0.1.0
DefaultDirName={pf}\OmniRemoteAgent
DefaultGroupName=Omni Remote Agent
UninstallDisplayIcon={app}\OmniRemoteAgent.exe
OutputDir=..\dist
OutputBaseFilename=OmniRemoteAgentSetup
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64

[Files]
Source: "..\dist\OmniRemoteAgent\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Omni Remote Agent"; Filename: "{app}\OmniRemoteAgent.exe"

[Run]
Filename: "{app}\OmniRemoteAgent.exe"; Description: "Launch Omni Remote Agent"; Flags: nowait postinstall skipifsilent
