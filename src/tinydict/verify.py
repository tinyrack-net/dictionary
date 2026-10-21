"""Sanity checks for a built StarDict dictionary."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .config import Dictionary
from .glossary import read_stardict

_TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class VerifyResult:
    entries: int = 0
    synonyms: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def verify(dictionary: Dictionary, ifo: Path) -> VerifyResult:
    result = VerifyResult()
    if not ifo.exists():
        result.errors.append(f"missing {ifo}")
        return result

    queries = {c.query for c in dictionary.checks}
    found: dict[str, list[tuple[str, str]]] = {q: [] for q in queries}

    for entry in read_stardict(ifo):
        result.entries += 1
        terms = entry.l_term
        result.synonyms += len(terms) - 1
        for q in queries.intersection(terms):
            text = _TAG_RE.sub(" ", entry.defi)
            found[q].append((terms[0], text))

    if result.entries < dictionary.min_entries:
        result.errors.append(f"only {result.entries} entries (< min_entries {dictionary.min_entries})")

    for check in dictionary.checks:
        hits = found[check.query]
        if not hits:
            result.errors.append(f"{check.query!r}: not found")
            continue
        if check.headword and all(h != check.headword for h, _ in hits):
            heads = sorted({h for h, _ in hits})
            result.errors.append(f"{check.query!r}: expected headword {check.headword!r}, got {heads}")
        if check.contains and all(check.contains not in t for _, t in hits):
            result.errors.append(f"{check.query!r}: definition lacks {check.contains!r}")
    return result
