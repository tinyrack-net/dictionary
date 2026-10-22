"""Dictionary builders.

Each builder turns one or more cached Kaikki sources into a StarDict dictionary
at ``BuildContext.ifo_path``. Other formats are converted from that StarDict.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..config import Config, Dictionary
from ..sources import SourceMeta, data_path, load_meta


@dataclass
class BuildContext:
    config: Config
    dictionary: Dictionary
    cache_dir: Path
    work_dir: Path
    output_dir: Path
    sources: dict[str, SourceMeta]

    def source_path(self, source_id: str) -> Path:
        return data_path(self.cache_dir, self.config.sources[source_id])

    def format_dir(self, format_id: str) -> Path:
        return self.output_dir / format_id

    def output_path(self, format_id: str) -> Path:
        """Main file of a format: the .ifo for StarDict, the .slob file for slob."""
        suffix = ".ifo" if format_id == "stardict" else f".{format_id}"
        return self.format_dir(format_id) / f"{self.dictionary.id}{suffix}"

    @property
    def ifo_path(self) -> Path:
        return self.output_path("stardict")

    @property
    def data_date(self) -> str:
        dates = [m.extracted for m in self.sources.values() if m.extracted]
        return max(dates) if dates else "unknown"

    @property
    def bookname(self) -> str:
        return f"{self.dictionary.name} ({self.data_date})"

    def info(self, summary: str | None = None) -> dict[str, str]:
        """Glossary info written into every output format.

        Without ``summary`` the description is left out, so a conversion keeps
        the description already stored in the StarDict source.
        """
        info = {
            "name": self.bookname,
            "website": "https://github.com/tinyrack-net/dictionary",
            "author": "Wiktionary contributors (via kaikki.org)",
            "license": "CC BY-SA 4.0 / GFDL",
            "creationTime": self.data_date,
        }
        if summary is not None:
            info["description"] = self.description(summary)
        return info

    def description(self, summary: str) -> str:
        lines = [summary]
        for m in self.sources.values():
            lines.append(
                f"Source: {m.wiktionary or 'Wiktionary'} dump {m.dump or '?'}, "
                f"extracted {m.extracted or '?'} by kaikki.org/Wiktextract."
            )
        lines.append("Data license: CC BY-SA 4.0 / GFDL (Wiktionary contributors).")
        lines.append("Built by https://github.com/tinyrack-net/dictionary")
        return " ".join(lines)


Builder = Callable[[BuildContext], None]


def get_builder(name: str) -> Builder:
    if name == "wiktextract":
        from .wiktextract import build
    elif name == "bilingual":
        from .bilingual import build
    else:
        raise ValueError(f"unknown builder {name!r}")
    return build


def make_context(config: Config, dictionary: Dictionary, cache_dir: Path, build_dir: Path) -> BuildContext:
    root = build_dir / dictionary.id
    work_dir = root / "work"
    output_dir = root / "out"
    for d in (work_dir, output_dir):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
    for format_id in dictionary.formats:
        (output_dir / format_id).mkdir()
    sources = {sid: load_meta(cache_dir, config.sources[sid]) for sid in dictionary.sources}
    return BuildContext(config, dictionary, cache_dir, work_dir, output_dir, sources)
