# Projektplan: S2-Atlas-Savegame-Editor

## 1. Produktvision

### 1.1 Zielbild
S2-Atlas-Savegame-Editor wird ein vollwertiger Desktop-Editor fuer `The Sims 2`-Savegames. Die Software soll echte Spielstaende nicht nur laden, sondern deren relevante Datenstrukturen systematisch analysieren, visualisieren, validieren, reparieren und gezielt veraendern koennen.

Der Anspruch ist ausdruecklich groesser als ein Cheat-Tool:
- komplette Nachbarschaften analysieren
- Sims, Haushalte, Lots und Beziehungen bearbeiten
- defekte oder inkonsistente Daten erkennen
- problematische Komponenten entfernen oder rekonstruieren
- sichere Schreibvorgaenge mit Backup, Diff, Validierung und Rollback bereitstellen
- Mod-/Custom-Content-Szenarien moeglichst robust behandeln

### 1.2 Spielerproblem
Langjaehrige Sims-2-Spielstaende werden oft durch inkonsistente Referenzen, unvollstaendige Daten, Mods, falsche Lebensphasen, fehlerhafte Beziehungsdaten oder beschaedigte Packages unbrauchbar. Gleichzeitig fehlen moderne Werkzeuge, die sowohl tief genug fuer Reparaturen als auch sicher genug fuer Alltagsnutzung sind.

### 1.3 Produktversprechen
S2-Atlas-Savegame-Editor soll:
- alles Relevante im Savegame sichtbar machen
- moeglichst alle bearbeitbaren Aspekte kontrolliert editierbar machen
- Defekte nicht nur melden, sondern in einen reproduzierbaren Repair-Workflow ueberfuehren
- Aenderungen transparent, rueckgaengig und testbar machen
- trotz technischer Tiefe leicht verstaendlich und aufgeraeumt bedienbar bleiben
- intern nach soliden Software-Standards gebaut sein

## 2. Erkenntnisse aus dem echten Referenz-Savegame

### 2.1 Verwendeter Testkorpus
Referenzpfad:
- `C:\Users\steve\Github\Sims2-Savegame\The Sims 2`

Beobachtete Struktur:
- Top-Level-Verzeichnisse wie `Neighborhoods`, `LotCatalog`, `Downloads`, `Storytelling`, `Teleport`, `Thumbnails`, `Collections`, `Config`, `Logs`
- zentrale Dateien wie `Accessory.cache`, `Groups.cache`
- in `Neighborhoods` mehrere spielbare Nachbarschaften plus `NeighborhoodManager.package`

### 2.2 Bisher verifizierte Savegame-Merkmale
Im vorliegenden Savegame wurden folgende Neighborhoods erkannt:
- `E001`: 487 Character-Packages, 68 Lots, 5 Suburbs
- `F001`: 443 Character-Packages, 36 Lots, 5 Suburbs
- `G001`: 432 Character-Packages, 35 Lots, 5 Suburbs
- `N001`: 445 Character-Packages, 38 Lots, 5 Suburbs
- `N002`: 179 Character-Packages, 11 Lots, 0 Suburbs
- `N003`: 181 Character-Packages, 26 Lots, 0 Suburbs
- `N004`: 1342 Character-Packages, 324 Lots, 6 Suburbs

Damit ist klar:
- das Tool muss grosse Savegames mit tausenden Character-Packages verarbeiten koennen
- Neighborhoods bestehen nicht nur aus einer Datei, sondern aus einem Verbund aus Haupt-Package, Character-Packages, Lot-Packages, Storytelling-Dateien, Thumbnails und optionalen Suburbs
- Repair- und Editierfunktionen muessen dateiuebergreifend arbeiten

### 2.3 Konsequenzen fuer den Projektumfang
Der Editor darf nicht nur einzelne Werte in einer abstrahierten JSON-Datei aendern. Er braucht:
- ein echtes Paket-/Ressourcenmodell
- eine referenzsichere Sicht ueber mehrere Dateien
- Scanner fuer defekte Komponenten
- transaktionale Schreibprozesse ueber mehrere beteiligte Dateien
- Performance-Strategien fuer sehr grosse Nachbarschaften

## 3. Scope: Was S2-Atlas-Savegame-Editor koennen soll

### 3.1 Vollstaendige inhaltliche Abdeckung
Das Ziel ist, alle relevanten Aspekte eines Savegames anzusehen, zu analysieren und bei Bedarf zu veraendern. Dazu gehoeren mindestens:

- Nachbarschaften
- Suburbs und deren Verknuepfungen
- Sims
- Haushalte
- Lots
- Beziehungen
- Familienbaeume und Verwandtschaft
- Erinnerungen und Metadaten
- Karriere, Skills, Beduerfnisse, Aspiration, Lebensphase
- Inventare, Besitz, Finanzen und Haushaltswerte
- Storytelling-bezogene Daten
- Verweise auf externe oder interne Ressourcen
- mod- oder custom-content-bezogene Inkonsistenzen, soweit technisch erfassbar

### 3.2 Kernfaehigkeiten
S2-Atlas-Savegame-Editor soll fuer jede unterstuetzte Datenart vier Dinge koennen:
- anzeigen
- durchsuchen und filtern
- validieren
- sicher bearbeiten, entfernen oder reparieren

### 3.3 Nicht-Ziele fuer die erste stabile Version
Folgende Themen sind nachrangig, aber nicht ausgeschlossen:
- Plugin-System fuer Dritte
- Skript-Automation fuer Endnutzer
- Linux/macOS-Unterstuetzung
- Multiplayer oder Cloud-Sync

## 4. Produktziele

### 4.1 Primaere Ziele
- Echte Sims-2-Savegames als Ordnerstruktur und als verknuepfte Paketlandschaft laden
- Alle wichtigen Entitaeten in einer einheitlichen Domain-Sicht abbilden
- Defekte Referenzen, verwaiste Daten und potenziell gefaehrliche Inkonsistenzen erkennen
- Sichere Editor-Workflows fuer Sims, Haushalte, Beziehungen, Lots und Nachbarschaften liefern
- Reparaturvorschlaege mit nachvollziehbarer Risikoklassifikation anbieten
- Schreibvorgaenge mit Backup, Diff, Integritaetschecks und Rollback absichern

### 4.2 Qualitaetsziele
- keine stillen Datenverluste
- keine unsichtbaren Auto-Fixes ohne Benutzerentscheidung
- reproduzierbare Analyseergebnisse
- klare Trennung von Lesen, Analysieren, Mutieren und Schreiben
- geringe visuelle Komplexitaet trotz grossem Funktionsumfang
- selbsterklaerende Sprache statt technischer UI-Fachsprache, wo immer moeglich
- wartbarer, testbarer und dokumentierter Code

### 4.3 Messbare Erfolgskriterien
- mindestens 95 % der Referenz-Savegames koennen read-only geoeffnet werden
- mindestens 90 % der unterstuetzten Edit-Operationen laufen mit automatischem Backup und erfolgreicher Nachvalidierung
- 100 % aller Schreibvorgaenge verwenden transaktionales Speichern
- Defekt-Scanner liefert fuer bekannte Testfaelle reproduzierbare Ergebnisse
- grosse Neighborhoods wie `N004` bleiben fuer Kernansichten interaktiv nutzbar
- Kernaufgaben wie Sim finden, Haushalt bearbeiten oder Repair-Vorschlag anwenden sind ohne Doku in wenigen Schritten moeglich

## 5. Nutzergruppen

### 5.1 Casual-Spieler
- moechte Geld, Skills, Beduerfnisse, Karriere oder Alter schnell anpassen
- braucht klare Sprache, Warnstufen und gefuehrte Flows

### 5.2 Legacy- und Story-Spieler
- moechte Beziehungen, Stammbaeume, Haushaltsstatus und Story-Fortschritt kontrollieren
- braucht Historie, Diffs und visuelle Zusammenhaenge

### 5.3 Repair- und Power-User
- moechte korruptionsnahe Probleme finden und beheben
- braucht Rohdatenansicht, Referenzgraphen, Regelpruefungen und Batch-Operationen

## 6. Funktionsumfang

### 6.1 Read-only Analyse
- Laden von `The Sims 2`, `Neighborhoods` oder einzelner Neighborhood
- Scan aller zugehoerigen Packages und Nebenressourcen
- Projektuebersicht mit Groessen, Dateianzahl, Neighborhood-Struktur und Scan-Status
- Explorer fuer Sims, Haushalte, Lots, Beziehungen, Erinnerungen und unbekannte Ressourcen
- Such- und Filterfunktionen ueber IDs, Namen, Status und Problemklassen
- Referenzansichten: Wer verweist auf wen, was ist verwaist, was ist inkonsistent

### 6.2 Editor-Funktionen
- Sims bearbeiten:
  - Name
  - Alter/Lebensphase
  - Aspiration
  - Beduerfnisse
  - Skills
  - Karriere und Karrierestufe
  - Haushaltszuordnung
  - Status-/Meta-Felder, soweit technisch abgesichert
- Haushalte bearbeiten:
  - Name
  - Funds
  - Mitglieder
  - grundlegende Metadaten
- Beziehungen bearbeiten:
  - Beziehungspaare erkennen
  - Scores und Flags anzeigen
  - Asymmetrien erkennen
  - Beziehungen hinzufuegen, korrigieren, entfernen
- Lots bearbeiten:
  - Lot-Metadaten
  - Verknuepfungen zu Haushalt/Nachbarschaft
  - problematische Lots markieren oder isolieren
- Nachbarschaften bearbeiten:
  - Name und Metadaten, soweit verfuegbar
  - Suburb-Verknuepfungen
  - globale Inkonsistenzen pruefen

### 6.3 Repair-Funktionen
- Erkennung von:
  - fehlenden Gegenreferenzen
  - ungueltigen Sim-/Household-/Lot-Referenzen
  - verwaisten Character-Packages
  - inkonsistenten Beziehungsdaten
  - defekten Haushaltsmitgliedschaften
  - unvollstaendigen Neighborhood-Verknuepfungen
  - widerspruechlichen Lebensphasen-/Karriere-/Wertebereichen
  - fehlenden oder nicht aufloesbaren Package-Abhaengigkeiten
- Repair-Aktionen:
  - Referenz neu verknuepfen
  - verwaiste Eintraege entfernen
  - defekte Datensegmente deaktivieren oder quarantainen
  - problematische Packages aus aktiven Referenzen loesen
  - automatisch erzeugte Repair-Vorschlaege mit Preview und Undo anbieten

### 6.4 Expertenmodus
- Rohdateninspektor fuer Package-Ressourcen
- Referenzgraph
- Batch-Operationen
- Regel-Engine fuer erweiterte Plausibilitaetspruefungen
- Export von Analyseberichten

## 7. UX- und Interaktionsprinzipien

### 7.1 Leitlinien
- Safety first
- Einfachheit vor Ueberfrachtung
- Sichtbarkeit vor Magie
- Read-only als Standard fuer unbekannte oder riskante Bereiche
- Vorher/Nachher immer nachvollziehbar
- progressive Offenlegung: Standardansicht zuerst, Details bei Bedarf
- klare visuelle Hierarchie, wenig Ablenkung, konsistente Navigation
- eine aufgeraeumte Oberflaeche mit fokussierten Arbeitsbereichen statt ueberladener Alles-auf-einmal-Ansichten
- Expertenmodus ohne Casual-Nutzer zu ueberfordern

### 7.2 Hauptbereiche der UI
- Dashboard
- Neighborhood Explorer
- Sim Browser
- Household Browser
- Relationship Graph
- Lot Browser
- Validation Center
- Repair Center
- Change Log / Diff
- Backup and Restore

### 7.3 UI-Prinzipien fuer Verstaendlichkeit
- jede Hauptansicht beantwortet eine klare Frage, z. B. "Welcher Sim?", "Welches Problem?", "Welche Aenderung?"
- Formulare zeigen standardmaessig nur die wichtigsten Felder
- riskante oder seltene Felder liegen in erweiterten Abschnitten
- Listen, Filter und Detailansicht folgen ueberall demselben Muster
- Warnungen sind konkret, ruhig formuliert und handlungsorientiert
- technische IDs und Rohdaten sind sichtbar, aber nicht permanent im Vordergrund
- Standard-Workflows sollen mit moeglichst wenig Klicks und ohne Fachwissen funktionieren

### 7.4 Kritische Nutzerfluesse
- Savegame oeffnen -> Scan -> Probleme anzeigen -> gezielte Reparatur
- Sim auswaehlen -> Werte aendern -> referenzbetroffene Folgeaenderungen sehen -> validieren -> speichern
- Beziehungspaare anzeigen -> Inkonsistenzen erkennen -> korrigieren -> referenzielle Integritaet pruefen
- Defektes Package erkennen -> Risiko einstufen -> entfernen/quarantainen -> Re-Scan

## 8. Technische Architektur

### 8.1 Architekturstil
Schichtenmodell mit klaren Verantwortlichkeiten:
- Input Layer: Filesystem- und Package-Zugriff
- Parser Layer: Binaerparser fuer Sims-2-Packages und Nebenformate
- Domain Layer: normierte Entitaeten, Relationen und Regeln
- Application Layer: Use Cases, Undo/Redo, Repair, Save-Transaktionen
- UI Layer: PySide6-Desktop-Anwendung

### 8.2 Zentrale technische Bausteine
- Filesystem-Scanner fuer `The Sims 2`-Ordner
- Package-Reader/Writer mit Ressourcenmodell
- Domain-Mapping fuer Sims, Haushalte, Beziehungen, Lots und Neighborhoods
- Referenzgraph ueber dateiuebergreifende IDs
- Validierungsengine
- Repair-Engine
- Diff-Engine
- Backup-/Rollback-Service
- Telemetrie-/Logging-Komponenten fuer lokale Diagnose

### 8.3 Datenmodell
Mindestens benoetigte Entitaeten:
- `SaveProject`
- `Neighborhood`
- `Suburb`
- `Sim`
- `Household`
- `Relationship`
- `Lot`
- `Memory`
- `PackageResource`
- `ReferenceIssue`
- `RepairProposal`
- `ChangeSet`
- `BackupSnapshot`

### 8.4 Performance-Anforderungen
- lazy loading fuer grosse Neighborhoods
- inkrementelle Re-Scans nach Aenderungen
- Caching fuer teure Parser-Operationen
- Hintergrundjobs fuer Validierung und Repair-Vorschlaege
- UI darf bei grossen Scans nicht blockieren

## 9. Software-Standards und Best Practices

### 9.1 Entwicklungsgrundsaetze
- klare Modulgrenzen und Single Responsibility
- Domain-getriebener Kern statt UI-zentrierter Logik
- typsicherer Python-Code
- bevorzugt reine Funktionen in Parser-, Mapping- und Validierungslogik
- explizite Fehlerklassen statt generischer Fehlerbehandlung
- keine stillen Fallbacks bei korruptionskritischen Pfaden

### 9.2 Code-Qualitaet
- `ruff` fuer Linting
- `black` oder teamweit einheitlicher Formatter
- `mypy` fuer statische Typpruefung
- durchgaengige Docstrings bei komplexen Parser-/Repair-Komponenten
- Architekturentscheidungen als ADRs dokumentieren

### 9.3 Teststrategie als Standard
- Unit-Tests fuer Parser, Mapper und Regeln
- Goldens/Snapshots fuer bekannte Package-Strukturen
- Integrations-Tests mit echten Test-Savegames
- Regressionstests fuer bekannte Korruptionsmuster
- End-to-End-Tests fuer kritische UI-Workflows
- Smoke-Tests fuer grosse Neighborhoods

### 9.4 Sicherheits- und Integritaetsstandards
- niemals direkt im Original ohne Backup schreiben
- jeder Schreibvorgang ist transaktional
- Vor- und Nachvalidierung vor finalem Replace
- Hash-/Fingerprint-basierte Aenderungskontrolle
- Crash-sichere Wiederaufnahme oder Rollback
- Repair-Aktionen immer mit Vorschau und Begruendung

### 9.5 Dokumentationsstandards
- technische Parser-Dokumentation
- Mapping-Dokumentation von Savegame-Struktur zu Domain-Modell
- Repair-Katalog mit Problemtyp, Risiko und Loesungsstrategie
- Nutzerdokumentation fuer riskante Operationen

## 10. Validierungs- und Repair-Regelwerk

### 10.1 Technische Validierungen
- Datei vorhanden, lesbar, parsebar
- Package-Struktur konsistent
- Ressourcen-IDs eindeutig und gueltig
- referenzierte Ziele existieren
- verlinkte Dateien sind vorhanden

### 10.2 Domainen-Validierungen
- Sim gehoert zu gueltigem Haushalt oder ist bewusst haushaltslos
- Household-Mitglieder existieren
- Beziehungen zeigen auf existierende Sims
- bidirektionale Beziehungen sind konsistent
- Lot-Verknuepfungen stimmen mit Neighborhood-Daten ueberein
- Lebensphase, Karriere, Wertebereiche und Flags sind plausibel

### 10.3 Repair-Klassifikation
- `info`: kosmetisch oder unkritisch
- `warning`: inkonsistent, aber meist spielbar
- `error`: datenlogisch fehlerhaft
- `critical`: hohes Korruptions- oder Absturzrisiko

### 10.4 Repair-Entscheidungslogik
Jede Repair-Aktion braucht:
- Problemklassifikation
- betroffene Entitaeten/Dateien
- Risiko-Hinweis
- geplante Mutation
- erwartete Folgeeffekte
- Undo-Unterstuetzung

## 11. Roadmap

### Phase 0: Discovery und Reverse Engineering
- Referenz-Savegames sammeln und klassifizieren
- Dateitypen, Package-Arten und Referenzmuster dokumentieren
- erstes lesbares Ressourcenmodell definieren
- bekannte Korruptionsmuster sammeln

### Phase 1: Read-only Foundation
- stabiler Filesystem-Scanner
- Neighborhood-, Character- und Lot-Inventar
- Basis-Domain-Modell
- read-only Explorer fuer Hauptentitaeten
- erste Validierungsregeln

### Phase 2: Echter Parser-Kern
- Binaerparser fuer priorisierte Package-Ressourcen
- Mapping von Package-Daten auf Sims, Haushalte, Beziehungen und Lots
- Referenzgraph und Cross-File-Index
- Performance-Benchmark mit grossen Saves

### Phase 3: Sicheres Editieren
- transaktionales Schreiben
- Backup-/Restore-Workflow
- Undo/Redo auf Domain-Ebene
- erste stabile Editoren fuer Sims, Haushalte und Beziehungen

### Phase 4: Repair Center
- Defekt-Scanner
- Regelengine und Repair-Vorschlaege
- Quarantaene-/Entfernungs-Workflows fuer defekte Komponenten
- Berichtsexport und Diff-Ansichten

### Phase 5: Vollstaendige Editor-Abdeckung
- Lots, Memories, weitere Metadaten und globale Neighborhood-Daten
- Batch-Operationen
- Expertenansichten und Rohdateninspektor
- Stabilisierung fuer modded Saves

### Phase 6: Release-Haertung
- Testabdeckung ausbauen
- UX-Polish
- Fehlerbehandlung verfeinern
- Dokumentation, Installer und Release-Prozess

## 12. Priorisiertes Backlog

1. Referenz-Savegames systematisch katalogisieren und dokumentieren.
2. Neighborhood-, Character- und Lot-Scanner finalisieren.
3. Paket-Ressourcenmodell definieren.
4. Parser fuer die ersten relevanten Sims-/Household-/Relationship-Ressourcen bauen.
5. Cross-File-Referenzindex implementieren.
6. Read-only Explorer fuer Sims, Haushalte, Lots und Beziehungen ausbauen.
7. Validierungsengine fuer Referenzen und Wertebereiche erweitern.
8. Repair-Katalog fuer bekannte Defekte definieren.
9. Transaktionales Save/Backup/Restore implementieren.
10. Erste echte Editoren fuer Sims, Haushalte und Beziehungen liefern.
11. Diff-Ansicht fuer Mutation auf Entitaets- und Dateiebene bauen.
12. Regressionstest-Korpus fuer defekte Savegames aufbauen.

## 13. Definition of Done

Ein Feature gilt nur dann als fertig, wenn:
- die fachliche Auswirkung auf das Savegame dokumentiert ist
- Unit- und Integrations-Tests vorhanden sind
- relevante Fehlerfaelle abgefangen sind
- Backup-/Rollback-Verhalten verifiziert ist
- UI-Feedback fuer Erfolg, Risiko und Fehler vorhanden ist
- die UI fuer den Anwendungsfall aufgeraeumt bleibt und keine unnoetige Komplexitaet einfuehrt
- Beschriftungen, Hinweise und Aktionen fuer Nicht-Experten verstaendlich sind
- bei Schreibfeatures eine Nachvalidierung erfolgt
- Dokumentation und Changelog aktualisiert wurden

## 14. Ergebnis

S2-Atlas-Savegame-Editor soll zu einem professionell aufgebauten Sims-2-Savegame-Editor werden, der reale Nachbarschaften umfassend lesen, verstehen, pruefen, reparieren und veraendern kann. Das Projekt richtet sich nicht auf einen engen MVP mit Beispiel-JSONs aus, sondern auf eine robuste Arbeitsumgebung fuer echte Savegames, inklusive grosser und potenziell beschaedigter Spielstaende.
