from tinydict.cleaning import (
    clean_wiktextract_entry,
    inflected_forms,
    is_bogus_form,
    is_noise_etymology,
    is_noise_example,
    is_noise_sense,
)

ENTRY = {
    "word": "raven",
    "pos": "verb",
    "forms": [
        {"form": "no-table-tags", "tags": ["table-tags"]},
        {"form": "glossary", "tags": ["inflection-template"]},
        {"form": "-", "tags": ["imperative", "past"]},
        {"form": "ravens", "tags": ["present", "singular", "third-person"]},
        {"form": "ravened", "tags": ["past"]},
        {"form": "ravin", "tags": ["alternative"]},
        {"form": "x" * 100, "tags": ["plural"]},
    ],
    "translations": [{"code": "ko", "word": "x"}],
    "head_templates": [{"name": "en-verb"}],
    "senses": [{"glosses": ["to devour"], "categories": ["c"], "id": "s1"}],
}


def test_bogus_forms():
    assert is_bogus_form({"form": "-"}, "w")
    assert is_bogus_form({"form": "w"}, "w")
    assert is_bogus_form({"form": "glossary", "tags": ["inflection-template"]}, "w")
    assert not is_bogus_form({"form": "ws", "tags": ["plural"]}, "w")


def test_clean_entry_drops_bogus_forms_and_unused_fields():
    out = clean_wiktextract_entry(ENTRY)
    assert [f["form"] for f in out["forms"]] == ["ravens", "ravened", "ravin"]
    assert "translations" not in out and "head_templates" not in out
    assert out["senses"] == [{"glosses": ["to devour"]}]
    # input is untouched
    assert len(ENTRY["forms"]) == 7


def test_inflected_forms_only_inflections():
    assert inflected_forms(ENTRY) == {"ravens", "ravened"}


def test_noise_filters():
    assert is_noise_example("음성 듣기 미국")
    assert is_noise_example("2016, VOA Learning English (public domain)")
    assert not is_noise_example("This dictionary is good. 이 사전은 좋다.")
    assert is_noise_sense(", VOA Learning English (public domain)")
    assert not is_noise_sense("attractive")
    assert not is_noise_sense(None)
    assert is_noise_etymology("음성 듣기 미국\n\nIPA [doʊ]")
    assert not is_noise_etymology("< 라틴어 dictio")
