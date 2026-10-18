; playdate.iss - Inno Setup installer script for PlayDate
; Build with Inno Setup 6+: https://jrsoftware.org/isinfo.php

#define AppName      "PlayDate"
#ifndef AppVersion
#error "AppVersion must be supplied via /DAppVersion=X.Y.Z -- use build.py instead of running iscc directly"
#endif
#define AppPublisher "PlayDate"
#define AppURL       "https://github.com/RobbyRatpoison/PlayDate"
#define AppExeName   "PlayDate.exe"
; PyInstaller's output folder; change it together with the exe name
#define DistDir      "dist\PlayDate"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}

#ifdef MoveToNewFolder
; From the first Zest version: install into a fresh "Zest" folder next to the old "PlayDate" one (see
; GetDefaultDir below) and let the app move the user data on its first start. Inno would otherwise reuse the
; previous folder, so that is switched off.
UsePreviousAppDir=no
DefaultDirName={code:GetDefaultDir}
#else
DefaultDirName={%USERPROFILE}\{#AppName}
#endif
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes

OutputDir=installer
OutputBaseFilename=PlayDate-Setup
SetupIconFile=static\img\favicon.ico
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}

Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

WizardStyle=modern
WizardSizePercent=120
DisableWelcomePage=no
DisableDirPage=no
DisableReadyPage=no

PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

RestartIfNeededByRun=no

VersionInfoVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} Installer
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
#if AppExeName != "PlayDate.exe"
; A copy of the app under its old name, so a taskbar pin or shortcut to PlayDate.exe keeps working and lights up
; (it runs the same program from the same folder; the old folder name is a link to this one, see installmove.py).
Source: "{#DistDir}\{#AppExeName}"; DestDir: "{app}"; DestName: "PlayDate.exe"; Flags: ignoreversion
#endif

[UninstallDelete]
Type: filesandordirs; Name: "{app}\.rollback"

[Icons]
Name: "{group}\{#AppName}";         FileName: "{app}\{#AppExeName}"
Name: "{group}\Uninstall PlayDate"; FileName: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}";   FileName: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[Code]
#ifdef MoveToNewFolder
var
  OldAppDir: String;

const
  UninstallKey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}_is1';

function PreviousAppPath(): String;
begin
  Result := '';
  if not RegQueryStringValue(HKCU, UninstallKey, 'Inno Setup: App Path', Result) then
    RegQueryStringValue(HKLM, UninstallKey, 'Inno Setup: App Path', Result);
end;

{ A previous install in a folder called PlayDate moves to a Zest folder beside it; a previous install in any
  other folder is updated where it is (its data is already there), and a first install goes to the profile. }
function GetDefaultDir(Param: String): String;
var
  Prev: String;
begin
  Prev := RemoveBackslash(PreviousAppPath());
  OldAppDir := '';
  if Prev = '' then
    Result := ExpandConstant('{%USERPROFILE}') + '\Zest'
  else if CompareText(ExtractFileName(Prev), 'PlayDate') = 0 then
  begin
    OldAppDir := Prev;
    Result := ExtractFilePath(Prev) + 'Zest';
  end
  else
    Result := Prev;
end;

{ Only program files go: the user data stays until the new app has copied it and shown its first page, and
  .rollback stays for the old version's update watchdog. A file Windows still holds open is simply left. }
procedure RemoveOldProgramFiles(Dir: String);
var
  FindRec: TFindRec;
begin
  DelTree(Dir + '\_internal', True, True, True);
  DeleteFile(Dir + '\PlayDate.exe');
  if FindFirst(Dir + '\unins*.*', FindRec) then
  begin
    try
      repeat
        DeleteFile(Dir + '\' + FindRec.Name);
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;
end;

function PdGetFileAttributes(lpFileName: String): Cardinal;
  external 'GetFileAttributesW@kernel32.dll stdcall uninstallonly';

{ After an update from a PlayDate folder, the old folder name is a junction to this one (see installmove.py). When
  the app is uninstalled, drop that link too. RemoveDir on a junction removes only the link, never the folder it
  points at, and the attribute check makes sure it is a junction and not a real folder. }
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  OldLink: String;
  Attr: Cardinal;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    OldLink := ExtractFilePath(RemoveBackslash(ExpandConstant('{app}'))) + 'PlayDate';
    Attr := PdGetFileAttributes(OldLink);
    if (Attr <> $FFFFFFFF) and ((Attr and $400) <> 0) then
      RemoveDir(OldLink);
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and (OldAppDir <> '') and (CompareText(OldAppDir, RemoveBackslash(ExpandConstant('{app}'))) <> 0) then
    RemoveOldProgramFiles(OldAppDir);
end;
#endif

{ Deletes every file in Dir matching Pattern (the library is one games_<steam id>.db per account plus
  games_default.db, and there is a wins file per account, so a single file name is not enough). }
procedure DeleteMatching(Dir: String; Pattern: String);
var
  FindRec: TFindRec;
begin
  if FindFirst(Dir + '\' + Pattern, FindRec) then
  begin
    try
      repeat
        DeleteFile(Dir + '\' + FindRec.Name);
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;
end;

{ Everything PlayDate saved next to the program: settings, library, caches, the game artwork (static) and the
  installed plugins (plugins). The program files themselves are the uninstaller's own business. }
procedure DeleteUserData(Dir: String);
begin
  DeleteFile(Dir + '\config.json');
  DeleteFile(Dir + '\config.json.corrupt');
  DeleteFile(Dir + '\state.json');
  DeleteFile(Dir + '\theme.json');
  DeleteFile(Dir + '\playdate.log');
  DeleteFile(Dir + '\steam_hltb_map.json');
  DeleteFile(Dir + '\emulators.json');
  DeleteFile(Dir + '\santa_gifts.json');
  DeleteFile(Dir + '\.moved_from_old_install.json');
  DeleteFile(Dir + '\.move_in_progress');
  DeleteMatching(Dir, 'games*.db*');
  DeleteMatching(Dir, 'group_sources_*.json');
  DeleteMatching(Dir, 'steamgifts_wins_*.json');
  DelTree(Dir + '\static', True, True, True);
  DelTree(Dir + '\plugins', True, True, True);
end;

function InitializeUninstall(): Boolean;
var
  MsgResult: Integer;
  NL: String;
  Msg: String;
begin
  Result := True;
  NL := Chr(13) + Chr(10);
  Msg := 'Do you want to delete your PlayDate user data?' + NL +
         NL +
         'This includes:' + NL +
         '  - config.json and state.json  (accounts, API keys, filters, shelves)' + NL +
         '  - your game library  (the games databases)' + NL +
         '  - game artwork and installed plugins' + NL +
         '  - playdate.log and other saved data' + NL +
         NL +
         'Click YES to delete everything.' + NL +
         'Click NO to keep your data (you can re-use it after reinstalling).';
  MsgResult := MsgBox(Msg, mbConfirmation, MB_YESNO or MB_DEFBUTTON2);

  if MsgResult = IDYES then
    DeleteUserData(ExpandConstant('{app}'));
end;
