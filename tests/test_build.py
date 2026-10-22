import json
import zipfile

import pytest

from tinydict.cli import main
from tinydict.glossary import read_glossary
from tinydict.sources import parse_page_dates


def _out(project, did, format_id):
    suffix = ".ifo" if format_id == "stardict" else f".{format_id}"
    return project / "build" / did / "out" / format_id / f"{did}{suffix}"


def _entries(path):
    """Map every lookup key to its entries' definitions (joined).

    Slob stores keys sorted rather than headword-first, so index by all keys.
    """
    by_key: dict[str, list] = {}
    for e in read_glossary(path):
        for t in e.l_term:
            by_key.setdefault(t, []).append(e)
    return by_key


def _defi(entries, key):
    return "".join(e.defi for e in entries[key])


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


def test_parse_page_dates():
    html = (
        "<p>This dictionary is based on structured data extracted on 2026-10-03 from the "
        "<b>enwiktionary</b> dump dated 2026-09-02 using wiktextract</p>"
    )
    assert parse_page_dates(html) == {
        "extracted": "2026-10-03",
        "wiktionary": "enwiktionary",
        "dump": "2026-09-02",
    }
    assert parse_page_dates("nothing")["extracted"] is None


def test_build_all(project):
    assert _run(project, "build") == 0

    manifest = json.loads((project / "dist" / "manifest.json").read_text(encoding="utf-8"))
    by_key = {(m["id"], m["format"]): m for m in manifest["dictionaries"]}
    assert set(by_key) == {
        ("test-en", "stardict"),
        ("test-en", "slob"),
        ("test-en-ko", "stardict"),
        ("test-en-ko", "slob"),
        ("test-ko-en", "stardict"),
        ("test-ko-en", "slob"),
    }
    assert by_key["test-en", "stardict"]["name"] == "Test English (2026-10-03)"
    assert by_key["test-en-ko", "slob"]["data_date"] == "2026-10-21"
    assert by_key["test-en-ko", "slob"]["asset"] == "test-en-ko.slob"
    # Both formats hold the same entries and lookup keys.
    for did in ("test-en", "test-en-ko"):
        sd, sl = by_key[did, "stardict"], by_key[did, "slob"]
        assert (sd["entries"], sd["synonyms"]) == (sl["entries"], sl["synonyms"])

    with zipfile.ZipFile(project / "dist" / by_key["test-en", "stardict"]["asset"]) as z:
        names = set(z.namelist())
    assert {
        "test-en/test-en.ifo",
        "test-en/test-en.idx",
        "test-en/test-en.dict.dz",
        "test-en/README.txt",
    } <= names
    assert (project / "dist" / "test-en-ko.slob").is_file()

    ifo = _out(project, "test-en-ko", "stardict").read_text(encoding="utf-8")
    assert "bookname=Test 영한 (2026-10-21)\n" in ifo  # no auto "(en-ko)" suffix


def test_slob_metadata(project):
    from pyglossary import slob

    assert _run(project, "build", "test-en-ko") == 0
    with slob.Slob(str(_out(project, "test-en-ko", "slob"))) as s:
        tags = dict(s.tags)
    assert tags["label"] == "Test 영한 (2026-10-21)"
    assert tags["license.name"] == "CC BY-SA 4.0 / GFDL"
    assert tags["created.at"] == "2026-10-21"
    assert tags["uri"] == "test-en-ko_slob"  # stable across releases


@pytest.mark.parametrize("format_id", ["stardict", "slob"])
def test_monolingual_content(project, format_id):
    assert _run(project, "build", "test-en") == 0
    entries = _entries(_out(project, "test-en", format_id))
    assert any("go" in e.l_term for e in entries["went"])  # inflected form reaches "go"
    assert "-" not in entries and "no-table-tags" not in entries
    # Links follow each format's own convention, written by stock PyGlossary.
    defis = "".join(e.defi for es in entries.values() for e in es)
    if format_id == "stardict":
        assert 'href="bword://' in defis
    else:
        assert "bword://" not in defis and 'href="' in defis


@pytest.mark.parametrize("format_id", ["stardict", "slob"])
def test_bilingual_content(project, format_id):
    assert _run(project, "build", "test-en-ko") == 0
    entries = _entries(_out(project, "test-en-ko", format_id))
    bank = _defi(entries, "bank")
    assert "은행" in bank
    assert "Banking day" in bank  # example from Korean Wiktionary
    dictionary = _defi(entries, "dictionary")
    assert "번역어" in dictionary and "辭典" in dictionary
    beautiful = _defi(entries, "beautiful")
    assert "음성 듣기" not in beautiful
    assert "public domain" not in beautiful.split("동의어")[0]
    href = "bword://lovely" if format_id == "stardict" else "lovely"
    assert f'<a href="{href}">lovely</a>' in beautiful  # linked synonym
    assert any("went" in e.l_term for e in entries["go"])


def test_failed_check_returns_error(project):
    cfg = project / "dictionaries.toml"
    cfg.write_text(
        cfg.read_text(encoding="utf-8").replace('contains = "은행"', 'contains = "없는말"'), encoding="utf-8"
    )
    assert _run(project, "build", "test-en-ko") == 1
    assert not (project / "dist" / "test-en-ko-stardict.zip").exists()
    assert not (project / "dist" / "test-en-ko.slob").exists()


def test_release_tag(project, capsys):
    assert _run(project, "release-tag") == 0
    tag = capsys.readouterr().out.strip()
    assert tag.startswith("2026-10-21-") and len(tag) == len("2026-10-21-") + 8
