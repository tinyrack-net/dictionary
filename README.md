# Tinyrack Dictionary

Offline dictionaries built automatically from [Wiktionary](https://www.wiktionary.org/)
data published by [kaikki.org](https://kaikki.org/) (extracted with
[Wiktextract](https://github.com/tatuylonen/wiktextract)).

A scheduled GitHub Actions workflow checks Kaikki every week. When the data
changes, it rebuilds the dictionaries and publishes them as a GitHub release.

## Dictionaries

| ID | Name | Contents |
| --- | --- | --- |
| `wiktionary-en` | Wiktionary English | English-English. About 1.5M entries with definitions, examples, IPA, part of speech, usage tags, inflections, etymology, synonyms and antonyms |
| `wiktionary-en-ko` | Wiktionary 영한 | English-Korean. Korean glosses and examples from Korean Wiktionary, plus Korean translations from English Wiktionary. About 33K headwords |

You can look up a word by its inflected forms too. For example, `went` finds
`go`, and `dictionaries` finds `dictionary`.

## Download

Get the latest files from
[Releases](https://github.com/tinyrack-net/dictionary/releases/latest). Each
`<id>-stardict.zip` contains one folder with these files:

```
wiktionary-en/
├─ wiktionary-en.ifo        dictionary info
├─ wiktionary-en.idx        index
├─ wiktionary-en.dict.dz    compressed definitions
├─ wiktionary-en.syn        inflected forms and alternate keys
└─ README.txt               sources and license
```

`manifest.json` in each release lists the entry counts, source dump dates and
SHA-256 checksums.

## Using the dictionaries

The files use the StarDict format, so any app that reads StarDict can open them.

| Platform | App | How |
| --- | --- | --- |
| Windows / macOS / Linux | [GoldenDict-ng](https://github.com/xiaoyifang/goldendict-ng) | Unzip into a folder, then add the folder under *Edit → Dictionaries → Sources → Files* and enable *Recursive* |
| Android | [OSS-Dict](https://github.com/Akylas/OSS-Dict) (Play Store, F-Droid) | In the *Dictionaries* tab, tap **+** and pick the downloaded `.zip` as is. Don't unzip it. The first open unpacks it into app storage |
| E-readers | [KOReader](https://koreader.rocks/) | Copy the unzipped folder to `koreader/data/dict/` |

To see English definitions and Korean translations for the same word, turn on
both dictionaries. Most apps then show the results together.

## Building locally

Requirements: [uv](https://docs.astral.sh/uv/) and about 5 GB of free disk space.

```sh
uv sync
uv run tinydict fetch            # download source data to .cache/ (skips unchanged files)
uv run tinydict build            # build, verify and package all dictionaries into dist/
uv run tinydict build wiktionary-en-ko   # build one dictionary
```

The English dump is about 520 MB compressed. A full build takes about 7 minutes.

| Command | What it does |
| --- | --- |
| `tinydict fetch [ids...]` | Downloads source data into `.cache/sources/<source>/` and records its ETag and dump dates |
| `tinydict fetch --metadata-only` | Refreshes metadata without downloading the data |
| `tinydict build [ids...]` | Builds StarDict files into `build/<id>/stardict/`, checks them, then writes zips and `manifest.json` to `dist/` |
| `tinydict release-tag` | Prints `<data date>-<fingerprint>`. The tag changes when source data, config, code or locked dependencies change |
| `tinydict release-notes` | Prints Markdown release notes from `dist/manifest.json` |

## Adding a dictionary

Dictionaries are defined in [`dictionaries.toml`](dictionaries.toml).

```toml
[sources.enwiktionary-ja]          # https://kaikki.org/dictionary/Japanese/
edition = "dictionary"             # "dictionary" = English Wiktionary,
language = "Japanese"              # "kowiktionary" = Korean Wiktionary, ...

[[dictionaries]]
id = "wiktionary-ja"
name = "Wiktionary Japanese-English"
builder = "wiktextract"
sources = ["enwiktionary-ja"]
min_entries = 100_000              # the build fails if there are fewer entries
checks = [                         # sample lookups that must pass
  { query = "食べた", headword = "食べる" },
  { query = "辞書", contains = "dictionary" },
]
```

Builders:

- **`wiktextract`**: one source. Uses PyGlossary's Wiktextract reader after
  removing junk inflection forms and fields the reader doesn't use.
- **`bilingual`**: translations from one source in `target_lang`, optionally
  combined with glosses from a Wiktionary edition written in the target
  language. Options are `target_lang`, `translations_source` and
  `glosses_source`.

A build fails, and nothing is released, if any check fails or the entry count
is below `min_entries`.

## Releases

[`.github/workflows/release.yml`](.github/workflows/release.yml) runs every
Monday and can also be started by hand. It:

1. Reads the source metadata and computes the release tag.
2. Stops if a release with that tag already exists. Running it by hand with
   `force` skips this check.
3. Otherwise it downloads the data, builds and verifies the dictionaries, and
   publishes the zips and `manifest.json` to a release.

## License

- **Code**: [GPL-3.0-or-later](LICENSE).
- **Dictionary data**: written by Wiktionary contributors and licensed under
  [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) and the
  [GFDL](https://www.gnu.org/licenses/fdl-1.3.html). Every released zip
  includes a `README.txt` with the source and license notice. If you share
  modified dictionaries, use the same license.
