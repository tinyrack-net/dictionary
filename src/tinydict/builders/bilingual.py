"""Bilingual dictionary from two Kaikki sources.

* ``translations_source``: an English-Wiktionary-style dump whose entries carry
  ``translations`` lists; entries in ``target_lang`` become "translation" lines.
* ``glosses_source`` (optional): a target-language Wiktionary dump restricted to
  the source language (e.g. Korean Wiktionary's English entries); its glosses
  and examples are already written in the target language.
"""

from __future__ import annotations

import html
import json
import logging
from collections import OrderedDict, defaultdict
from typing import Any

from ..cleaning import inflected_forms, is_noise_etymology, is_noise_example, is_noise_sense
from ..glossary import STARDICT_WRITE_OPTIONS, new_glossary
from ..sources import iter_entries, iter_lines
from . import BuildContext

log = logging.getLogger(__name__)
esc = html.escape

POS_LABELS: dict[str, dict[str, str]] = {
    "ko": {
        "noun": "명사",
        "verb": "동사",
        "adj": "형용사",
        "adv": "부사",
        "pron": "대명사",
        "prep": "전치사",
        "conj": "접속사",
        "intj": "감탄사",
        "num": "수사",
        "name": "고유명사",
        "phrase": "구",
        "prep_phrase": "전치사구",
        "prefix": "접두사",
        "suffix": "접미사",
        "abbrev": "약어",
        "det": "한정사",
        "article": "관사",
        "particle": "불변화사",
        "proverb": "속담",
        "contraction": "축약형",
        "symbol": "기호",
        "character": "문자",
        "affix": "접사",
    },
}
UI_LABELS: dict[str, dict[str, str]] = {
    "ko": {"translations": "번역어", "synonyms": "동의어", "antonyms": "반의어", "etymology": "어원"},
}
MAX_EXAMPLES = 4
DEFAULT_UI = {
    "translations": "Translations",
    "synonyms": "Synonyms",
    "antonyms": "Antonyms",
    "etymology": "Etymology",
}


def _first_ipa(entry: dict[str, Any]) -> str | None:
    for s in entry.get("sounds") or ():
        if s.get("ipa"):
            return s["ipa"]
    return None


def _translations(entry: dict[str, Any], lang: str):
    lists = [entry.get("translations") or []]
    lists += [s.get("translations") or [] for s in entry.get("senses") or ()]
    for items in lists:
        for t in items:
            if t.get("lang_code") == lang or t.get("code") == lang:
                yield t


class Collector:
    def __init__(self, target_lang: str) -> None:
        self.lang = target_lang
        # word -> pos -> sense -> [translation]
        self.trans: dict[str, OrderedDict[str, OrderedDict[str, list[dict]]]] = defaultdict(OrderedDict)
        self.glosses: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.ipa: dict[str, str] = {}
        self.forms: dict[str, set[str]] = defaultdict(set)

    def add_glosses_entry(self, entry: dict[str, Any]) -> None:
        if any(not is_noise_sense(g) for s in entry.get("senses") or () for g in s.get("glosses") or ()):
            self.glosses[entry["word"]].append(entry)

    def add_translations_entry(self, entry: dict[str, Any]) -> None:
        ts = list(_translations(entry, self.lang))
        if not ts:
            return
        by_sense = self.trans[entry["word"]].setdefault(entry.get("pos") or "", OrderedDict())
        for t in ts:
            target = (t.get("word") or "").strip()
            if not target:
                continue
            items = by_sense.setdefault((t.get("sense") or "").strip(), [])
            key = (target, t.get("alt"), t.get("roman"))
            if all((x.get("word"), x.get("alt"), x.get("roman")) != key for x in items):
                items.append(t)

    def add_headword_details(self, entry: dict[str, Any]) -> None:
        """Record IPA and inflected forms for a headword already selected."""
        word = entry["word"]
        if word not in self.ipa and (ipa := _first_ipa(entry)):
            self.ipa[word] = ipa
        self.forms[word] |= inflected_forms(entry)

    def words(self) -> list[str]:
        return sorted(set(self.trans) | set(self.glosses), key=lambda w: (w.lower(), w))


def _pos_label(lang: str, pos: str | None, title: str | None = None) -> str:
    if title:
        return title
    if not pos or pos == "unknown":
        return ""
    return POS_LABELS.get(lang, {}).get(pos, pos)


def render(word: str, c: Collector) -> str:
    ui = UI_LABELS.get(c.lang, DEFAULT_UI)
    parts: list[str] = []

    ipa = c.ipa.get(word)
    if not ipa:
        ipa = next((i for e in c.glosses.get(word, ()) if (i := _first_ipa(e))), None)
    if ipa:
        shown = ipa if ipa.startswith(("/", "[")) else f"/{ipa}/"
        parts.append(f'<div class="ipa">{esc(shown)}</div>')

    for e in c.glosses.get(word, ()):
        if label := _pos_label(c.lang, e.get("pos"), e.get("pos_title")):
            parts.append(f'<div class="pos"><font color="green">{esc(label)}</font></div>')
        parts.append("<ol>")
        for s in e.get("senses") or ():
            glosses = [g for g in s.get("glosses") or () if not is_noise_sense(g)]
            if not glosses:
                continue
            li = esc(" ".join(glosses))
            if tags := s.get("tags"):
                li = f'<small><font color="gray">({esc(", ".join(tags))})</font></small> {li}'
            examples = [x for x in s.get("examples") or () if not is_noise_example(x.get("text") or "")]
            for x in examples[:MAX_EXAMPLES]:
                text = x["text"].strip()
                tr = (x.get("translation") or "").strip()
                li += (
                    f'<div class="ex" style="padding-left:1em;color:#555">'
                    f"{esc(text)}{(' — ' + esc(tr)) if tr else ''}</div>"
                )
            parts.append(f"<li>{li}</li>")
        parts.append("</ol>")
        for key in ("synonyms", "antonyms"):
            words = [x["word"] for x in e.get(key) or () if x.get("word")]
            if words:
                # bword:// is PyGlossary's internal link form; each writer
                # converts it for its format (kept in StarDict, stripped in slob).
                links = ", ".join(
                    f'<a href="bword://{esc(w, quote=True)}">{esc(w)}</a>' for w in dict.fromkeys(words)
                )
                parts.append(f"<div>{ui[key]}: {links}</div>")
        if ety := [t for t in e.get("etymology_texts") or () if not is_noise_etymology(t)]:
            parts.append(f"<div>{ui['etymology']}: {esc(' '.join(ety))}</div>")

    if word in c.trans:
        if word in c.glosses:
            parts.append(f'<hr><div><small><font color="gray">{ui["translations"]}</font></small></div>')
        for pos, by_sense in c.trans[word].items():
            if label := _pos_label(c.lang, pos):
                parts.append(f'<div class="pos"><font color="green">{esc(label)}</font></div>')
            parts.append("<ul>")
            for sense, items in by_sense.items():
                rendered = []
                for t in items:
                    s = f"<b>{esc(t['word'])}</b>"
                    if extra := [v for v in (t.get("alt"), t.get("roman")) if v]:
                        s += f' <small><font color="gray">({esc(", ".join(extra))})</font></small>'
                    if t.get("tags"):
                        s += f" <small><i>{esc(', '.join(t['tags']))}</i></small>"
                    rendered.append(s)
                head = f"<i>{esc(sense)}</i> → " if sense and not is_noise_sense(sense) else ""
                parts.append(f"<li>{head}{', '.join(rendered)}</li>")
            parts.append("</ul>")

    return "".join(parts)


def build(ctx: BuildContext) -> None:
    opts = ctx.dictionary.options
    lang = opts.get("target_lang")
    trans_src = opts.get("translations_source")
    gloss_src = opts.get("glosses_source")
    if not lang or not trans_src:
        raise ValueError(f"{ctx.dictionary.id}: bilingual needs target_lang and translations_source")

    c = Collector(lang)
    if gloss_src:
        for entry in iter_entries(ctx.source_path(gloss_src)):
            c.add_glosses_entry(entry)
        log.info("%s: %d words from %s", ctx.dictionary.id, len(c.glosses), gloss_src)

    # Pass 1: target-language translations. Cheap substring test skips most lines.
    needle = f'"{lang}"'
    trans_path = ctx.source_path(trans_src)
    for line in iter_lines(trans_path):
        if needle in line:
            c.add_translations_entry(json.loads(line))
    log.info("%s: %d words with %s translations", ctx.dictionary.id, len(c.trans), lang)

    # Pass 2: IPA and inflected forms for every selected headword, from all of
    # its entries (a word's translations and forms often live on different POS).
    selected = set(c.trans) | set(c.glosses)
    for entry in iter_entries(trans_path):
        if entry.get("word") in selected:
            c.add_headword_details(entry)

    glos = new_glossary()
    summary = f"{ctx.dictionary.name}: translations and target-language glosses from Wiktionary."
    for key, value in ctx.info(summary).items():
        glos.setInfo(key, value)
    for word in c.words():
        keys = [word, *sorted(c.forms.get(word, set()) - {word})]
        glos.addEntry(glos.newEntry(keys, render(word, c), defiFormat="h"))
    glos.write(str(ctx.ifo_path), formatName="Stardict", **STARDICT_WRITE_OPTIONS)
