"""Load and validate dictionaries.toml."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote

KAIKKI_BASE = "https://kaikki.org"
KRDICT_BASE = "https://krdict.korean.go.kr"
# 한국어기초사전 "사전 전체 내려받기" item ids (download popup): JSON zip.
KRDICT_JSON_SEQ = "220"
SOURCE_TYPES = {"kaikki", "krdict"}
BUILDERS = {"wiktextract", "bilingual", "krdict", "krdict-reverse"}
# Builders always produce StarDict; other formats are converted from it.
FORMATS = ("stardict", "slob")
DEFAULT_FORMATS = FORMATS


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Source:
    """A downloadable dataset.

    * ``kaikki``: a Wiktextract JSONL dump from kaikki.org
      (``edition`` + ``language`` select the page).
    * ``krdict``: the full 한국어기초사전 (Basic Korean Dictionary) JSON export.
    """

    id: str
    type: str = "kaikki"
    edition: str = ""
    language: str = ""

    @property
    def page_url(self) -> str | None:
        if self.type == "kaikki":
            return f"{KAIKKI_BASE}/{self.edition}/{quote(self.language)}/index.html"
        return None

    @property
    def data_url(self) -> str:
        if self.type == "krdict":
            return f"{KRDICT_BASE}/dicBatchDownload?seq={KRDICT_JSON_SEQ}"
        lang = quote(self.language)
        return f"{KAIKKI_BASE}/{self.edition}/{lang}/kaikki.org-dictionary-{lang}.jsonl.gz"

    @property
    def data_name(self) -> str:
        return "data.zip" if self.type == "krdict" else "data.jsonl.gz"


@dataclass(frozen=True)
class Check:
    query: str
    headword: str | None = None
    contains: str | None = None


@dataclass(frozen=True)
class Dictionary:
    id: str
    name: str
    builder: str
    sources: tuple[str, ...]
    min_entries: int = 0
    checks: tuple[Check, ...] = ()
    formats: tuple[str, ...] = DEFAULT_FORMATS
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Config:
    path: Path
    sources: dict[str, Source]
    dictionaries: dict[str, Dictionary]

    def select(self, ids: list[str] | None) -> list[Dictionary]:
        if not ids:
            return list(self.dictionaries.values())
        unknown = [i for i in ids if i not in self.dictionaries]
        if unknown:
            raise ConfigError(f"unknown dictionary id(s): {', '.join(unknown)}")
        return [self.dictionaries[i] for i in ids]

    def sources_for(self, dicts: list[Dictionary]) -> list[Source]:
        ids = dict.fromkeys(s for d in dicts for s in d.sources)
        return [self.sources[i] for i in ids]


def load_config(path: Path) -> Config:
    with path.open("rb") as f:
        raw = tomllib.load(f)

    sources: dict[str, Source] = {}
    for sid, s in (raw.get("sources") or {}).items():
        stype = s.get("type", "kaikki")
        if stype not in SOURCE_TYPES:
            raise ConfigError(f"source {sid!r}: type must be one of {sorted(SOURCE_TYPES)}")
        if stype == "kaikki":
            missing = [k for k in ("edition", "language") if not s.get(k)]
            if missing:
                raise ConfigError(f"source {sid!r} is missing {missing[0]!r}")
        sources[sid] = Source(
            id=sid, type=stype, edition=s.get("edition", ""), language=s.get("language", "")
        )

    dictionaries: dict[str, Dictionary] = {}
    for d in raw.get("dictionaries") or []:
        did = d.get("id")
        if not did:
            raise ConfigError("dictionary without id")
        if did in dictionaries:
            raise ConfigError(f"duplicate dictionary id {did!r}")
        if d.get("builder") not in BUILDERS:
            raise ConfigError(f"{did}: builder must be one of {sorted(BUILDERS)}")
        missing = [s for s in d.get("sources", []) if s not in sources]
        if missing or not d.get("sources"):
            raise ConfigError(f"{did}: unknown or empty sources {missing}")
        checks = tuple(Check(**c) for c in d.get("checks", []))
        formats = tuple(d.get("formats", DEFAULT_FORMATS))
        if "stardict" not in formats or any(f not in FORMATS for f in formats):
            raise ConfigError(f"{did}: formats must include 'stardict' and only use {list(FORMATS)}")
        dictionaries[did] = Dictionary(
            id=did,
            name=d.get("name") or did,
            builder=d["builder"],
            sources=tuple(d["sources"]),
            min_entries=int(d.get("min_entries", 0)),
            checks=checks,
            formats=formats,
            options=dict(d.get("options") or {}),
        )

    return Config(path=path, sources=sources, dictionaries=dictionaries)
