# BackupTool

Automatisches Dateisynchronisations-Tool fuer Windows mit Recycle-Bin-Funktion.

## Was wird installiert?

| Datei | Zweck |
|---|---|
| **BackupToolTray.exe** | System-Tray-App — das ist die Datei, die du starten sollst. Hier kannst du Ordnerpaare verwalten, den Service steuern und den Status sehen. |
| **BackupToolService.exe** | Hintergrund-Service — wird automatisch gestartet, **nicht manuell ausfuehren**. |

## Installation

### Variante A: Setup-Installer (empfohlen)

1. `build.bat` ausfuehren (erstellt die EXE-Dateien)
2. `dist/BackupToolSetup.exe` ausfuehren
3. Der Installer installiert den Windows-Service und richtet den Autostart der Tray-App ein
4. Fertig — das Tray-Icon erscheint im System-Tray

### Variante B: Manuell (Entwickler)

1. Virtual Environment erstellen und aktivieren:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Service installieren (als Administrator):
   ```
   python main.py install
   ```

3. Service starten:
   ```
   python main.py start
   ```

4. Tray-App starten:
   ```
   python main.py tray
   ```

## Benutzung

1. **Rechtsklick auf das Tray-Icon** im System-Tray
2. **Settings** oeffnen
3. Im Tab "Folder Pairs" auf **Add...** klicken
4. Quell- und Zielordner auswaehlen
5. Die erste Synchronisation startet sofort automatisch
6. Der Status (Fortschritt, letzter Sync) wird direkt in der Liste angezeigt

## Ordnerpaare

- Jedes Paar synchronisiert Dateien von **Source** nach **Destination**
- Geloeschte Dateien werden in einen `__RecycleBin__`-Ordner im Zielverzeichnis verschoben
- Nach Ablauf der Aufbewahrungsfrist (Standard: 30 Tage) werden sie endgueltig geloescht

## Konfiguration

Konfigurationsdatei: `C:\ProgramData\BackupTool\config.json`

| Einstellung | Standard | Beschreibung |
|---|---|---|
| `retention_days` | 30 | Tage bis Recycle-Bin-Dateien geloescht werden |
| `scan_interval_minutes` | 30 | Intervall fuer vollstaendigen Abgleich |
| `log_level` | INFO | Log-Level (DEBUG, INFO, WARNING, ERROR) |

## Log-Dateien

- Hauptlog: `C:\ProgramData\BackupTool\backuptool.log`
- Service-Bootlog: `C:\ProgramData\BackupTool\service_boot.log`

## Deinstallation

### Via Installer
Windows Einstellungen > Apps > BackupTool > Deinstallieren

### Manuell
```
python main.py stop
python main.py uninstall
```

## Befehle (Entwicklung)

```
python main.py install    # Service installieren
python main.py uninstall  # Service entfernen
python main.py start      # Service starten
python main.py stop       # Service stoppen
python main.py debug      # Sync-Engine im Vordergrund (ohne Service)
python main.py tray       # Tray-App starten
```

## Build

```
build.bat
```

Erzeugt `dist/BackupTool/` mit den EXE-Dateien und optional `dist/BackupToolSetup.exe` (benoetigt Inno Setup).
