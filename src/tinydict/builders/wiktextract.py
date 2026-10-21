"""Monolingual dictionary rendered by PyGlossary's Wiktextract reader."""

from __future__ import annotations

import gzip
import json
import logging

from ..cleaning import clean_wiktextract_entry
from ..glossary import convert_wiktextract
from ..sources import iter_entries
from . import BuildContext

log = logging.getLogger(__name__)


def build(ctx: BuildContext) -> None:
    if len(ctx.dictionary.sources) != 1:
        raise ValueError(f"{ctx.dictionary.id}: wiktextract builder takes exactly one source")
    source = ctx.source_path(ctx.dictionary.sources[0])

    cleaned = ctx.work_dir / "cleaned.jsonl.gz"
    count = 0
    with gzip.open(cleaned, "wt", encoding="utf-8", compresslevel=1) as out:
        for entry in iter_entries(source):
            out.write(json.dumps(clean_wiktextract_entry(entry), ensure_ascii=False))
            out.write("\n")
            count += 1
    log.info("%s: cleaned %d entries", ctx.dictionary.id, count)

    convert_wiktextract(
        cleaned,
        ctx.ifo_path,
        info={
            "name": ctx.bookname,
            "description": ctx.description(f"{ctx.dictionary.name} built from Wiktionary."),
            "website": "https://github.com/tinyrack-net/dictionary",
        },
    )
    cleaned.unlink()
