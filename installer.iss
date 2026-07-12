; Inno-Setup-Skript für Lyrix 2.x – modularer Installer
;
; - Sprachauswahl-Dialog (Systemsprache vorausgewählt)
; - Komponenten: Kern-Player (fest) + KI-Paket (abwählbar)
; - Optionale Aufgabe „GPU-Beschleunigung“: setzt ein Registry-Flag,
;   die App lädt das Paket beim ersten Start herunter (~800 MB, PyPI/NVIDIA)
; - Deinstalliert eine vorhandene Transkriptor-Installation (Vorgängername)
; - Registriert „Öffnen mit“ für gängige Audio-/Videoformate
;
; Voraussetzung: tools/gen_components.py hat build\components_files.iss erzeugt.

#define MyAppName "Lyrix"
#define MyAppVersion "2.1.0"
#define MyAppPublisher "Lyrix"
#define MyAppExeName "Lyrix.exe"
#define LegacyAppId "{7C2F1A94-5B7E-4E43-9C11-3AD0E6E2B7F1}"
; Entpackte Größe des GPU-Pakets (cuBLAS/cuDNN/CUDA-Runtime) auf der Platte –
; auf einer realen Installation gemessen; der Download selbst ist ~800 MB.
#define SizeGpuMB 1820

[Setup]
AppId={{A3E90D1B-64C7-4A21-9C7E-2F8B1D5E6A42}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; Zielordner-Seite ("Select Destination Location" mit Durchsuchen…) immer
; anzeigen – auch bei erkannter Vorinstallation (Punkt 2).
DisableDirPage=no
OutputDir=installer_out
OutputBaseFilename=Lyrix-Setup-{#MyAppVersion}
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ChangesAssociations=yes
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequiredOverridesAllowed=dialog
ShowLanguageDialog=yes

[Languages]
Name: "de"; MessagesFile: "compiler:Languages\German.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"
Name: "it"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "tr"; MessagesFile: "compiler:Languages\Turkish.isl"

[CustomMessages]
de.CompCore=Audio-Player (Kern)
de.CompWhisper=KI: Transkription (Whisper)
de.CompSpeakers=KI: Sprechertrennung (pyannote)
de.CompSounds=KI: Geräusch-/Musik-Erkennung (PANNs)
de.CompGpu=KI: NVIDIA-GPU-Beschleunigung – Download beim ersten Start (~800 MB), NUR für NVIDIA-Grafikkarten
de.TaskAssoc=Im Menü „Öffnen mit“ für Audio-/Videodateien anbieten
de.UninstallDataCheck=Heruntergeladene KI-Daten löschen (Whisper-Modelle, GPU-Paket, Songtext-Cache)
de.UninstallSettingsCheck=Einstellungen und „Zuletzt verwendet“-Liste löschen
de.UninstallOptionsText=Was soll zusätzlich zum Programm entfernt werden?
en.CompCore=Audio player (core)
en.CompWhisper=AI: transcription (Whisper)
en.CompSpeakers=AI: speaker separation (pyannote)
en.CompSounds=AI: sound/music recognition (PANNs)
en.CompGpu=AI: NVIDIA GPU acceleration – downloads on first start (~800 MB), NVIDIA graphics cards ONLY
en.TaskAssoc=Offer in the "Open with" menu for audio/video files
en.UninstallDataCheck=Delete downloaded AI data (Whisper models, GPU pack, lyrics cache)
en.UninstallSettingsCheck=Delete settings and the "recently used" list
en.UninstallOptionsText=What should be removed in addition to the program?
es.CompCore=Reproductor de audio (núcleo)
es.CompWhisper=IA: transcripción (Whisper)
es.CompSpeakers=IA: separación de hablantes (pyannote)
es.CompSounds=IA: detección de sonidos/música (PANNs)
es.CompGpu=IA: aceleración GPU NVIDIA – se descarga al primer inicio (~800 MB), SOLO tarjetas NVIDIA
es.TaskAssoc=Ofrecer en el menú «Abrir con» para archivos de audio/vídeo
es.UninstallDataCheck=Eliminar datos de IA descargados (modelos Whisper, paquete GPU, caché de letras)
es.UninstallSettingsCheck=Eliminar ajustes y la lista de «recientes»
es.UninstallOptionsText=¿Qué debe eliminarse además del programa?
fr.CompCore=Lecteur audio (noyau)
fr.CompWhisper=IA : transcription (Whisper)
fr.CompSpeakers=IA : séparation des locuteurs (pyannote)
fr.CompSounds=IA : détection des sons/musique (PANNs)
fr.CompGpu=IA : accélération GPU NVIDIA – téléchargée au premier démarrage (~800 Mo), UNIQUEMENT cartes NVIDIA
fr.TaskAssoc=Proposer dans le menu « Ouvrir avec » pour les fichiers audio/vidéo
fr.UninstallDataCheck=Supprimer les données IA téléchargées (modèles Whisper, pack GPU, cache des paroles)
fr.UninstallSettingsCheck=Supprimer les paramètres et la liste « récents »
fr.UninstallOptionsText=Que faut-il supprimer en plus du programme ?
it.CompCore=Lettore audio (base)
it.CompWhisper=IA: trascrizione (Whisper)
it.CompSpeakers=IA: separazione dei parlanti (pyannote)
it.CompSounds=IA: rilevamento suoni/musica (PANNs)
it.CompGpu=IA: accelerazione GPU NVIDIA – scaricata al primo avvio (~800 MB), SOLO schede NVIDIA
it.TaskAssoc=Proponi nel menu «Apri con» per i file audio/video
it.UninstallDataCheck=Elimina i dati IA scaricati (modelli Whisper, pacchetto GPU, cache dei testi)
it.UninstallSettingsCheck=Elimina impostazioni ed elenco «recenti»
it.UninstallOptionsText=Cosa rimuovere oltre al programma?
ru.CompCore=Аудиоплеер (ядро)
ru.CompWhisper=ИИ: расшифровка речи (Whisper)
ru.CompSpeakers=ИИ: разделение говорящих (pyannote)
ru.CompSounds=ИИ: распознавание звуков/музыки (PANNs)
ru.CompGpu=ИИ: ускорение NVIDIA GPU – загрузка при первом запуске (~800 МБ), ТОЛЬКО видеокарты NVIDIA
ru.TaskAssoc=Показывать в меню «Открыть с помощью» для аудио/видео
ru.UninstallDataCheck=Удалить загруженные ИИ-данные (модели Whisper, GPU-пакет, кэш текстов)
ru.UninstallSettingsCheck=Удалить настройки и список «недавние»
ru.UninstallOptionsText=Что удалить помимо программы?
tr.CompCore=Ses oynatıcı (çekirdek)
tr.CompWhisper=YZ: yazıya dökme (Whisper)
tr.CompSpeakers=YZ: konuşmacı ayrımı (pyannote)
tr.CompSounds=YZ: ses/müzik tanıma (PANNs)
tr.CompGpu=YZ: NVIDIA GPU hızlandırma – ilk başlatmada indirilir (~800 MB), YALNIZCA NVIDIA ekran kartları
tr.TaskAssoc=Ses/video dosyaları için "Birlikte aç" menüsünde göster
tr.UninstallDataCheck=İndirilen yapay zekâ verilerini sil (Whisper modelleri, GPU paketi, söz önbelleği)
tr.UninstallSettingsCheck=Ayarları ve "son kullanılanlar" listesini sil
tr.UninstallOptionsText=Programın yanı sıra neler kaldırılsın?

[Components]
Name: "core"; Description: "{cm:CompCore}"; Types: full compact custom; Flags: fixed
Name: "ai_whisper"; Description: "{cm:CompWhisper}"; Types: full
Name: "ai_speakers"; Description: "{cm:CompSpeakers}"; Types: full
Name: "ai_sounds"; Description: "{cm:CompSounds}"; Types: full
; GPU-Beschleunigung als gleichwertige Komponente (Punkt 1): installiert
; keine Dateien, sondern setzt das Registry-Flag – die App lädt das Paket
; beim ersten Start. ExtraDiskSpaceRequired = entpackte Größe auf der Platte.
; Bewusst in keinem Typ enthalten (standardmäßig abgewählt, nur NVIDIA).
Name: "gpu"; Description: "{cm:CompGpu}"; ExtraDiskSpaceRequired: {#SizeGpuMB * 1048576}

[Types]
Name: "full"; Description: "{#MyAppName} + KI / AI"
Name: "compact"; Description: "Player"
Name: "custom"; Description: "Custom"; Flags: iscustom

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "assoc"; Description: "{cm:TaskAssoc}"; GroupDescription: "{cm:AdditionalIcons}"

; [Files] kommt vollständig aus dem generierten Include (Kern/KI-Aufteilung)
#include "build\components_files.iss"
; Gruppengrößen (MB) für die selbst berechnete Speicherplatz-Anzeige
#include "build\components_sizes.iss"

[Icons]
; Startmenü-Ordner mit Programm UND sichtbarem Deinstallations-Eintrag (Punkt 5)
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; Oberflächensprache aus dem Installer als App-Vorgabe übernehmen
Root: HKCU; Subkey: "Software\{#MyAppName}\{#MyAppName}"; ValueType: string; ValueName: "ui_language"; ValueData: "{language}"; Flags: uninsdeletekeyifempty
; GPU-Paket-Wunsch (App lädt beim ersten Start herunter)
Root: HKCU; Subkey: "Software\{#MyAppName}\{#MyAppName}"; ValueType: string; ValueName: "gpu_pack_wanted"; ValueData: "true"; Components: gpu

; Anwendungs-Registrierung (macht die App im "Öffnen mit"-Dialog auffindbar)
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "{#MyAppName}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\shell\open\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\SupportedTypes"; ValueType: string; ValueName: ".mp3"; ValueData: ""; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\SupportedTypes"; ValueType: string; ValueName: ".wav"; ValueData: ""; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\SupportedTypes"; ValueType: string; ValueName: ".m4a"; ValueData: ""; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\SupportedTypes"; ValueType: string; ValueName: ".aac"; ValueData: ""; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\SupportedTypes"; ValueType: string; ValueName: ".flac"; ValueData: ""; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\SupportedTypes"; ValueType: string; ValueName: ".ogg"; ValueData: ""; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\SupportedTypes"; ValueType: string; ValueName: ".opus"; ValueData: ""; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\SupportedTypes"; ValueType: string; ValueName: ".wma"; ValueData: ""; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\SupportedTypes"; ValueType: string; ValueName: ".mp4"; ValueData: ""; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\SupportedTypes"; ValueType: string; ValueName: ".mkv"; ValueData: ""; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\SupportedTypes"; ValueType: string; ValueName: ".webm"; ValueData: ""; Flags: uninsdeletekey

; Eigene ProgId
Root: HKA; Subkey: "Software\Classes\{#MyAppName}.Audio"; ValueType: string; ValueData: "Audiodatei ({#MyAppName})"; Flags: uninsdeletekey; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\{#MyAppName}.Audio\DefaultIcon"; ValueType: string; ValueData: "{app}\{#MyAppExeName},0"; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\{#MyAppName}.Audio\shell\open\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: assoc

; "Öffnen mit"-Einträge je Dateityp (ohne die Standard-App zu verdrängen)
Root: HKA; Subkey: "Software\Classes\.mp3\OpenWithProgids"; ValueType: string; ValueName: "{#MyAppName}.Audio"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.wav\OpenWithProgids"; ValueType: string; ValueName: "{#MyAppName}.Audio"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.m4a\OpenWithProgids"; ValueType: string; ValueName: "{#MyAppName}.Audio"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.aac\OpenWithProgids"; ValueType: string; ValueName: "{#MyAppName}.Audio"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.flac\OpenWithProgids"; ValueType: string; ValueName: "{#MyAppName}.Audio"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.ogg\OpenWithProgids"; ValueType: string; ValueName: "{#MyAppName}.Audio"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.opus\OpenWithProgids"; ValueType: string; ValueName: "{#MyAppName}.Audio"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.wma\OpenWithProgids"; ValueType: string; ValueName: "{#MyAppName}.Audio"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.mp4\OpenWithProgids"; ValueType: string; ValueName: "{#MyAppName}.Audio"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.mkv\OpenWithProgids"; ValueType: string; ValueName: "{#MyAppName}.Audio"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.webm\OpenWithProgids"; ValueType: string; ValueName: "{#MyAppName}.Audio"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; In der App nachgeladene KI-Komponenten stehen nicht im Uninstall-Log von
; Inno – das Programmverzeichnis deshalb ausdrücklich vollständig entfernen
; (Punkt 5: restlose Deinstallation der Kernanwendung inkl. Nachladungen).
Type: filesandordirs; Name: "{app}\_internal"
Type: dirifempty; Name: "{app}"

[Code]
// ---------------------------------------------------------------------------
// Speicherplatz-Anzeige selbst berechnen (Punkt 1): Inno zählt Dateien mit
// Oder-Komponenten-Ausdrücken ("ai_speakers or ai_sounds") in jeder genannten
// Komponente mit, wodurch die eingebaute Summe bei Mehrfachauswahl um mehrere
// hundert MB zu hoch ausfällt. Hier wird jede geteilte Gruppe genau einmal
// gezählt und das Label bei jeder Checkbox-Änderung neu gesetzt.
var
  PrevComponentsClickCheck: TNotifyEvent;
  PrevTypesComboChange: TNotifyEvent;

function GpuListIndex(): Integer;
var
  I: Integer;
begin
  { Index des GPU-Eintrags in der Komponentenliste (über die Beschriftung
    gesucht, damit keine Positions-Annahme nötig ist). }
  Result := -1;
  for I := 0 to WizardForm.ComponentsList.Items.Count - 1 do
    if WizardForm.ComponentsList.ItemCaption[I] = CustomMessage('CompGpu') then
    begin
      Result := I;
      Exit;
    end;
end;

procedure SyncGpuComponent();
var
  Idx: Integer;
begin
  { GPU-Beschleunigung nützt nur der Whisper-Transkription: ohne Whisper
    wird der Eintrag abgewählt und gesperrt. }
  Idx := GpuListIndex();
  if Idx < 0 then
    Exit;
  if not WizardIsComponentSelected('ai_whisper') then
    WizardForm.ComponentsList.Checked[Idx] := False;
  WizardForm.ComponentsList.ItemEnabled[Idx] :=
    WizardIsComponentSelected('ai_whisper');
end;

procedure UpdateComponentsDiskSpace();
var
  TotalMB: Integer;
  Caption: String;
  SelWhisper, SelSpeakers, SelSounds: Boolean;
begin
  SelWhisper := WizardIsComponentSelected('ai_whisper');
  SelSpeakers := WizardIsComponentSelected('ai_speakers');
  SelSounds := WizardIsComponentSelected('ai_sounds');
  TotalMB := {#SizeCoreMB};
  if SelWhisper then
    TotalMB := TotalMB + {#SizeWhisperMB};
  if SelSpeakers then
    TotalMB := TotalMB + {#SizeSpeakersMB};
  if SelSounds then
    TotalMB := TotalMB + {#SizeSoundsMB};
  if SelSpeakers or SelSounds then
    TotalMB := TotalMB + {#SizeTorchSharedMB};
  if SelWhisper or SelSpeakers then
    TotalMB := TotalMB + {#SizeHubSharedMB};
  if SelWhisper or SelSpeakers or SelSounds then
    TotalMB := TotalMB + {#SizeAnyAiSharedMB};
  if WizardIsComponentSelected('gpu') then
    TotalMB := TotalMB + {#SizeGpuMB};
  { Die Inno-Meldung enthält den literalen Platzhalter "[mb]" (kein %1!) –
    FmtMessage ließe ihn unverändert stehen, deshalb StringChangeEx. }
  Caption := SetupMessage(msgComponentsDiskSpaceMBLabel);
  StringChangeEx(Caption, '[mb]', IntToStr(TotalMB), True);
  { Zeilen duerfen in .iss nie mit "[" beginnen (wird als Sektion gelesen) }
  WizardForm.ComponentsDiskSpaceLabel.Caption := Caption;
end;

procedure ComponentsListClickCheck(Sender: TObject);
begin
  if PrevComponentsClickCheck <> nil then
    PrevComponentsClickCheck(Sender);
  SyncGpuComponent();
  UpdateComponentsDiskSpace();
end;

procedure TypesComboChange(Sender: TObject);
begin
  if PrevTypesComboChange <> nil then
    PrevTypesComboChange(Sender);
  SyncGpuComponent();
  UpdateComponentsDiskSpace();
end;

procedure InitializeWizard();
begin
  PrevComponentsClickCheck := WizardForm.ComponentsList.OnClickCheck;
  WizardForm.ComponentsList.OnClickCheck := @ComponentsListClickCheck;
  PrevTypesComboChange := WizardForm.TypesCombo.OnChange;
  WizardForm.TypesCombo.OnChange := @TypesComboChange;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpSelectComponents then
  begin
    SyncGpuComponent();
    UpdateComponentsDiskSpace();
  end;
end;

// Vorgänger "Transkriptor" (alter Programmname) still deinstallieren
procedure RemoveLegacyTranskriptor();
var
  UninstallKey, UninstallStr: string;
  ResultCode: Integer;
begin
  UninstallKey := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\' +
                  '{#LegacyAppId}' + '_is1';
  if not RegQueryStringValue(HKCU, UninstallKey, 'QuietUninstallString',
                             UninstallStr) then
    if not RegQueryStringValue(HKLM, UninstallKey, 'QuietUninstallString',
                               UninstallStr) then
      Exit;
  Exec('>', UninstallStr, '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
    RemoveLegacyTranskriptor();
end;

// ---------------------------------------------------------------------------
// Deinstallation (Punkte 5+8): Der Nutzer wählt per Checkboxen, was zusätzlich
// zum Programm entfernt wird – heruntergeladene KI-Daten (Whisper-Modelle,
// GPU-Paket, Caches unter %LOCALAPPDATA%\Lyrix) und/oder Einstellungen
// (Registry inkl. „Zuletzt verwendet“). Das Programm selbst entfernt der
// Standard-Deinstaller; nachgeladene Pakete in {app}\_internal räumt die
// [UninstallDelete]-Sektion ab.
var
  UninstDeleteData: Boolean;
  UninstDeleteSettings: Boolean;

function AskUninstallOptionsForm(): Boolean;
var
  Form: TSetupForm;
  InfoText: TNewStaticText;
  DataCheck, SettingsCheck: TNewCheckBox;
  OkButton, CancelButton: TNewButton;
begin
  Form := TSetupForm.Create(nil);
  try
    Form.ClientWidth := ScaleX(430);
    Form.ClientHeight := ScaleY(150);
    Form.Caption := '{#MyAppName}';
    Form.Position := poScreenCenter;

    InfoText := TNewStaticText.Create(Form);
    InfoText.Parent := Form;
    InfoText.Left := ScaleX(16);
    InfoText.Top := ScaleY(14);
    InfoText.Width := Form.ClientWidth - ScaleX(32);
    InfoText.AutoSize := False;
    InfoText.WordWrap := True;
    InfoText.Height := ScaleY(28);
    InfoText.Caption := CustomMessage('UninstallOptionsText');

    DataCheck := TNewCheckBox.Create(Form);
    DataCheck.Parent := Form;
    DataCheck.Left := ScaleX(16);
    DataCheck.Top := ScaleY(48);
    DataCheck.Width := Form.ClientWidth - ScaleX(32);
    DataCheck.Caption := CustomMessage('UninstallDataCheck');
    DataCheck.Checked := True;

    SettingsCheck := TNewCheckBox.Create(Form);
    SettingsCheck.Parent := Form;
    SettingsCheck.Left := ScaleX(16);
    SettingsCheck.Top := ScaleY(74);
    SettingsCheck.Width := Form.ClientWidth - ScaleX(32);
    SettingsCheck.Caption := CustomMessage('UninstallSettingsCheck');
    SettingsCheck.Checked := False;

    OkButton := TNewButton.Create(Form);
    OkButton.Parent := Form;
    OkButton.Width := ScaleX(90);
    OkButton.Height := ScaleY(26);
    OkButton.Left := Form.ClientWidth - ScaleX(196);
    OkButton.Top := Form.ClientHeight - ScaleY(38);
    OkButton.Caption := SetupMessage(msgButtonOK);
    OkButton.ModalResult := mrOk;
    OkButton.Default := True;

    CancelButton := TNewButton.Create(Form);
    CancelButton.Parent := Form;
    CancelButton.Width := ScaleX(90);
    CancelButton.Height := ScaleY(26);
    CancelButton.Left := Form.ClientWidth - ScaleX(100);
    CancelButton.Top := Form.ClientHeight - ScaleY(38);
    CancelButton.Caption := SetupMessage(msgButtonCancel);
    CancelButton.ModalResult := mrCancel;
    CancelButton.Cancel := True;

    Result := Form.ShowModal() = mrOk;
    if Result then
    begin
      UninstDeleteData := DataCheck.Checked;
      UninstDeleteSettings := SettingsCheck.Checked;
    end;
  finally
    Form.Free();
  end;
end;

function InitializeUninstall(): Boolean;
begin
  UninstDeleteData := False;
  UninstDeleteSettings := False;
  if UninstallSilent then
  begin
    { Stille Deinstallation: große, wiederbeschaffbare Downloads entfernen,
      persönliche Einstellungen aus Vorsicht behalten. }
    UninstDeleteData := True;
    Result := True;
    Exit;
  end;
  try
    Result := AskUninstallOptionsForm();
  except
    { Fallback, falls das Formular in der Uninstall-Umgebung nicht
      erzeugt werden kann: zwei einfache Ja/Nein-Fragen. }
    UninstDeleteData := MsgBox(CustomMessage('UninstallDataCheck') + '?',
                               mbConfirmation, MB_YESNO) = IDYES;
    UninstDeleteSettings := MsgBox(CustomMessage('UninstallSettingsCheck') + '?',
                                   mbConfirmation, MB_YESNO) = IDYES;
    Result := True;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    if UninstDeleteData then
      DelTree(ExpandConstant('{localappdata}\{#MyAppName}'), True, True, True);
    if UninstDeleteSettings then
    begin
      RegDeleteKeyIncludingSubkeys(HKCU, 'Software\{#MyAppName}');
      RegDeleteKeyIncludingSubkeys(HKCU, 'Software\Transkriptor');
    end;
  end;
end;
