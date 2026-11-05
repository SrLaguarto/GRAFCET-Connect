; Instalador de GRAFCET Connect (Inno Setup 6). Lo compila tools/construir_ejecutable.py con:
;   ISCC.exe /DVersion=1.0.0 /DOrigen=<dist\GRAFCET Connect> /DSalida=<dist> /DRaiz=<raíz del repositorio> instalador.iss
; Instala para el usuario actual (sin permisos de administrador), crea el acceso en el menú Inicio, asocia los
; archivos .grafnet al programa y deja un desinstalador. La versión portable (zip) sigue siendo la misma carpeta.

#ifndef Version
  #define Version "0.0.0"
#endif
#ifndef Origen
  #error Falta /DOrigen con la carpeta del programa construida
#endif
#ifndef Salida
  #define Salida "."
#endif
#ifndef Raiz
  #define Raiz ".."
#endif

#define Nombre "GRAFCET Connect"
#define Exe "GRAFCET Connect.exe"
#define TipoArchivo "GRAFCETConnect.Proyecto"

[Setup]
AppId={{6F0C2D8E-3B7A-4C55-9E1D-6A2B9C4E7F10}
AppName={#Nombre}
AppVersion={#Version}
AppVerName={#Nombre} {#Version}
AppPublisher=SrLaguarto
AppPublisherURL=https://github.com/SrLaguarto/GRAFCET-Connect
AppSupportURL=https://github.com/SrLaguarto/GRAFCET-Connect/issues
AppUpdatesURL=https://github.com/SrLaguarto/GRAFCET-Connect/releases
DefaultDirName={autopf}\{#Nombre}
DefaultGroupName={#Nombre}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
LicenseFile={#Raiz}\LICENSE
SetupIconFile={#Raiz}\escritorio\recursos\grafcet_connect.ico
UninstallDisplayIcon={app}\{#Exe}
UninstallDisplayName={#Nombre} {#Version}
OutputDir={#Salida}
OutputBaseFilename=GRAFCET-Connect-{#Version}-setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ChangesAssociations=yes
VersionInfoVersion={#Version}.0
VersionInfoProductName={#Nombre}
VersionInfoDescription={#Nombre}: instalador

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "escritorio"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"; Flags: unchecked
Name: "asociar"; Description: "Abrir los archivos .grafnet con {#Nombre}"; GroupDescription: "Archivos:"

[Files]
Source: "{#Origen}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#Nombre}"; Filename: "{app}\{#Exe}"
Name: "{group}\Léame de {#Nombre}"; Filename: "{app}\LEEME.txt"
Name: "{group}\Desinstalar {#Nombre}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#Nombre}"; Filename: "{app}\{#Exe}"; Tasks: escritorio

[Registry]
Root: HKA; Subkey: "Software\Classes\.grafnet"; ValueType: string; ValueName: ""; ValueData: "{#TipoArchivo}"; Flags: uninsdeletevalue; Tasks: asociar
Root: HKA; Subkey: "Software\Classes\{#TipoArchivo}"; ValueType: string; ValueName: ""; ValueData: "Proyecto de {#Nombre}"; Flags: uninsdeletekey; Tasks: asociar
Root: HKA; Subkey: "Software\Classes\{#TipoArchivo}\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#Exe},0"; Tasks: asociar
Root: HKA; Subkey: "Software\Classes\{#TipoArchivo}\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#Exe}"" ""%1"""; Tasks: asociar

[Run]
Filename: "{app}\{#Exe}"; Description: "Abrir {#Nombre}"; Flags: nowait postinstall skipifsilent
