"""Load and validate dictionaries.toml."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote

KAIKKI_BASE = "https://kaikki.org"
BUILDERS = {"wiktextract", "bilingual"}


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Source:
    id: str
    edition: str
    language: str

    @property
    def page_url(self) -> str:
        return f"{KAIKKI_BASE}/{self.edition}/{quote(self.language)}/index.html"

    @property
    def data_url(self) -> str:
        lang = quote(self.language)
        return f"{KAIKKI_BASE}/{self.edition}/{lang}/kaikki.org-dictionary-{lang}.jsonl.gz"


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
        try:
            sources[sid] = Source(id=sid, edition=s["edition"], language=s["language"])
        except KeyError as e:
            raise ConfigError(f"source {sid!r} is missing {e.args[0]!r}") from None

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
        dictionaries[did] = Dictionary(
            id=did,
            name=d.get("name") or did,
            builder=d["builder"],
            sources=tuple(d["sources"]),
            min_entries=int(d.get("min_entries", 0)),
            checks=checks,
            options=dict(d.get("options") or {}),
        )

    return Config(path=path, sources=sources, dictionaries=dictionaries)
