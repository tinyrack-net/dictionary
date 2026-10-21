"""Thin wrappers around PyGlossary."""

from __future__ import annotations

import logging
import sys
from functools import cache
from pathlib import Path

_excepthook = sys.excepthook
from pyglossary.glossary_v2 import ConvertArgs, Glossary  # noqa: E402

# PyGlossary replaces sys.excepthook on import; on Windows its hook opens a
# blocking error dialog. Keep Python's default behaviour.
sys.excepthook = _excepthook

STARDICT_WRITE_OPTIONS = {"dictzip": True}


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


def read_stardict(ifo: Path) -> Glossary:
    glos = new_glossary()
    if not glos.directRead(str(ifo), formatName="Stardict"):
        raise OSError(f"cannot read {ifo}")
    return glos
