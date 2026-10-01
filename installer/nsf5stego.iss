; nsf5stego Windows 安装器 (打包计划 M3, 见 docs/PACKAGING.md)
; 构建: python scripts/build_installer.py  (内部调 ISCC 编译本文件)
; 前置: python scripts/build_exe.py 已产出 build\exe\nsf5stego\ 双 exe

#define MyAppName "nsF5 隐写工具"
#define MyAppExeName "nsf5stego-gui.exe"
; GetFileVersion 返回四段 "1.8.0.0" (二进制版本资源), 剥掉最后一段回到 semver
#define VerQuad GetFileVersion("..\build\exe\nsf5stego\nsf5stego.exe")
#define MyAppVersion Copy(VerQuad, 1, RPos(".", VerQuad) - 1)
#if MyAppVersion == ""
#pragma error "冻结 exe 缺版本资源 —— 先跑 python scripts/build_exe.py"
#endif

[Setup]
; 固定 GUID: 同一应用跨版本必须不变, 否则升级/卸载互相不认识
AppId={{8E5F1C42-7D93-4A2B-B0C6-15F49E3A7D21}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
DefaultGroupName={#MyAppName}
; 每用户安装 (免管理员): 默认 %LOCALAPPDATA%\Programs\nsf5stego, 可改
DefaultDirName={userpf}\nsf5stego
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=nsf5stego-setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName={#MyAppName} {#MyAppVersion}
SetupIconFile=../img/nsf5stego.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
ChangesEnvironment=yes

[Languages]
Name: "chs"; MessagesFile: "ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; \
    GroupDescription: "{cm:AdditionalIcons}"
Name: "addpath"; Description: "将 nsf5stego 命令行加入用户 PATH (重开终端生效)"; \
    GroupDescription: "可选组件:"; Flags: unchecked

[Files]
Source: "..\build\exe\nsf5stego\*"; DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\nsf5stego 命令行"; Filename: "{app}\nsf5stego.exe"; \
    Parameters: "--help"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; \
    Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "立即运行 {#MyAppName}"; \
    Flags: nowait postinstall skipifsilent

[Code]
const
  EnvKey = 'Environment';

procedure PathBroadcast();
var
  Msg: DWORD;
begin
  Msg := RegisterWindowMessage('WM_SETTINGCHANGE');
  PostMessage(HWND_BROADCAST, Msg, 0, 0);
end;

function GetCurrentUserPath(): string;
var
  V: string;
begin
  if RegQueryStringValue(HKEY_CURRENT_USER, EnvKey, 'Path', V) then
    Result := V
  else
    Result := '';
end;

procedure AddToUserPath(Dir: string);
var
  V, NewV: string;
begin
  V := GetCurrentUserPath();
  if Pos(';' + LowerCase(Dir) + ';', ';' + LowerCase(V) + ';') > 0 then
    exit;                                    // 已在 PATH 里
  if V = '' then
    NewV := Dir
  else
    NewV := V + ';' + Dir;
  RegWriteExpandStringValue(HKEY_CURRENT_USER, EnvKey, 'Path', NewV);
  PathBroadcast;
end;

procedure RemoveFromUserPath(Dir: string);
var
  V, Rest, Item, NewV: string;
  I: Integer;
begin
  V := GetCurrentUserPath();
  if V = '' then
    exit;
  NewV := '';
  Rest := V + ';';
  Dir := LowerCase(Dir);
  repeat
    I := Pos(';', Rest);
    Item := Copy(Rest, 1, I - 1);
    Rest := Copy(Rest, I + 1, MaxInt);
    if (Item <> '') and (LowerCase(Item) <> Dir) then
      NewV := NewV + Item + ';';
  until Length(Rest) = 0;
  if Length(NewV) > 0 then
    SetLength(NewV, Length(NewV) - 1);       // 去掉末尾多余分号
  if NewV = V then
    exit;                                    // 本来就没有我们那一项
  if NewV = '' then
    RegDeleteValue(HKEY_CURRENT_USER, EnvKey, 'Path')
  else
    RegWriteExpandStringValue(HKEY_CURRENT_USER, EnvKey, 'Path', NewV);
  PathBroadcast;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    if IsTaskSelected('addpath') then
      AddToUserPath(ExpandConstant('{app}'));
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    RemoveFromUserPath(ExpandConstant('{app}'));
end;
