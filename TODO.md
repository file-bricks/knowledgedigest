# Pre-Release TODO: KnowledgeDigest

**Audit Date:** 2026-05-28  
**Auditor:** GPT / Codex automation `ai-modules-care`  
**Target Repo:** `file-bricks/knowledgedigest`

---

## BLOCKER

- [x] **Secrets:** Final Gate Check meldet keine Secret-Pattern in getrackten Dateien.
- [x] **Private Data:** Final Gate Check meldet keine bekannten PII-Pattern.
- [x] **Hardcoded Paths:** Final Gate Check meldet keine persönlichen lokalen Pfade.
- [x] **Database Files:** Keine `.db`-Dateien sind in Git getrackt.
- [x] **.env Files:** Keine `.env`-Dateien sind in Git getrackt.
- [x] **BACH Internals:** Keine BACH-internen Integrationsdokumente sind getrackt; optionale BACH-Integration bleibt dokumentierte Modul-Funktion.
- [x] **.gitignore:** Mindestmuster sind vorhanden, einschließlich `__pycache__/`, `*.pyc`, `.env`, `*.db`, `.venv/`, `.idea/`, `.vscode/` und `data/`.
- [x] **LICENSE:** MIT-Lizenzdatei ist vorhanden.
- [x] **README.md:** Englische README ist vorhanden und besteht den Gate-Check.

---

## HIGH PRIORITY

- [x] Versionen konsolidieren: README-Changelog nennt v0.4.0 als neuesten Stand, `__init__.py`, `requirements.txt` und `ARCHITECTURE.md` nennen jetzt ebenfalls v0.4.0. (2026-06-01)
- [ ] Öffentliche CLI-/GUI-Texte sprachlich entscheiden: aktuell existiert ein Mix aus englischer README und deutschen Laufzeitmeldungen.
- [x] Architektur-Diagramm auf Encoding-Artefakte prüfen und bei der nächsten Doku-Runde nachziehen. (2026-06-02)
- [ ] Optionalen BACH-Import als Standalone-Funktion mit kleinem Fixture-Test absichern.

## MEDIUM PRIORITY

- [x] `CHANGELOG.md` ergänzen, damit Release-Notizen nicht nur in der README stehen. (2026-06-02)
- [x] CI-Smoke-Test für `python -m pytest tests -q` ergänzen oder bestehende GitHub Actions auf Relevanz prüfen. (2026-06-02)
- [ ] Dependency-Policy klären: `requirements.txt` nutzt Mindestversionen, aber keine reproduzierbaren Pins.

## LOW PRIORITY

- [x] README um einen kurzen Abschnitt zu lokalen Runtime-Daten (`data/knowledge.db`, `knowledgedigest.json`) ergänzen. (2026-06-02)
- [ ] Web-Viewer- und GUI-Smoke-Checks getrennt dokumentieren.

---

## STATUS

| Category | Status | Notes |
|----------|--------|-------|
| Secrets | PASS | Final Gate Check ohne Secret-Befund. |
| Private Data (PII) | PASS | Keine bekannten PII-Pattern gemeldet. |
| .gitignore | PASS | Gate-Mindestmuster sind vorhanden. |
| Language (English) | PASS | README besteht den Englisch-Check; Runtime-Sprache bleibt Folgepunkt. |
| BACH Internals | PASS | Keine internen BACH-Dokumente getrackt; Integration ist optional. |
| Database Files | PASS | Keine `.db`-Dateien in Git getrackt. |
| README.md | PASS | README vorhanden. |
| LICENSE | PASS | MIT-Lizenz vorhanden. |
| Tests | PASS | `python -m pytest tests -q` bestanden am 2026-05-28. |
| **Overall** | **GATE PASS / RELEASE FOLLOW-UPS OPEN** | Gate sauber, Release-Qualität noch weiter verbessern. |

**Audit Date:** 2026-05-28  
**Gate Check Exit Code:** `0` nach Hygiene-Patch

---

*Erstellt beim `.MODULES`-Care-Check am 2026-05-28. Quelle für Gate-Regeln: `C:\Users\User\OneDrive\.TOPICS\.AI\.MODULES\RELEASE-POLICY.md`.*
