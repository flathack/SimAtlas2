# S2-Atlas-Savegame-Editor

Python-basierte Desktop-Grundlage fuer einen Sims-2-Savegame-Editor.

## Status

Dieses Setup liefert:
- modulare Projektstruktur (Core, UI, Tests)
- lauffaehige PySide6-Oberflaeche
- JSON-basierte Savegame-Daten als MVP-Format
- Backup, Validierung, Undo/Redo auf Session-Ebene

Hinweis: Der proprietaere Sims-2-Binaerparser ist bewusst noch als naechster Schritt geplant.

## Schnellstart

1. Virtuelle Umgebung erstellen:
   - Windows PowerShell: python -m venv .venv
2. Umgebung aktivieren:
   - Windows PowerShell: .\\.venv\\Scripts\\Activate.ps1
3. Abhaengigkeiten installieren:
   - pip install -r requirements-dev.txt
4. Projekt lokal installierbar machen:
   - pip install -e .
5. App starten:
   - python -m s2saveforge
   - alternativ: s2atlas

## Tests

- pytest

## Projektstruktur

- src/s2saveforge: Anwendungscode
- tests: Tests fuer Core-Logik
- sample_data: Beispiel-Savegame fuer lokale Tests

## MVP-Dateiformat

Aktuell wird ein JSON-MVP-Format genutzt, damit UX, Validierung und Workflow parallel zum spaeteren Binaerparser entwickelt werden koennen.

Beispieldatei:
- sample_data/demo_save.s2json
