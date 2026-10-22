"""Korean dictionary from 한국어기초사전 (Basic Korean Dictionary, NIKL).

The export is LMF-style JSON (``LexicalResource.Lexicon.LexicalEntry``), split
over several files in a zip. Every sense has a Korean definition plus
translations in 11 languages; ``target_lang`` selects which translation to show
(e.g. ``"영어"``).

Each homonym (배¹ belly, 배² boat, ...) becomes its own entry. Conjugated forms
(먹어, 먹으니, ...) and spelling variants are added as lookup keys.

Only text is used. Pronunciation audio, images and video are linked from NIKL's
servers under separate terms and are left out.
"""

from __future__ import annotations

import html
import json
import logging
import re
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from ..glossary import STARDICT_WRITE_OPTIONS, new_glossary
from . import BuildContext

log = logging.getLogger(__name__)
esc = html.escape

SUPERSCRIPT = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
NO_EQUIVALENT = "(no equivalent expression)"
MAX_EXAMPLES = 5


def _list(x: Any) -> list:
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


_TAG_RE = re.compile(r"<\s*/?\s*(?:i|b|br|sup|sub|u)\s*/?\s*>", re.IGNORECASE)


def clean_text(value: str) -> str:
    """Plain text from an export value.

    Values carry HTML entities (``&apos;``, ``&quot;``) and a few inline tags
    (``<I>``, ``<BR/>``), sometimes themselves escaped. Unescape and drop the
    tags; rendering escapes the text again.
    """
    text = html.unescape(html.unescape(value))
    text = _TAG_RE.sub(lambda m: " " if "br" in m.group(0).lower() else "", text)
    return " ".join(text.split())


def _feats(node: dict) -> dict[str, list[str]]:
    """``{"feat": [{"att": a, "val": v}, ...]}`` -> ``{a: [clean text, ...]}``."""
    out: dict[str, list[str]] = {}
    for f in _list(node.get("feat")):
        if "val" in f:
            out.setdefault(f["att"], []).append(clean_text(f["val"]))
    return out


def _one(feats: dict[str, list[str]], key: str) -> str:
    vals = feats.get(key) or [""]
    return vals[0].strip()


@dataclass
class Sense:
    definition: str
    target_lemma: str = ""
    target_definition: str = ""
    pattern: str = ""
    annotation: str = ""
    examples: list[tuple[str, list[str]]] = field(default_factory=list)  # (type, lines)
    relations: list[tuple[str, str, str]] = field(default_factory=list)  # (type, lemma, homonym)


@dataclass
class Entry:
    word: str
    homonym: str
    pos: str
    unit: str
    origin: str
    level: str
    category: str
    annotation: str
    pronunciations: list[str]
    keys: list[str]  # conjugations and variants
    see_also: list[tuple[str, str]]  # (type, word)
    senses: list[Sense]

    @property
    def title(self) -> str:
        if self.homonym and self.homonym != "0":
            return self.word + self.homonym.translate(SUPERSCRIPT)
        return self.word


def parse_entry(e: dict, target_lang: str) -> Entry:
    feats = _feats(e)
    lemmas = _list(e.get("Lemma"))
    word = _one(_feats(lemmas[0]), "writtenForm")
    keys: list[str] = []
    for extra in lemmas[1:]:
        for v in _feats(extra).get("variant", []):
            keys += [s.strip() for s in v.split(",")]

    pronunciations: list[str] = []
    for wf in _list(e.get("WordForm")):
        f = _feats(wf)
        kind = _one(f, "type")
        if kind == "발음":
            pronunciations += [p for p in f.get("pronunciation", []) if p]
        elif kind == "활용":
            keys += [w for w in f.get("writtenForm", []) if w]

    see_also = [
        (_one(f, "type"), _one(f, "writtenForm"))
        for f in map(_feats, _list(e.get("RelatedForm")))
        if _one(f, "writtenForm")
    ]

    senses = []
    for s in _list(e.get("Sense")):
        f = _feats(s)
        sense = Sense(
            definition=_one(f, "definition"),
            pattern=_one(f, "syntacticPattern"),
            annotation=_one(f, "annotation"),
        )
        for q in map(_feats, _list(s.get("Equivalent"))):
            if _one(q, "language") == target_lang:
                lemma = _one(q, "lemma")
                sense.target_lemma = "" if lemma == NO_EQUIVALENT else lemma
                sense.target_definition = _one(q, "definition")
        for x in map(_feats, _list(s.get("SenseExample"))):
            lines = [t.strip() for t in x.get("example", []) if t.strip()]
            if lines:
                sense.examples.append((_one(x, "type"), lines))
        for r in map(_feats, _list(s.get("SenseRelation"))):
            if _one(r, "lemma"):
                sense.relations.append((_one(r, "type"), _one(r, "lemma"), _one(r, "homonymNumber")))
        senses.append(sense)

    return Entry(
        word=word,
        homonym=_one(feats, "homonym_number"),
        pos=_one(feats, "partOfSpeech"),
        unit=_one(feats, "lexicalUnit"),
        origin=_one(feats, "origin"),
        level=_one(feats, "vocabularyLevel"),
        category=_one(feats, "semanticCategory"),
        annotation=_one(feats, "annotation"),
        pronunciations=list(dict.fromkeys(pronunciations)),
        keys=[k for k in dict.fromkeys(keys) if k and k != word],
        see_also=see_also,
        senses=senses,
    )


def iter_lexical_entries(path) -> Iterator[dict]:
    """Yield raw LexicalEntry objects from the export zip, in file order."""
    with zipfile.ZipFile(path) as z:
        names = sorted(
            (n for n in z.namelist() if n.endswith(".json")),
            key=lambda n: int(n.split("_", 1)[0]) if n.split("_", 1)[0].isdigit() else 0,
        )
        for name in names:
            with z.open(name) as f:
                data = json.load(f)
            yield from _list(data["LexicalResource"]["Lexicon"]["LexicalEntry"])


def _link(word: str) -> str:
    # bword:// is PyGlossary's internal link form; each writer converts it.
    return f'<a href="bword://{esc(word, quote=True)}">{esc(word)}</a>'


def render(e: Entry) -> str:
    parts: list[str] = []
    head = []
    if e.pronunciations:
        head.append(esc("[" + " / ".join(e.pronunciations) + "]"))
    if e.origin:
        head.append(f"<span>{esc(e.origin)}</span>")
    if head:
        parts.append(f"<div>{' '.join(head)}</div>")

    tags = [t for t in (e.pos if e.pos != "품사 없음" else e.unit, e.level) if t]
    if tags:
        parts.append(f'<div class="pos"><font color="green">{esc(" · ".join(tags))}</font></div>')
    if e.annotation:
        parts.append(f'<div><small><font color="gray">{esc(e.annotation)}</font></small></div>')

    parts.append("<ol>")
    for s in e.senses:
        li = ""
        if s.pattern:
            li += f'<small><font color="gray">【{esc(s.pattern)}】</font></small> '
        li += esc(s.definition)
        if s.target_lemma or s.target_definition:
            li += '<div style="color:#1a5fb4">'
            if s.target_lemma:
                li += f"<b>{esc(s.target_lemma)}</b>"
            if s.target_definition:
                li += f"{': ' if s.target_lemma else ''}{esc(s.target_definition)}"
            li += "</div>"
        if s.annotation:
            li += f'<div><small><font color="gray">{esc(s.annotation)}</font></small></div>'
        # Full sentences and dialogues first; short phrases only fill remaining space.
        examples = sorted(s.examples, key=lambda x: x[0] == "구")[:MAX_EXAMPLES]
        for kind, lines in examples:
            text = " / ".join(f"「{ln}」" for ln in lines) if kind == "대화" else lines[0]
            li += f'<div class="ex" style="padding-left:1em;color:#555">{esc(text)}</div>'
        rels: dict[str, list[str]] = {}
        for kind, lemma, _ in s.relations:
            rels.setdefault(kind, []).append(lemma)
        for kind, lemmas in rels.items():
            li += (
                f"<div><small>{esc(kind)}: {', '.join(_link(w) for w in dict.fromkeys(lemmas))}</small></div>"
            )
        parts.append(f"<li>{li}</li>")
    parts.append("</ol>")

    groups: dict[str, list[str]] = {}
    for kind, word in e.see_also:
        groups.setdefault("참고" if kind.startswith("☞") else kind, []).append(word)
    for kind, words in groups.items():
        parts.append(f"<div>{esc(kind)}: {', '.join(_link(w) for w in dict.fromkeys(words))}</div>")
    if e.category:
        parts.append(f'<div><small><font color="gray">{esc(e.category)}</font></small></div>')
    return "".join(parts)


def build(ctx: BuildContext) -> None:
    if len(ctx.dictionary.sources) != 1:
        raise ValueError(f"{ctx.dictionary.id}: krdict builder takes exactly one source")
    target_lang = ctx.dictionary.options.get("target_lang", "영어")

    glos = new_glossary()
    summary = f"{ctx.dictionary.name}: 한국어기초사전 definitions, examples and {target_lang} translations."
    for key, value in ctx.info(summary).items():
        glos.setInfo(key, value)

    count = 0
    for raw in iter_lexical_entries(ctx.source_path(ctx.dictionary.sources[0])):
        e = parse_entry(raw, target_lang)
        if not e.word or not e.senses:
            continue
        # Headword first; superscripted title as a key so "배²" can be searched.
        keys = [e.word, *([e.title] if e.title != e.word else []), *e.keys]
        defi = f"<div><b>{esc(e.title)}</b></div>" + render(e)
        glos.addEntry(glos.newEntry(keys, defi, defiFormat="h"))
        count += 1
    log.info("%s: %d entries", ctx.dictionary.id, count)
    glos.write(str(ctx.ifo_path), formatName="Stardict", **STARDICT_WRITE_OPTIONS)
