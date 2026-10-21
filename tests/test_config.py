from pathlib import Path

import pytest

from tinydict.config import ConfigError, load_config

ROOT = Path(__file__).parents[1]


def test_repo_config_is_valid():
    cfg = load_config(ROOT / "dictionaries.toml")
    assert {"wiktionary-en", "wiktionary-en-ko"} <= set(cfg.dictionaries)
    for d in cfg.dictionaries.values():
        assert d.checks, f"{d.id} should have verification checks"


def test_source_urls(config):
    ko = config.sources["ko"]
    assert ko.data_url == (
        "https://kaikki.org/kowiktionary/%EC%98%81%EC%96%B4/kaikki.org-dictionary-%EC%98%81%EC%96%B4.jsonl.gz"
    )
    assert config.sources["en"].page_url == "https://kaikki.org/dictionary/English/index.html"


def test_select(config):
    assert [d.id for d in config.select(None)] == ["test-en", "test-en-ko"]
    assert [s.id for s in config.sources_for(config.select(["test-en"]))] == ["en"]
    with pytest.raises(ConfigError):
        config.select(["nope"])


@pytest.mark.parametrize(
    "body, message",
    [
        ('[[dictionaries]]\nid="x"\nbuilder="nope"\nsources=[]', "builder"),
        ('[[dictionaries]]\nid="x"\nbuilder="wiktextract"\nsources=["missing"]', "sources"),
        ('[sources.a]\nedition="dictionary"', "language"),
    ],
)
def test_invalid_config(tmp_path, body, message):
    p = tmp_path / "c.toml"
    p.write_text(body, encoding="utf-8")
    with pytest.raises(ConfigError, match=message):
        load_config(p)
