import json
import zipfile

from tinydict.cli import main
from tinydict.glossary import read_stardict
from tinydict.sources import parse_page_dates


def _entries(ifo):
    return {e.l_term[0]: e for e in read_stardict(ifo)}


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
    by_id = {m["id"]: m for m in manifest["dictionaries"]}
    assert set(by_id) == {"test-en", "test-en-ko"}
    assert by_id["test-en"]["name"] == "Test English (2026-10-03)"
    assert by_id["test-en-ko"]["data_date"] == "2026-10-21"

    with zipfile.ZipFile(project / "dist" / by_id["test-en"]["asset"]) as z:
        names = set(z.namelist())
    assert {
        "test-en/test-en.ifo",
        "test-en/test-en.idx",
        "test-en/test-en.dict.dz",
        "test-en/README.txt",
    } <= names

    ifo = (project / "build" / "test-en-ko" / "stardict" / "test-en-ko.ifo").read_text(encoding="utf-8")
    assert "bookname=Test 영한 (2026-10-21)\n" in ifo  # no auto "(en-ko)" suffix


def test_monolingual_content(project):
    assert _run(project, "build", "test-en") == 0
    entries = _entries(project / "build" / "test-en" / "stardict" / "test-en.ifo")
    go = [
        e
        for e in read_stardict(project / "build" / "test-en" / "stardict" / "test-en.ifo")
        if "went" in e.l_term
    ]
    assert go and go[0].l_term[0] == "go"
    for e in entries.values():
        assert "-" not in e.l_term and "no-table-tags" not in e.l_term
        # cross-references must be plain relative links (OSS-Dict ignores bword://)
        assert "bword://" not in e.defi
    assert any('href="' in e.defi for e in entries.values())


def test_bilingual_content(project):
    assert _run(project, "build", "test-en-ko") == 0
    entries = _entries(project / "build" / "test-en-ko" / "stardict" / "test-en-ko.ifo")
    bank = entries["bank"].defi
    assert "은행" in bank
    assert "Banking day" in bank  # example from Korean Wiktionary
    dictionary = entries["dictionary"].defi
    assert "번역어" in dictionary and "辭典" in dictionary
    assert "음성 듣기" not in entries["beautiful"].defi
    assert '<a href="lovely">lovely</a>' in entries["beautiful"].defi  # linked synonym
    assert "public domain" not in entries["beautiful"].defi.split("동의어")[0]
    assert "went" in entries["go"].l_term


def test_failed_check_returns_error(project):
    cfg = project / "dictionaries.toml"
    cfg.write_text(
        cfg.read_text(encoding="utf-8").replace('contains = "은행"', 'contains = "없는말"'), encoding="utf-8"
    )
    assert _run(project, "build", "test-en-ko") == 1
    assert not (project / "dist" / "test-en-ko-stardict.zip").exists()


def test_release_tag(project, capsys):
    assert _run(project, "release-tag") == 0
    tag = capsys.readouterr().out.strip()
    assert tag.startswith("2026-10-21-") and len(tag) == len("2026-10-21-") + 8
