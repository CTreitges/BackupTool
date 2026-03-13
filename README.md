# BackupTool

Automatisches Backup-Tool fuer Windows, das Ordner im Hintergrund synchronisiert und geloeschte Dateien sicher im Papierkorb aufbewahrt -- ideal fuer OneDrive-zu-NAS-Backups.

---

## Schnellstart

1. **BackupToolTray.exe** starten (Doppelklick)
2. Das gruene Icon erscheint unten rechts im System-Tray
3. **Rechtsklick** auf das Icon > **Settings...**
4. Im Tab **Folder Pairs** auf **Add...** klicken
5. Quellordner (z.B. OneDrive) und Zielordner (z.B. NAS-Laufwerk) auswaehlen
6. Fertig -- die Synchronisation startet sofort

---

## Was ist im Ordner?

| Datei | Beschreibung |
|---|---|
| **BackupToolTray.exe** | Die Haupt-App. Diese Datei starten! Zeigt ein Icon im System-Tray und synchronisiert im Hintergrund. |
| `_internal/` | Benoetigt fuer die EXE -- nicht loeschen, nicht veraendern. |

> **Wichtig:** `_internal/` muss im selben Ordner wie die EXE liegen, sonst startet das Programm nicht.

---

## Bedienung

### System-Tray-Menue (Rechtsklick auf das Icon)

| Menue-Eintrag | Funktion |
|---|---|
| **Start Sync** | Synchronisation starten |
| **Stop Sync** | Synchronisation anhalten |
| **Restart Sync** | Synchronisation neu starten (z.B. nach Aenderungen) |
| **Settings...** | Einstellungen oeffnen (Ordnerpaare, Optionen, Status) |
| **Open Log** | Log-Datei oeffnen (hilfreich bei Problemen) |
| **Quit** | Programm beenden |

### Icon-Farben

| Farbe | Bedeutung |
|---|---|
| Gruen | Synchronisation laeuft |
| Grau | Synchronisation gestoppt |
| Rot | Fehler aufgetreten -- Details in den Settings unter "Status" |

---

## Einstellungen

Ueber **Rechtsklick > Settings...** oeffnet sich ein Fenster mit drei Tabs:

### Tab: Folder Pairs

Hier verwaltest du deine Ordnerpaare:

- **Add...** -- Neues Ordnerpaar hinzufuegen (Quell- und Zielordner auswaehlen)
- **Remove** -- Ausgewaehltes Paar loeschen
- **Enable / Disable** -- Einzelne Paare ein-/ausschalten, ohne sie zu loeschen

Die Liste zeigt live den Status jedes Paares an: Sync-Fortschritt in Prozent, letzter Sync-Zeitpunkt und eventuelle Fehler.

### Tab: Settings

| Einstellung | Standard | Beschreibung |
|---|---|---|
| **Retention (Tage)** | 30 | So lange bleiben geloeschte Dateien im Papierkorb, bevor sie endgueltig entfernt werden (1--3650 Tage) |
| **Scan-Intervall (Min.)** | 30 | Alle X Minuten wird ein vollstaendiger Abgleich durchgefuehrt (1--1440 Min.) |
| **Log-Level** | INFO | Detailgrad der Protokollierung (DEBUG = sehr ausfuehrlich, ERROR = nur Fehler) |
| **Autostart (Desktop)** | -- | BackupTool startet automatisch mit Windows (Tray-Icon) |
| **Autostart Headless** | -- | Fuer Server: Startet ohne Oberflaeche als geplante Aufgabe |

### Tab: Status

Zeigt den aktuellen Zustand der Synchronisation:
- Laeuft der Sync?
- Wann war der letzte vollstaendige Scan?
- Wann wurde der Papierkorb zuletzt aufgeraeumt?
- Aufgetretene Fehler

---

## Wie funktioniert die Synchronisation?

BackupTool synchronisiert Dateien **in eine Richtung**: von der Quelle zum Ziel.

1. **Echtzeit-Ueberwachung** -- Aenderungen im Quellordner werden sofort erkannt und kopiert
2. **Regelmaessiger Vollabgleich** -- Zusaetzlich wird alle 30 Minuten (einstellbar) ein kompletter Vergleich durchgefuehrt
3. **Papierkorb statt Loeschen** -- Wird eine Datei in der Quelle geloescht, wird sie im Ziel nicht sofort entfernt, sondern in einen `__RecycleBin__`-Ordner verschoben
4. **Automatische Bereinigung** -- Nach Ablauf der Aufbewahrungsfrist (Standard: 30 Tage) werden Papierkorb-Dateien endgueltig geloescht

### Was wird automatisch ignoriert?

Temporaere und Systemdateien werden uebersprungen:
`~$*`, `*.tmp`, `*.part`, `desktop.ini`, `thumbs.db`

---

## Papierkorb (Recycle Bin)

Geloeschte und ueberschriebene Dateien landen nicht sofort im Nichts, sondern im Ordner `__RecycleBin__` innerhalb des jeweiligen Zielordners.

- Dateien werden mit Zeitstempel gespeichert: `2026-03-13_143022__dokument.docx`
- Die Ordnerstruktur wird beibehalten
- Nach Ablauf der eingestellten Aufbewahrungsfrist werden sie automatisch entfernt
- Leere Unterordner im Papierkorb werden ebenfalls aufgeraeumt

So kannst du versehentlich geloeschte Dateien einfach wiederherstellen, indem du sie aus dem `__RecycleBin__`-Ordner zurueckkopierst.

---

## Wo speichert BackupTool seine Daten?

| Datei / Ordner | Pfad |
|---|---|
| Konfiguration | `C:\ProgramData\BackupTool\config.json` |
| Log-Datei | `C:\ProgramData\BackupTool\backuptool.log` |
| Status | `C:\ProgramData\BackupTool\status.json` |
| Papierkorb | `__RecycleBin__` im jeweiligen Zielordner |

---

## Haeufige Fragen

**Muss ich die App als Administrator starten?**
Nein. Fuer den normalen Betrieb ueber das Tray-Icon sind keine Admin-Rechte noetig.

**Kann ich mehrere Ordnerpaare gleichzeitig synchronisieren?**
Ja, beliebig viele. Jedes Paar wird unabhaengig synchronisiert.

**Was passiert bei einem Netzwerkausfall?**
Die Synchronisation versucht es beim naechsten Intervall erneut. Fehler werden im Status-Tab angezeigt.

**Kann ich den Zielordner auch auf einer externen Festplatte haben?**
Ja, jeder Ordner, auf den Windows zugreifen kann (lokale Laufwerke, Netzlaufwerke, USB), funktioniert.

**Wie stelle ich eine geloeschte Datei wieder her?**
Navigiere zum `__RecycleBin__`-Ordner im Zielverzeichnis und kopiere die Datei zurueck. Der Dateiname enthaelt das Loeschdatum.

---

## Deinstallation

1. Rechtsklick auf das Tray-Icon > **Quit**
2. Den BackupTool-Ordner einfach loeschen
3. Optional: `C:\ProgramData\BackupTool\` loeschen, um Konfiguration und Logs zu entfernen
