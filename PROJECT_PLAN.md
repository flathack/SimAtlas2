# Projektplan: Sims 2 Savegame Editor

## 1. Projektueberblick

### 1.1 Ziel
Entwicklung einer Desktop-Software, die Sims 2 Savegames sicher lesen, analysieren, bearbeiten und in kontrolliertem Rahmen manipulieren kann, inklusive Rueckgaengig-Funktionen, Backup-Management und einer klaren, einsteigerfreundlichen Oberflaeche.

### 1.2 Vision aus Spieler-Sicht
Ein Sims-2-Spieler moechte vor allem:
- kaputte Spielstaende retten statt sie wegzuwerfen
- lang gespielte Nachbarschaften sichern und zwischen PCs uebertragen
- Storytelling unterstuetzen (Beziehungen, Karrieren, Haushaltswerte)
- grindige oder frustrierende Teile abkuerzen (z. B. Geld, Beduerfnisse, Skill-Werte)
- fehlerhafte Daten korrigieren (falsche Alterung, inkonsistente Beziehungen, broken references)
- schnell verstehen, was geaendert wird und welche Risiken bestehen

### 1.3 Projektname (Arbeitstitel)
S2 Save Forge

## 2. Produktziele und Erfolgskriterien

### 2.1 Primaere Ziele
- Savegame-Dateien robust einlesen und strukturierte Daten anzeigen.
- Sichere Bearbeitung mit Validierung und Undo/Redo anbieten.
- Export mit Integritaetspruefung und automatischem Backup realisieren.
- Modding- und Casual-User mit unterschiedlichen UI-Modi bedienen.

### 2.2 Messbare Erfolgskriterien (KPIs)
- Mindestens 95 % aller getesteten Savegames werden ohne Absturz geoeffnet.
- 0 Datenverlust-Faelle durch verpflichtende Backup-Strategie.
- 90 % der Testnutzer koennen Kernaufgaben ohne Doku in unter 3 Minuten erledigen.
- Bearbeitung + Speichern eines Haushalts in unter 10 Sekunden auf Standard-Hardware.

## 3. Zielgruppen

### 3.1 Casual-Spieler
- Will schnelle Aenderungen (Geld, Skills, Beduerfnisse)
- Erwartet gefuehrte UI mit klaren Warnhinweisen

### 3.2 Story-/Legacy-Spieler
- Will Beziehungen, Erinnerungen, Lebensphasen kontrollieren
- Legt Wert auf Historie, Snapshots und Vergleichsansicht

### 3.3 Power-User/Modder
- Will Batch-Operationen, erweiterte Datensicht, Regel-Checks
- Braucht transparente Datenmodelle und optional Script-Hooks

## 4. Kernfunktionen (MVP bis Advanced)

### 4.1 MVP-Funktionen
- Savegame laden (Datei- oder Ordnerauswahl)
- Automatisches Backup vor jeder Aenderung
- Entity-Browser:
  - Sims
  - Haushalte
  - Beziehungen
  - Karriere/Skills
- Schnellbearbeitung:
  - Simoleons
  - Beduerfnisse
  - Skill-Level
  - Karrierestufe
  - Alter/Lebensphase (mit Plausibilitaetspruefung)
- Validierung vor dem Speichern
- Undo/Redo
- Fehlerprotokoll mit konkreten Handlungsempfehlungen

### 4.2 Erweiterte Funktionen (Phase 2+)
- Beziehungseditor mit graphischer Darstellung
- Konflikt- und Inkonsistenz-Scanner
- Batch-Editor (z. B. alle Sims einer Altersgruppe)
- Snapshot-Manager (Vergleich zwischen zwei Save-Staenden)
- Import/Export einzelner Datensegmente
- Presets (z. B. "Starter-Haushalt", "Story-Setup")

### 4.3 Expertenfunktionen (optional)
- Regel-Engine fuer benutzerdefinierte Validierungen
- Skriptbare Massenoperationen
- Plugin-Schnittstelle fuer Community-Erweiterungen

## 5. UX/UI-Konzept (userfreundliche Oberflaeche)

### 5.1 Designprinzipien
- Safety first: Keine riskante Aktion ohne Backup/Bestätigung
- Klarheit vor Tiefe: Einfache Ansicht als Standard, Expertenmodus zuschaltbar
- Sichtbare Konsequenzen: Jede Aenderung zeigt "vorher/nachher"
- Niedrige Einstiegshuerde: Gefuehrte Workflows fuer haeufige Aufgaben

### 5.2 Informationsarchitektur
- Startbildschirm:
  - "Savegame oeffnen"
  - "Letzte Projekte"
  - "Backup wiederherstellen"
- Hauptnavigation (Tabs):
  - Uebersicht
  - Sims
  - Haushalte
  - Beziehungen
  - Validierung
  - Aenderungsprotokoll

### 5.3 Spielerzentrierte User-Flows
- Flow 1: "Ich will nur schnell Geld anpassen"
  - Save laden -> Haushalt waehlen -> Simoleons aendern -> validieren -> speichern
- Flow 2: "Mein Save ist kaputt, bitte reparieren"
  - Save laden -> Scan starten -> empfohlene Fixes anzeigen -> Backup + Repair ausfuehren
- Flow 3: "Ich baue eine Story-Nachbarschaft"
  - Snapshot laden -> Beziehungen bearbeiten -> Alterslogik pruefen -> speichern

### 5.4 UI-Komponenten
- Datentabelle mit Suche/Filter
- Detailpanel mit in-place Editoren
- Warnbanner bei riskanten Feldern
- Diff-Ansicht (alt/neu)
- Statusleiste mit Validierungszustand

## 6. Technisches Konzept

### 6.1 Architektur
- Schichtenmodell:
  - Core Parser Layer (Dateiformat lesen/schreiben)
  - Domain Layer (Sims, Haushalte, Beziehungen, Regeln)
  - Application Layer (Use Cases, Validierung, Undo/Redo)
  - UI Layer (Desktop-Frontend)

### 6.2 Technologie-Optionen
Option A (Python-first):
- Backend/Core: Python
- GUI: PySide6
- Vorteile: schnell fuer Prototyping, gute Datenverarbeitung

Option B (Web-Tech Desktop):
- Backend: TypeScript/Node
- UI: React + Tauri
- Vorteile: moderne UI, starke Komponentenbibliotheken

Empfehlung fuer schnellen Start:
- Python + PySide6

### 6.3 Datenmodell (vereinfachte Entitaeten)
- Sim
  - id, name, age_stage, aspiration, skills, career, needs
- Household
  - id, name, funds, members
- Relationship
  - sim_a, sim_b, score_daily, score_lifetime, flags
- SaveProject
  - source_path, backup_path, changeset, version

### 6.4 Sicherheits- und Integritaetsmechanismen
- Schreibsperre auf Originaldatei bis Speichervorgang abgeschlossen ist
- Transactional Save (temp file -> verify -> replace)
- Signatur/Hash-Vergleich vor und nach Save
- Rollback auf letztes funktionierendes Backup

## 7. Validierungs- und Regelwerk

### 7.1 Technische Validierungen
- Dateistruktur vollstaendig und parsebar
- Referenzen auf vorhandene Objekte zeigen
- Wertebereiche gueltig (z. B. keine negativen Skill-Level)

### 7.2 Gameplay-Validierungen
- Altersphase und Karriere konsistent
- Beziehungen ohne ungueltige Gegenreferenzen
- Haushaltsdaten ohne Null-Referenzen

### 7.3 Benutzerwarnungen
- Gelb: ungewoehnlich, aber moeglich
- Rot: starkes Risiko fuer korruptes Save

## 8. Entwicklungsphasen und Roadmap

### Phase 0: Discovery (1-2 Wochen)
- Savegame-Struktur analysieren
- Testkorpus von Savegames aufbauen (vanilla + modded + defekt)
- Risikokatalog erstellen

### Phase 1: MVP Core (3-5 Wochen)
- Parser lesen/schreiben (minimal)
- Backup-System
- Basis-UI + Entity-Browser
- Kernfelder editierbar

### Phase 2: Stabilisierung (2-3 Wochen)
- Validierungsengine
- Undo/Redo
- Crash-Schutz und Fehlerdialoge
- interne Alpha-Tests

### Phase 3: Feature-Ausbau (3-4 Wochen)
- Beziehungseditor
- Diff-Ansicht
- Snapshot/Compare
- Batch-Aktionen

### Phase 4: Release Candidate (2 Wochen)
- Performance-Optimierung
- UX-Polish
- Dokumentation + Tutorial-Guide
- Beta mit Community-Feedback

### Phase 5: v1.0 Release
- Installer
- Changelog/Versionierung
- Support-Kanal und Bug-Template

## 9. Teststrategie

### 9.1 Testarten
- Unit-Tests fuer Parser und Domain-Regeln
- Integrations-Tests fuer Lade/Save-Pipeline
- Snapshot-Tests fuer Aenderungsdifferenzen
- UI-Tests fuer Kern-Workflows
- Recovery-Tests (defekte Dateien, unerwartete Abbrueche)

### 9.2 Testdaten
- Kleine, mittlere, grosse Nachbarschaften
- Savegames mit und ohne Mods
- gezielt fehlerhafte Savegames fuer Repair-Tests

### 9.3 Abnahmekriterien fuer v1.0
- Alle MVP-Features stabil
- Keine Blocker-Bugs in Top-10 Workflows
- Erfolgreiche Wiederherstellung aus Backup in 100 % der Tests

## 10. Risiken und Gegenmassnahmen

- Unklare Savegame-Spezifikation
  - Gegenmassnahme: Reverse-Engineering dokumentieren, modulare Parser
- Hohe Varianz durch Mods
  - Gegenmassnahme: Toleranter Parser + Kompatibilitaetsmatrix
- Save-Korruption durch fehlerhafte Writes
  - Gegenmassnahme: Transaktionales Speichern + Pflicht-Backup
- UX wird fuer Casuals zu komplex
  - Gegenmassnahme: Simple Mode als Default

## 11. Teamrollen (auch fuer Solo-Projekt nutzbar)

- Product/UX: Anforderungen, User-Flows, Usability-Tests
- Core Engineer: Parser, Datenmodell, Validierung
- UI Engineer: Views, State-Management, Interaktionsdesign
- QA: Testkorpus, Regressionstests, Release-Freigaben

## 12. Dokumentation und Community

- In-App Hilfesystem mit "Was passiert bei dieser Aenderung?"
- Kurze Tutorials fuer typische Spielerziele
- Oeffentliche Known-Issues-Liste
- Versionskompatibilitaet transparent dokumentieren

## 13. Konkrete erste 10 Aufgaben (Start-Backlog)

1. Savegame-Beispiele sammeln und klassifizieren.
2. Minimalen Parser-Prototyp fuer Header/Metadaten bauen.
3. Backup- und Restore-Funktion als erstes produktives Feature implementieren.
4. Datenmodell fuer Sim/Haushalt/Beziehung festlegen.
5. Read-only Browser-UI fuer Sims und Haushalte bauen.
6. Editor fuer Simoleons + Skills umsetzen.
7. Validierungsregeln fuer Wertebereiche einfuehren.
8. Undo/Redo auf Domain-Ebene implementieren.
9. Diff-Ansicht fuer Aenderungen integrieren.
10. Interne Alpha mit echten Spieler-Szenarien durchfuehren.

## 14. Definition of Done (DoD)

Ein Feature gilt als fertig, wenn:
- Code-Review erfolgt ist
- Tests vorhanden und gruen sind
- Fehlerfaelle mit Benutzerfeedback abgefangen sind
- Doku und UI-Texte aktualisiert sind
- Backup/Recovery fuer das Feature verifiziert ist

## 15. Ergebnis

Mit diesem Plan entsteht ein Savegame-Editor, der nicht nur "Cheat-Werte" aendert, sondern den realen Bedarf von Sims-2-Spielern trifft: Sicherheit fuer langjaehrige Spielstaende, schnelle Korrekturen, kreative Story-Kontrolle und transparente, risikoarme Bearbeitung.