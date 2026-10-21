"""Shared fixtures: a tiny project using trimmed real Kaikki entries."""

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
"""


@pytest.fixture(autouse=True)
def _quiet_pyglossary():
    quiet(False)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A project dir with config and pre-fetched source cache."""
    (tmp_path / "dictionaries.toml").write_text(CONFIG, encoding="utf-8")
    for sid, fixture, extracted in (("en", "en.jsonl.gz", "2026-10-03"), ("ko", "ko.jsonl.gz", "2026-10-21")):
        d = tmp_path / ".cache" / "sources" / sid
        d.mkdir(parents=True)
        shutil.copy(FIXTURES / fixture, d / "data.jsonl.gz")
        meta = {
            "id": sid,
            "url": f"https://example.invalid/{sid}.jsonl.gz",
            "size": (d / "data.jsonl.gz").stat().st_size,
            "etag": f'"{sid}-etag"',
            "last_modified": None,
            "extracted": extracted,
            "wiktionary": f"{sid}wiktionary",
            "dump": "2026-09-02",
        }
        (d / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return tmp_path


@pytest.fixture
def config(project: Path):
    return load_config(project / "dictionaries.toml")
