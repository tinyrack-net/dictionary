"""Thin wrappers around PyGlossary.

Output formats are written with PyGlossary's stock plugins and options only, so
each format follows its own conventions (e.g. ``bword://`` links in StarDict,
plain links in slob).
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from functools import cache
from pathlib import Path

_excepthook = sys.excepthook
from pyglossary.glossary_v2 import ConvertArgs, Glossary  # noqa: E402

# PyGlossary replaces sys.excepthook on import; on Windows its hook opens a
# blocking error dialog. Keep Python's default behaviour.
sys.excepthook = _excepthook

STARDICT_WRITE_OPTIONS = {"dictzip": True}
SLOB_WRITE_OPTIONS = {"compression": "zlib", "content_type": "text/html; charset=utf-8"}

# Output format id -> (PyGlossary format name, file suffix, write options)
FORMATS: dict[str, tuple[str, str, dict]] = {
    "stardict": ("Stardict", ".ifo", STARDICT_WRITE_OPTIONS),
    "slob": ("Aard2Slob", ".slob", SLOB_WRITE_OPTIONS),
}


@cache
def init() -> None:
    Glossary.init()


def quiet(verbose: bool) -> None:
    logging.getLogger("pyglossary").setLevel(logging.INFO if verbose else logging.WARNING)


def new_glossary() -> Glossary:
    init()
    return Glossary()


def convert_wiktextract(
    input_path: Path,
    output_ifo: Path,
    info: dict[str, str],
) -> None:
    """Convert a Wiktextract JSONL file to StarDict via PyGlossary's reader."""
    glos = new_glossary()
    glos.convert(
        ConvertArgs(
            inputFilename=str(input_path),
            inputFormat="Wiktextract",
            outputFilename=str(output_ifo),
            outputFormat="Stardict",
            readOptions={"audio": False, "categories": False},
            writeOptions=dict(STARDICT_WRITE_OPTIONS),
            sqlite=True,
            infoOverride=info,
        )
    )


def convert_stardict(input_ifo: Path, output: Path, format_id: str, info: dict[str, str]) -> None:
    """Convert a built StarDict dictionary to another format."""
    format_name, _, options = FORMATS[format_id]
    glos = new_glossary()
    glos.convert(
        ConvertArgs(
            inputFilename=str(input_ifo),
            inputFormat="Stardict",
            outputFilename=str(output),
            outputFormat=format_name,
            writeOptions=dict(options),
            infoOverride=info,
        )
    )


@dataclass
class DictEntry:
    """A built entry: lookup keys (headword first) and HTML definition."""

    l_term: list[str]
    defi: str


def read_stardict(ifo: Path) -> Glossary:
    glos = new_glossary()
    if not glos.directRead(str(ifo), formatName="Stardict"):
        raise OSError(f"cannot read {ifo}")
    return glos


def read_slob(path: Path) -> Iterator[DictEntry]:
    """Yield slob entries with all keys that point to the same content.

    PyGlossary's slob reader yields one key per blob, so alternate lookup keys
    (inflected forms) would be invisible. Read the refs directly instead.
    """
    from pyglossary import slob

    with slob.Slob(str(path)) as s:
        keys: dict[int, list[str]] = {}
        blobs = {}
        for blob in s:
            if blob.content_type.split(";")[0] != slob.MIME_HTML:
                continue
            keys.setdefault(blob.identity, []).append(blob.key)
            blobs.setdefault(blob.identity, blob)
        for identity, terms in keys.items():
            yield DictEntry(terms, blobs[identity].content.decode("utf-8"))


def read_glossary(path: Path) -> Iterator[DictEntry]:
    """Iterate a built dictionary (StarDict .ifo or .slob)."""
    if path.suffix == ".slob":
        yield from read_slob(path)
        return
    for entry in read_stardict(path):
        yield DictEntry(list(entry.l_term), entry.defi)
