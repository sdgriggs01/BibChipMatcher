; Inno Setup script for Bib Chip Matcher.
;
; Installs per-user (no admin prompt) into %LocalAppData%\Programs\BibChipMatcher
; -- the same pattern VS Code's "User Installer" uses. Expects the
; PyInstaller onedir build to already exist at ..\build\dist\BibChipMatcher
; (see bibchipmatcher.spec) and MyAppVersion to be passed on the command line:
;
;   ISCC.exe /DMyAppVersion=1.2.3 installer.iss

#define MyAppName "BibChipMatcher"
#ifndef MyAppVersion
  #define MyAppVersion "0.0.1"
#endif
#define MyAppExeName "BibChipMatcher.exe"
#define MyAppPublisher "Simon Griggs"

[Setup]
; Fixed AppId so future versions upgrade in place instead of installing
; side-by-side. Do not change this.
AppId={{FF6F5168-4E18-43FB-804C-6E2DE0CEDE44}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; No admin rights required or requested -- installs entirely into the
; current user's own profile.
PrivilegesRequired=lowest
OutputDir=..\build\installer
OutputBaseFilename=BibChipMatcherSetup
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "..\build\dist\BibChipMatcher\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
