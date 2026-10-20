; Inno Setup script for the Windows installer. Build after packaging/windows/build.sh:
;   iscc /DVersion=1.2.0 packaging\windows\narenj.iss
; Writes dist\narenj-<version>-setup.exe.

#ifndef Version
  #define Version "0.0.0"
#endif

[Setup]
AppId={{6F3A9C1E-2B7D-4E58-9A41-7C2E8D5B1F63}
AppName=Narenj
AppVersion={#Version}
AppVerName=Narenj {#Version}
AppPublisher=HAstaShakiba
AppPublisherURL=https://github.com/HAstaShakiba/narenj
DefaultDirName={autopf}\Narenj
DefaultGroupName=Narenj
DisableProgramGroupPage=yes
; installs for the current user without admin rights; the dialog offers all users too
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\dist
OutputBaseFilename=narenj-{#Version}-setup
SetupIconFile=narenj.ico
UninstallDisplayIcon={app}\narenj.ico
LicenseFile=..\..\LICENSE
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern

[Files]
Source: "..\..\dist\windows\Narenj\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
; Ctrl+Alt+N opens the wheel; pressed again it closes it (Windows hotkeys work on Start menu shortcuts)
Name: "{group}\Narenj"; Filename: "{app}\bin\pythonw.exe"; \
    Parameters: """{app}\share\narenj\narenj.py"" --toggle"; WorkingDir: "{userdocs}"; \
    IconFilename: "{app}\narenj.ico"; HotKey: ctrl+alt+n; Comment: "Drag-and-drop ffmpeg wheel"
Name: "{group}\Uninstall Narenj"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\bin\pythonw.exe"; Parameters: """{app}\share\narenj\narenj.py"""; \
    Description: "Open Narenj"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\Narenj"
