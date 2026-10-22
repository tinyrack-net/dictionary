"""Shared fixtures: a tiny project using trimmed real source entries."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from tinydict.config import load_config
from tinydict.glossary import quiet

FIXTURES = Path(__file__).parent / "fixtures"

CONFIG = """
[sources.en]
edition = "dictionary"
language = "English"

[sources.ko]
edition = "kowiktionary"
language = "영어"

[sources.krdict]
type = "krdict"

[[dictionaries]]
id = "test-en"
name = "Test English"
builder = "wiktextract"
sources = ["en"]
min_entries = 5
checks = [
  { query = "went", headword = "go" },
  { query = "dictionary", contains = "IPA" },
]

[[dictionaries]]
id = "test-en-ko"
name = "Test 영한"
builder = "bilingual"
sources = ["en", "ko"]
min_entries = 3
checks = [
  { query = "bank", contains = "은행" },
  { query = "went", headword = "go" },
]

[dictionaries.options]
target_lang = "ko"
translations_source = "en"
glosses_source = "ko"

[[dictionaries]]
id = "test-ko-en"
name = "Test 한영"
builder = "krdict"
sources = ["krdict"]
min_entries = 5
checks = [
  { query = "사과", contains = "apple" },
  { query = "먹어", headword = "먹다" },
]

[dictionaries.options]
target_lang = "영어"
"""

# source id -> (fixture file, cached file name, release/extract date, url)
SOURCES = {
    "en": ("en.jsonl.gz", "data.jsonl.gz", "2026-10-03", "https://example.invalid/en.jsonl.gz"),
    "ko": ("ko.jsonl.gz", "data.jsonl.gz", "2026-10-21", "https://example.invalid/ko.jsonl.gz"),
    "krdict": (
        "krdict.zip",
        "data.zip",
        "2026-10-19",
        "https://krdict.korean.go.kr/dicBatchDownload?seq=220",
    ),
}


@pytest.fixture(autouse=True)
def _quiet_pyglossary():
    quiet(False)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A project dir with config and pre-fetched source cache."""
    (tmp_path / "dictionaries.toml").write_text(CONFIG, encoding="utf-8")
    for sid, (fixture, name, date, url) in SOURCES.items():
        d = tmp_path / ".cache" / "sources" / sid
        d.mkdir(parents=True)
        shutil.copy(FIXTURES / fixture, d / name)
        meta = {
            "id": sid,
            "url": url,
            "size": (d / name).stat().st_size,
            "etag": f'"{sid}-etag"',
            "last_modified": None,
            "extracted": date,
            "wiktionary": None if sid == "krdict" else f"{sid}wiktionary",
            "dump": date if sid == "krdict" else "2026-09-02",
        }
        (d / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return tmp_path


@pytest.fixture
def config(project: Path):
    return load_config(project / "dictionaries.toml")
