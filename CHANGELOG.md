# Changelog

## [Unreleased]

### Changed
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
