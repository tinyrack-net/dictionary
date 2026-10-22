# AGENTS.md

## Scope

Guidance for agents working in `tinyrack-net/dictionary`. This repo builds
offline dictionaries (StarDict and slob) from kaikki.org Wiktextract data and
국립국어원 한국어기초사전 (krdict), and publishes them as GitHub releases. When this file disagrees with `pyproject.toml`,
`dictionaries.toml`, the workflows or the tests, trust the code and fix the
stale doc.

## Layout

| Path | Role |
| --- | --- |
| `dictionaries.toml` | Source datasets and the dictionaries built from them |
| `src/tinydict/cli.py` | `tinydict` CLI: `fetch`, `build`, `release-tag`, `release-notes` |
| `src/tinydict/config.py` | Loads and validates the config |
| `src/tinydict/sources.py` | Downloads sources (kaikki, krdict), records version metadata and attribution |
| `src/tinydict/cleaning.py` | Fixes Wiktextract data quirks (bogus forms, noise text) |
| `src/tinydict/glossary.py` | PyGlossary wrappers: output formats, conversion, reading built files |
| `src/tinydict/builders/` | `wiktextract`, `bilingual`, `krdict` and `krdict-reverse` builders (all emit StarDict) |
| `src/tinydict/verify.py` | Entry count and sample lookup checks, run on every format |
| `src/tinydict/package.py` | Release assets per format, attribution README, `manifest.json` |
| `tests/` | pytest suite using trimmed real entries in `tests/fixtures/` |
| `.github/workflows/` | `ci.yml` (lint and test), `release.yml` (weekly build and release) |

## Commands

Use uv with the Python version in `.python-version`.

- `uv sync`: install dependencies.
- `uv run pytest`: run the tests (fast; no network).
- `uv run ruff check . && uv run ruff format --check .`: lint.
- `uv run tinydict fetch`: download sources to `.cache/` (about 520 MB).
- `uv run tinydict build [ids...]`: full build into `build/` and `dist/`
  (about 10 minutes for all dictionaries and formats).

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
- Support each app with a format it handles natively, written by PyGlossary's
  stock writers. Don't patch PyGlossary output to make one format work in an
  app built for another. For example, OSS-Dict ignores StarDict's `bword://`
  links, so Android users get the slob, whose writer emits plain links.
- Builders produce StarDict only. Add a format by adding it to
  `glossary.FORMATS` and `config.FORMATS`. Hand-written HTML (the `bilingual`
  builder) links entries with `bword://<term>`, like PyGlossary, so every
  writer converts the links for its format.
- `glossary.read_slob` reads slob refs directly, because PyGlossary's slob
  reader drops alternate keys. Slob keys are not headword-first, so checks
  compare key membership, not `l_term[0]`.
- Importing PyGlossary replaces `sys.excepthook`. `glossary.py` restores it.
  Import PyGlossary only through `tinydict.glossary`.
- Every release asset must keep the CC BY-SA attribution: `README.txt` in
  zips, and the `license.name` tag and description in slob (`package.py`,
  `BuildContext.info`).
- krdict: the export is downloaded anonymously from
  `https://krdict.korean.go.kr/dicBatchDownload?seq=220` (JSON zip). No account
  is needed. The version is the date in the `Content-Disposition` file name,
  because the server sends no ETag. Use text fields only. NIKL media URLs
  (`dicmedia.korean.go.kr`: audio, images, video) have separate terms and must
  not be copied into the output. Values contain HTML entities and inline tags,
  so read them through `krdict.clean_text`.
- Attribution comes from the sources (`SourceMeta.credit()` / `.license`).
  Don't hard-code one project's credit in shared code.
- Keep slob file names free of dates. OSS-Dict uses the slob `uri` tag (taken
  from the file name) to keep bookmarks and history across updates.
- Don't add the GitHub Actions `cache` for `.cache/`. The source data is large,
  and the cache would always be stale by the time a release runs.
