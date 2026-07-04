# Changelog

## [Unreleased]

### Security
- Web viewer: state-changing routes (`/open/`, `/api/reset_doc/`, `/api/delete_file/`) are now POST-only (405 on GET — previously a simple `<img src>` GET could delete files), with a Host-header gate against DNS rebinding and an Origin/Referer gate against CSRF (empty Origin stays allowed so local CLI tools like curl keep working). Regression tests in `tests/test_web_viewer_security.py`.
- Web viewer: FTS5 search snippets are now HTML-escaped before `<mark>` highlighting is re-inserted (stored XSS via indexed document content).

### Changed
- Config discovery now honors `$XDG_CONFIG_HOME`/`~/.config/knowledgedigest/` on Linux/macOS (as the README already promised) and skips an empty `%APPDATA%`.
- The `summarize_model` config key is now passed through to the summarizer (was previously ignored).
- Server-specific deployment scripts removed from the public repository (kept privately).
- `llms.txt`: added `## Last-checked: 2026-06-11`, `## Audience` (5 groups), and `## Search Phrases` fenced code block (9 phrases).
- `README.md`: corrected BACH Integration link (`github.com/lukisch` → `github.com/ellmos-ai/bach`).

### Fixed
- `TODO.md` removed from Git tracking and added to `.gitignore` (contained internal audit paths).

## 2026-06-06

- Updated the test workflow to current `actions/checkout@v6` and `actions/setup-python@v6` majors.

## 2026-06-02

- Added packaging metadata so the repository can be installed as `knowledgedigest` while exposing the `KnowledgeDigest` package.
- Added GitHub Actions test workflow for Python 3.10, 3.11, and 3.12.
- Updated community workflow action versions.
- Corrected repository links from the former `lukisch` location to `file-bricks/knowledgedigest`.
- Aligned public docs with version `0.4.0` and cleaned visible encoding artifacts.

## 2026-05-17

- Added unit tests for core modules.

## 2026-05-01

- Added KnowledgeDigest icon and EXE build support.
- Backported v0.4.0 features from the local knowledge database line, including Gemini Flash summarization, deduplication, trash handling, and agent routing.
