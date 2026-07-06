<img src="assets/banner.svg" width="100%" alt="KnowledgeDigest Banner">

# KnowledgeDigest — Portable Wissensdatenbank

**[English](README.md)** | [Deutsch](README_de.md)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Lizenz: MIT](https://img.shields.io/badge/Lizenz-MIT-yellow.svg)](LICENSE)
[![SQLite FTS5](https://img.shields.io/badge/Suche-FTS5-green.svg)]()

> Portable, eigenständige Wissensdatenbank — indexiert Dokumente, chunked sie und macht sie über FTS5 durchsuchbar. Optionale LLM-Zusammenfassung. PySide6 Desktop-GUI + Web-Viewer.

---

## Einstieg

| Thema | Ort |
|---|---|
| Installation | `pip install git+https://github.com/file-bricks/knowledgedigest.git` |
| Schnellstart | [Schnellstart](#schnellstart) unten |
| CLI-Referenz | `knowledgedigest --help` |
| Englisches README | [README.md](README.md) |
| Tests | `python -m pytest -q` |
| Changelog | [CHANGELOG.md](CHANGELOG.md) |
| Issues / Feedback | [GitHub Issues](https://github.com/file-bricks/knowledgedigest/issues) |

## Warum es existiert

LLM-Agentenprojekte verlieren oft den Kontext zwischen den Durchläufen oder duplizieren Notizen über verschiedene Werkzeuge hinweg. KnowledgeDigest hält den Wissensspeicher schlank, portabel und wiederverwendbar:

- Extrahiere Text aus Dokumenten (PDF, DOCX, HTML, TXT, MD) lokal.
- Chunking-Engine mit satzgrenzenbasiertem Splitting für optimale LLM-Verarbeitung.
- Lokale SQLite-Datenbank mit FTS5-Index (BM25-Ranking und Such-Snippet-Hervorhebung).
- Optionale LLM-Zusammenfassungs-Queue (Claude Haiku / Gemini Flash).
- Keine externen Server oder Cloud-Abhängigkeiten für die Grundfunktionen notwendig (Offline-First).
- Einfache Integration für Multi-Agenten-Systeme (z. B. BACH-System).

## Installation

Über GitHub:

```bash
pip install git+https://github.com/file-bricks/knowledgedigest.git
```

Aus einem lokalen Verzeichnis:

```bash
pip install -e .
```

Der PyPI-Paketname `knowledgedigest` ist für dieses Projekt reserviert, aber noch nicht offiziell veröffentlicht. Bis zum ersten PyPI-Release bitte die Installation über GitHub nutzen.

## Schnellstart

```python
from KnowledgeDigest import KnowledgeDigest
from KnowledgeDigest.config import get_config

kd = KnowledgeDigest(config=get_config())

# Verzeichnis hinzufügen und indexieren
kd.add_directory("/pfad/zu/docs")
kd.scan_directory("/pfad/zu/docs", recursive=True)

# Suchen
results = kd.search_all("künstliche intelligenz", limit=10)
for r in results:
    print(f"{r['filename']}: {r['snippet'][:80]}...")
```

High-Level CLI:

```bash
# GUI starten
python -m KnowledgeDigest --gui

# Web-Viewer starten
python -m KnowledgeDigest --web

# Status abfragen
python -m KnowledgeDigest status

# Zusammenfassungen generieren (mit --flash für Gemini Flash API)
python -m KnowledgeDigest summarize --flash --limit 20
```

## Hauptkonzepte

1. **Text-Extraktion**: Integrierte Parser für PDF (via PyMuPDF), Word-Dokumente (.docx), HTML-Seiten, Markdown- und reine Textdateien.
2. **Chunking**: Zerlegung großer Dokumente in kleinere Sinneinheiten (Standard: ~350 Wörter) unter Berücksichtigung von Satzgrenzen, um Kontext für LLMs optimal aufzubereiten.
3. **FTS5-Suche**: Volltextsuche direkt über SQLite FTS5 mit BM25-Relevanzbewertung und dynamischen Such-Snippets.
4. **Zusammenfassungen (Summarization)**: Eine asynchrone Warteschlange verarbeitet Chunks und generiert strukturierte Zusammenfassungen (3-5 Sätze), Keywords und Domain-Tags mittels LLM (Haiku oder Gemini Flash).

## Schnittstellen

| Schnittstelle | Befehl | Version |
|---|---|---|
| **Desktop-GUI** | `python -m KnowledgeDigest --gui` | v0.4.0 |
| **Web-Viewer** | `python -m KnowledgeDigest --web` | v0.4.0 |
| **CLI** | `python -m KnowledgeDigest status` | v0.1.0+ |
| **Python API** | `from KnowledgeDigest import KnowledgeDigest` | v0.1.0+ |
| **SQLite Direct** | Beliebiges SQLite-Tool auf `knowledge.db` | Immer |

## Desktop-GUI

Bietet ein geteiltes 3-Spalten-Layout mit modernem Dark-Theme:
- **Links**: Liste der indexierten Verzeichnisse mit Dokumentenanzahl.
- **Mitte**: Sortier- und filterbare Dokumententabelle.
- **Rechts**: Live-Vorschau des ausgewählten Dokuments (Text, PDF-Vorschau via PyMuPDF, Metadaten).

## Web-Viewer

Ein leichtgewichtiger, im Browser laufender Viewer (basiert rein auf der Python Standardbibliothek, benötigt keine Framework-Abhängigkeiten):
- **Dashboard**: Statistiken zu Dokumenten und Verarbeitungszustand.
- **Suche**: Volltextsuche mit farblicher Hervorhebung der Treffer.
- **Details**: Ansicht einzelner Dokumentenchunks, Keywords und LLM-Zusammenfassungen.

## Konfiguration

JSON-basierte Konfiguration (`knowledgedigest.json`), die in folgender Reihenfolge gesucht wird:
1. `--config` CLI-Argument
2. Aktuelles Arbeitsverzeichnis
3. Pfad neben der Datenbankdatei
4. `%APPDATA%\KnowledgeDigest\` (Windows) / `~/.config/knowledgedigest/` (Linux)
5. Standardkonfiguration

Wichtige Parameter:

| Parameter | Standardwert | Beschreibung |
|---|---|---|
| `db_path` | `data/knowledge.db` | Pfad zur SQLite-Datenbank |
| `indexed_directories` | `[]` | Liste der zu indexierenden Verzeichnisse |
| `chunk_size` | `350` | Anzahl Wörter pro Chunk |
| `web_port` | `8787` | Port des Web-Viewers |
| `bach_enabled` | `false` | Aktivierung der optionalen BACH-Systemintegration |

## BACH-Integration (Optional)

KnowledgeDigest kann optional mit dem Agentensystem [BACH](https://github.com/ellmos-ai/bach) integriert werden. Bei `bach_enabled: true` und gesetztem `bach_db_path` werden BACH-Skills und Wiki-Artikel automatisch indexiert und fließen in die Suchergebnisse ein.

## Voraussetzungen

- Python 3.10+
- PySide6 (für Desktop-GUI)
- PyMuPDF (für PDF-Vorschau in der GUI)
- Für CLI und Web-Viewer sind keine zusätzlichen externen Abhängigkeiten notwendig.

## Laufzeitdaten

Lokale Laufzeitdaten (wie `data/knowledge.db` oder `knowledgedigest.json`) werden von Git ignoriert und sollten nicht in das Repository eingecheckt werden.

## Changelog

**v0.4.0 (Aktuell)**
- **Gemini Flash Summarizer**: Schnelle und kostengünstige API-Option (`--flash`) für Zusammenfassungen hinzugefügt (Standardmodell `gemini-2.0-flash`, konfigurierbar über `GEMINI_MODEL`; erfordert das optionale Paket `google-genai`).
- **Agent Tollbooth (`zoll_station.py`)**: Intelligente Steuerung für KI-Agenten, die die Zusammenfassungswarteschlange abarbeiten.
- **Physischer Papierkorb**: Button in der GUI und im Web-Viewer hinzugefügt, um Dateiduplikate physisch in einen dynamischen `_Papierkorb`-Ordner zu verschieben (Post-Route im Web-Viewer integriert).
- **Deduplizierungs-CLI**: Befehl `python -m KnowledgeDigest deduplicate` hinzugefügt, um kryptografische Duplikate aufzuspüren und DB sowie Dateisystem zu bereinigen.
- **Summary Reset**: Option zum Zurücksetzen fehlerhafter Zusammenfassungen hinzugefügt, um Dokumente wieder in die Ingest-Queue zu verschieben.

## Siehe auch: WikiStub-Seed

[WikiStub-Seed](https://github.com/dev-bricks/WikiStub-Seed) is a related knowledge dataset from the dev-bricks org: 630 multilingual stub articles across 12 domains (DE/EN + es/ja/ru/zh), deployable as a self-contained wiki module. Useful as a structured seed corpus for KnowledgeDigest indexing workflows.

## Siehe auch: ProFiler

Benötigen Sie PDF-Verschlüsselung, OCR-Texterkennung, Anonymisierung oder Dateiversionierung? Sehen Sie sich [ProFiler](https://github.com/file-bricks/ProFiler) an -- eine professionelle Dateiverwaltungssuite aus derselben Feder.

| Feature | KnowledgeDigest | ProFiler |
|---|---|---|
| **Schwerpunkt** | Wissenssuche, Chunking, LLM-Zusammenfassungen | Dateiverwaltung, PDF-Tools, OCR, Datenschutz |
| **Suche** | FTS5 mit BM25-Ranking, Snippet-Hervorhebung | Multi-Datenbanken, Filter nach Typ/Größe/Datum |
| **KI** | LLM-Zusammenfassungen, Keyword-Extraktion | -- |
| **PDF** | Nur Lesen (Text-Extraktion) | Verschlüsseln, Entschlüsseln, Extrahieren, OCR |
| **Datenschutz** | -- | Anonymisierung, Redaktionswerkzeug, Clipboard-Schutz |
| **Schnittstellen** | Desktop-GUI, Web-Viewer, CLI, Python API | Desktop-GUI, System-Tray-App |
| **Lizenz** | MIT | AGPL v3 |

## Lizenz

MIT License — Copyright (c) 2026 Lukas Geiger

## Autor

Lukas Geiger ([github.com/lukisch](https://github.com/lukisch))

---

## Haftung / Liability

Dieses Projekt ist eine **unentgeltliche Open-Source-Schenkung** im Sinne der §§ 516 ff. BGB. Die Haftung des Urhebers ist gemäß **§ 521 BGB** auf **Vorsatz und grobe Fahrlässigkeit** beschränkt. Ergänzend gelten die Haftungsausschlüsse der MIT-Lizenz.

Nutzung auf eigenes Risiko. Keine Wartungszusage, keine Verfügbarkeitsgarantie, keine Gewähr für Fehlerfreiheit oder Eignung für einen bestimmten Zweck.

This project is an unpaid open-source donation. Liability is limited to intent and gross negligence (§ 521 German Civil Code). Use at your own risk. No warranty, no maintenance guarantee, no fitness-for-purpose assumed.
