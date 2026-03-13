; ── BackupTool Inno Setup Script ─────────────────────────────────────────────
; Builds: BackupToolSetup.exe
; Requires: Inno Setup 6  (https://jrsoftware.org/isinfo.php)
; Build PyInstaller dist first:  build.bat

#define AppName      "BackupTool"
#define AppVersion   "1.0.0"
#define AppPublisher "Christof"
#define AppExeName   "BackupToolTray.exe"
#define ServiceExe   "BackupToolService.exe"
#define ServiceName  "BackupToolSvc"
#define SvcDisplay   "BackupTool Sync Service"
#define DistDir      "dist\BackupTool"

[Setup]
AppId={{A3F2C1D4-7B8E-4F2A-9C6D-1E5B3A7F2C8D}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL=https://github.com
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
OutputBaseFilename=BackupToolSetup
OutputDir=dist
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#AppExeName}
SetupIconFile=assets\icon_active.ico
; If no .ico exists, comment out the line above

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "german";  MessagesFile: "compiler:Languages\German.isl"

[Files]
; All PyInstaller output
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\BackupTool Tray";    Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall BackupTool"; Filename: "{uninstallexe}"

[Registry]
; Tray app autostart on Windows login (current user)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
    ValueType: string; ValueName: "BackupTool"; \
    ValueData: """{app}\{#AppExeName}"""; \
    Flags: uninsdeletevalue

[Run]
; Install and start the Windows service after copying files
Filename: "{app}\{#ServiceExe}"; Parameters: "install"; \
    Flags: runhidden waituntilterminated; \
    StatusMsg: "Installing BackupTool service..."

Filename: "sc.exe"; Parameters: "start {#ServiceName}"; \
    Flags: runhidden waituntilterminated; \
    StatusMsg: "Starting BackupTool service..."; \
    AfterInstall: WriteDefaultConfig

; Launch tray app immediately (user sees tray icon right away)
Filename: "{app}\{#AppExeName}"; \
    Flags: nowait postinstall skipifsilent; \
    Description: "Launch BackupTool tray app now"

[UninstallRun]
; Stop and remove service on uninstall
Filename: "sc.exe"; Parameters: "stop {#ServiceName}"; \
    Flags: runhidden waituntilterminated; RunOnceId: "StopSvc"
Filename: "{app}\{#ServiceExe}"; Parameters: "remove"; \
    Flags: runhidden waituntilterminated; RunOnceId: "RemoveSvc"

[Code]
procedure WriteDefaultConfig();
var
  ConfigDir, ConfigFile, Json: String;
begin
  ConfigDir  := ExpandConstant('{commonappdata}\BackupTool');
  ConfigFile := ConfigDir + '\config.json';
  if not DirExists(ConfigDir) then
    CreateDir(ConfigDir);
  if not FileExists(ConfigFile) then
  begin
    Json := '{'                                        + #13#10 +
            '  "folder_pairs": [],'                   + #13#10 +
            '  "retention_days": 30,'                 + #13#10 +
            '  "scan_interval_minutes": 30,'          + #13#10 +
            '  "recycle_bin_subdir": "__RecycleBin__",' + #13#10 +
            '  "log_level": "INFO"'                   + #13#10 +
            '}';
    SaveStringToFile(ConfigFile, Json, False);
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    // Remove tray autostart
    RegDeleteValue(HKCU,
      'Software\Microsoft\Windows\CurrentVersion\Run',
      'BackupTool');
  end;
end;
