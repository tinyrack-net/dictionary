"""Clean-up rules for Wiktextract data quirks."""

from __future__ import annotations

import re
from typing import Any

# Pseudo-forms emitted by inflection-table parsing, not real words.
_BOGUS_FORM_TAGS = {"table-tags", "inflection-template", "class"}
_BOGUS_FORMS = {"-", "—", "–", ""}
MAX_FORM_LENGTH = 80

# Inflection tag sets that are useful as lookup keys (e.g. "went" -> "go").
INFLECTION_TAGS = {
    frozenset({"plural"}),
    frozenset({"past"}),
    frozenset({"participle", "past"}),
    frozenset({"participle", "present"}),
    frozenset({"present", "singular", "third-person"}),
    frozenset({"comparative"}),
    frozenset({"superlative"}),
}

# Fields PyGlossary's Wiktextract reader never renders; dropping them shrinks the
# intermediate file and speeds up parsing.
_UNUSED_ENTRY_FIELDS = (
    "head_templates",
    "etymology_templates",
    "inflection_templates",
    "translations",
    "derived",
    "descendants",
    "categories",
    "wikipedia",
    "hyphenation",
    "hyphenations",
    "abbreviations",
)
_UNUSED_SENSE_FIELDS = ("categories", "translations", "id", "senseid", "wikidata", "wikipedia")


def is_bogus_form(form: dict[str, Any], word: str) -> bool:
    text = (form.get("form") or "").strip()
    if text in _BOGUS_FORMS or text == word or len(text) > MAX_FORM_LENGTH:
        return True
    return bool(_BOGUS_FORM_TAGS.intersection(form.get("tags") or ()))


def clean_wiktextract_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of an entry ready for PyGlossary's Wiktextract reader."""
    word = entry.get("word", "")
    out = {k: v for k, v in entry.items() if k not in _UNUSED_ENTRY_FIELDS}
    if "forms" in out:
        out["forms"] = [f for f in out["forms"] if not is_bogus_form(f, word)]
    if "senses" in out:
        out["senses"] = [{k: v for k, v in s.items() if k not in _UNUSED_SENSE_FIELDS} for s in out["senses"]]
    return out


def inflected_forms(entry: dict[str, Any]) -> set[str]:
    word = entry.get("word", "")
    forms = set()
    for f in entry.get("forms") or ():
        if is_bogus_form(f, word):
            continue
        if frozenset(f.get("tags") or ()) in INFLECTION_TAGS:
            forms.add(f["form"].strip())
    return forms


# Korean Wiktionary leaves audio widget labels and citation fragments in examples.
_NOISE_EXAMPLE_RE = re.compile(r"^(음성 듣기\b.*|\d{4}, .*\(public domain\).*)$")
_NOISE_SENSE_RE = re.compile(r"^,?\s*.*\(public domain\)\s*$")


def is_noise_example(text: str) -> bool:
    return not text.strip() or bool(_NOISE_EXAMPLE_RE.match(text.strip()))


def is_noise_sense(text: str | None) -> bool:
    return bool(text and _NOISE_SENSE_RE.match(text.strip()))


def is_noise_etymology(text: str | None) -> bool:
    """Pronunciation blocks that Korean Wiktionary parsing files under etymology."""
    return not text or not text.strip() or text.lstrip().startswith("음성 듣기")
