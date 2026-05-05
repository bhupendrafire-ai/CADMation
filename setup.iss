; Inno Setup Script for CADMation Enterprise
; Version: 3.5.0

[Setup]
AppName=CADMation Enterprise
AppVersion=3.6.7
DefaultDirName={localappdata}\CADMationEnterprise
DefaultGroupName=CADMation Enterprise
UninstallDisplayIcon={app}\CADMation_Enterprise.exe
OutputDir=installers
OutputBaseFilename=CADMation_v3.6.7_Setup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest
SetupIconFile=backend\resources\CADMation_Brand_Icon.ico

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\CADMation_Enterprise.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "backend\resources\CADMation_Brand_Icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\CADMation Enterprise"; Filename: "{app}\CADMation_Enterprise.exe"; WorkingDir: "{app}"; IconFilename: "{app}\CADMation_Brand_Icon.ico"
Name: "{commondesktop}\CADMation Enterprise"; Filename: "{app}\CADMation_Enterprise.exe"; WorkingDir: "{app}"; IconFilename: "{app}\CADMation_Brand_Icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\CADMation_Enterprise.exe"; Description: "{cm:LaunchProgram,CADMation Enterprise}"; Flags: nowait postinstall skipifsilent

[Code]
var
  ToolRoomUrlPage: TInputQueryWizardPage;

procedure InitializeWizard;
begin
  { Create the custom page }
  ToolRoomUrlPage := CreateInputQueryPage(wpSelectDir,
    'ToolRoom API Configuration', 'Enterprise Deployment Settings',
    'Please verify the ToolRoom ERP URL for your organization. This should only be changed by IT administrators.');
  
  { Add the input field }
  ToolRoomUrlPage.Add('API URL:', False);
  
  { Set default value }
  ToolRoomUrlPage.Values[0] := 'https://toolroom.saptasati.co.in';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  EnvContent: String;
begin
  if CurStep = ssPostInstall then
  begin
    { Create the .env file in the installation directory }
    { This ensures zero-touch deployment with organization defaults }
    EnvContent := 'TOOLROOM_API_URL=' + ToolRoomUrlPage.Values[0] + #13#10;
    SaveStringToFile(ExpandConstant('{app}\.env'), EnvContent, False);
  end;
end;
