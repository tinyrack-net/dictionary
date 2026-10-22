import zipfile

import pytest

from tinydict.builders.krdict import clean_text, iter_lexical_entries, parse_entry, render
from tinydict.cli import main
from tinydict.sources import parse_krdict_date

from .conftest import FIXTURES
from .test_build import _defi, _entries, _out


def _parsed(word: str, homonym: str | None = None):
    for raw in iter_lexical_entries(FIXTURES / "krdict.zip"):
        e = parse_entry(raw, "영어")
        if e.word == word and (homonym is None or e.homonym == homonym):
            return e
    raise LookupError(word)


def test_parse_krdict_date():
    header = "attachment;filename=전체 내려받기_한국어기초사전_json_20261019.zip"
    assert parse_krdict_date(header) == "2026-10-19"
    # urllib hands back UTF-8 header bytes decoded as latin-1
    assert parse_krdict_date(header.encode("utf-8").decode("latin-1")) == "2026-10-19"
    assert parse_krdict_date(None) is None


@pytest.mark.parametrize(
    "raw, text",
    [
        ("&apos;-어 먹다&apos;로 쓴다", "'-어 먹다'로 쓴다"),
        ("&lt;I&gt;latte&lt;/I&gt;", "latte"),
        ("<i>perilla</i>, biji <i>perilla</i>", "perilla, biji perilla"),
        ("их хаан<BR/>агуу", "их хаан агуу"),
    ],
)
def test_clean_text(raw, text):
    assert clean_text(raw) == text


def test_parse_entry():
    meok = _parsed("먹다", "2")
    assert meok.title == "먹다²"
    assert meok.pos == "동사"
    assert {"먹어", "먹으니"} <= set(meok.keys)
    assert meok.pronunciations == ["먹따"]
    first = meok.senses[0]
    assert first.target_lemma.startswith("eat")
    assert first.definition and first.examples

    chess = _parsed("체스")
    assert "케스" in chess.keys and "셰스" in chess.keys  # spelling variants

    apple = _parsed("사과", "1")
    assert apple.origin  # 沙果/砂果


def test_render_uses_target_language_only():
    defi = render(_parsed("사과", "1"))
    assert "apple" in defi
    assert "яблоко" not in defi and "苹果" not in defi  # other translations are dropped
    assert "dicmedia" not in defi and ".wav" not in defi  # no NIKL media links


def _run(project, *args):
    return main(
        [
            "-c", str(project / "dictionaries.toml"),
            "--cache-dir", str(project / ".cache"),
            "--build-dir", str(project / "build"),
            "--dist-dir", str(project / "dist"),
            *args,
        ]
    )  # fmt: skip


@pytest.mark.parametrize("format_id", ["stardict", "slob"])
def test_build_krdict(project, format_id):
    assert _run(project, "build", "test-ko-en") == 0
    entries = _entries(_out(project, "test-ko-en", format_id))
    assert "boat" in _defi(entries, "배")  # every homonym is reachable from the bare word
    assert "eat" in _defi(entries, "먹어")  # conjugated form
    assert "eat" in _defi(entries, "먹다²")  # superscripted homonym key
    link = 'href="bword://' if format_id == "stardict" else 'href="'
    assert link in _defi(entries, "먹다")  # related words are linked


def test_krdict_attribution(project):
    assert _run(project, "build", "test-ko-en") == 0
    with zipfile.ZipFile(project / "dist" / "test-ko-en-stardict.zip") as z:
        readme = z.read("test-ko-en/README.txt").decode("utf-8")
    assert "국립국어원" in readme and "CC BY-SA 2.0 KR" in readme
    assert "Wiktionary" not in readme
    ifo = _out(project, "test-ko-en", "stardict").read_text(encoding="utf-8")
    assert "author=National Institute of Korean Language" in ifo
