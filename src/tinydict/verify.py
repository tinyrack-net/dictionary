"""Sanity checks for a built dictionary file (any supported format)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .config import Dictionary
from .glossary import read_glossary

_TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class VerifyResult:
    entries: int = 0
    synonyms: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def verify(dictionary: Dictionary, path: Path) -> VerifyResult:
    result = VerifyResult()
    if not path.exists():
        result.errors.append(f"missing {path}")
        return result

    queries = {c.query for c in dictionary.checks}
    # query -> [(all keys of a matching entry, plain-text definition)]
    found: dict[str, list[tuple[list[str], str]]] = {q: [] for q in queries}

    for entry in read_glossary(path):
        result.entries += 1
        terms = entry.l_term
        result.synonyms += len(terms) - 1
        for q in queries.intersection(terms):
            text = _TAG_RE.sub(" ", entry.defi)
            found[q].append((terms, text))

    if result.entries < dictionary.min_entries:
        result.errors.append(f"only {result.entries} entries (< min_entries {dictionary.min_entries})")

    for check in dictionary.checks:
        hits = found[check.query]
        if not hits:
            result.errors.append(f"{check.query!r}: not found")
            continue
        # Slob has no headword order (keys are sorted), so check membership:
        # the query must reach an entry that is also found under `headword`.
        if check.headword and all(check.headword not in terms for terms, _ in hits):
            got = sorted({t for terms, _ in hits for t in terms[:3]})
            result.errors.append(f"{check.query!r}: expected entry {check.headword!r}, got {got}")
        if check.contains and all(check.contains not in t for _, t in hits):
            result.errors.append(f"{check.query!r}: definition lacks {check.contains!r}")
    return result
