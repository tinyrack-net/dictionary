# AGENTS.md

## Scope

Guidance for agents working in `tinyrack-net/dictionary`. This repo builds
offline StarDict dictionaries from kaikki.org Wiktextract data and publishes
them as GitHub releases. When this file disagrees with `pyproject.toml`,
`dictionaries.toml`, the workflows or the tests, trust the code and fix the
stale doc.

## Layout

| Path | Role |
| --- | --- |
| `dictionaries.toml` | Source datasets and the dictionaries built from them |
| `src/tinydict/cli.py` | `tinydict` CLI: `fetch`, `build`, `release-tag`, `release-notes` |
| `src/tinydict/config.py` | Loads and validates the config |
| `src/tinydict/sources.py` | Downloads Kaikki data, reads page metadata, iterates JSONL |
| `src/tinydict/cleaning.py` | Fixes Wiktextract data quirks (bogus forms, noise text) |
| `src/tinydict/builders/` | `wiktextract` (monolingual) and `bilingual` builders |
| `src/tinydict/verify.py` | Entry count and sample lookup checks |
| `src/tinydict/package.py` | Release zips, attribution README, `manifest.json` |
| `tests/` | pytest suite using trimmed real entries in `tests/fixtures/` |
| `.github/workflows/` | `ci.yml` (lint and test), `release.yml` (weekly build and release) |

## Commands

Use uv with the Python version in `.python-version`.

- `uv sync`: install dependencies.
- `uv run pytest`: run the tests (fast; no network).
- `uv run ruff check . && uv run ruff format --check .`: lint.
- `uv run tinydict fetch`: download sources to `.cache/` (about 520 MB).
- `uv run tinydict build [ids...]`: full build into `build/` and `dist/`
  (about 7 minutes for all dictionaries).

`.cache/`, `build/` and `dist/` are gitignored. Never commit data or build
output.

## Rules

- Run `uv run pytest` and both ruff commands before finishing any code change.
  When a change affects build output, also run a real build of the affected
  dictionary and check sample entries.
- New cleanup rules go in `cleaning.py` and need tests in `tests/test_cleaning.py`.
- Every dictionary in `dictionaries.toml` needs `min_entries` and at least one
  `checks` entry, so a broken build fails instead of being released.
- The release tag includes a hash of the config, `src/tinydict/**/*.py` and
  `uv.lock`. Changing any of these makes the next scheduled run publish a new
  release.
- Importing PyGlossary replaces `sys.excepthook`. `glossary.py` restores it.
  Import PyGlossary only through `tinydict.glossary`.
- Every release zip must keep the CC BY-SA attribution (`package.py`).
- Don't add the GitHub Actions `cache` for `.cache/`. The source data is large,
  and the cache would always be stale by the time a release runs.
