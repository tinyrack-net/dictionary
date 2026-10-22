# Tinyrack Dictionary

Offline dictionaries built automatically from open data:

- [Wiktionary](https://www.wiktionary.org/) data published by
  [kaikki.org](https://kaikki.org/) (extracted with
  [Wiktextract](https://github.com/tatuylonen/wiktextract))
- [한국어기초사전](https://krdict.korean.go.kr/) (Basic Korean Dictionary) by
  국립국어원 (National Institute of Korean Language)

A scheduled GitHub Actions workflow checks the sources every week. When the
data changes, it rebuilds the dictionaries and publishes them as a GitHub
release.

## Dictionaries

| ID | Name | Contents |
| --- | --- | --- |
| `wiktionary-en` | Wiktionary English | English-English. About 1.5M entries with definitions, examples, IPA, part of speech, usage tags, inflections, etymology, synonyms and antonyms |
| `wiktionary-en-ko` | Wiktionary 영한 | English-Korean. Korean glosses and examples from Korean Wiktionary, plus Korean translations from English Wiktionary. About 33K headwords |
| `krdict-ko-en` | 한국어기초사전 한영 | Korean-English. About 57K entries from the Basic Korean Dictionary: Korean definitions with hand-written English translations, pronunciation, Hanja origin, vocabulary level, sentence and dialogue examples, and related words |
| `krdict-en-ko` | 한국어기초사전 영한 | English-Korean, built by reversing `krdict-ko-en`. About 49K English words and phrases, each listing the Korean words translated by it (basic vocabulary first) with their English sense and Korean definition. Results link to `krdict-ko-en`, so install both |

You can look up a word by its inflected forms too. For example, `went` finds
`go`, and `먹어` finds `먹다`. Korean homonyms are separate entries; search
the bare word (`배`) to see all of them, or a numbered form (`배²`) for one.

## Download

Get the latest files from
[Releases](https://github.com/tinyrack-net/dictionary/releases/latest). Every
dictionary comes in two formats with the same entries:

| File | Format | Use with |
| --- | --- | --- |
| `<id>.slob` | [slob](https://github.com/itkach/slob) (Aard 2) | Android: OSS-Dict, Aard 2. Also GoldenDict-ng |
| `<id>-stardict.zip` | StarDict | Desktop: GoldenDict-ng. E-readers: KOReader |

A `.slob` is a single file that apps read in place. Each `-stardict.zip`
contains one folder:

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

Both formats are written by PyGlossary's standard writers, so each follows its
own format's conventions. For example, links between entries use `bword://` in
StarDict and plain links in slob, the form each target app expects.

## Using the dictionaries

| Platform | App | File | How |
| --- | --- | --- | --- |
| Android | [OSS-Dict](https://github.com/Akylas/OSS-Dict) (Play Store, F-Droid) or Aard 2 | `.slob` | In the *Dictionaries* tab, tap **+** and pick the `.slob` file |
| Windows / macOS / Linux | [GoldenDict-ng](https://github.com/xiaoyifang/goldendict-ng) | `-stardict.zip` | Unzip into a folder, then add the folder under *Edit → Dictionaries → Sources → Files* and enable *Recursive* |
| E-readers | [KOReader](https://koreader.rocks/) | `-stardict.zip` | Copy the unzipped folder to `koreader/data/dict/` |

OSS-Dict can also open the StarDict zip, but use the slob there. The app
follows slob links natively and reads the file without unpacking about 1 GB
into app storage.

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

The English dump is about 520 MB compressed. A full build of both formats takes
about 10 minutes.

| Command | What it does |
| --- | --- |
| `tinydict fetch [ids...]` | Downloads source data into `.cache/sources/<source>/` and records its ETag and dump dates |
| `tinydict fetch --metadata-only` | Refreshes metadata without downloading the data |
| `tinydict build [ids...]` | Builds each dictionary as StarDict, converts it to the other formats, checks every format, then writes release files and `manifest.json` to `dist/` |
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
formats = ["stardict", "slob"]     # optional; this is the default
```

Builders:

- **`wiktextract`**: one source. Uses PyGlossary's Wiktextract reader after
  removing junk inflection forms and fields the reader doesn't use.
- **`bilingual`**: translations from one source in `target_lang`, optionally
  combined with glosses from a Wiktionary edition written in the target
  language. Options are `target_lang`, `translations_source` and
  `glosses_source`.
- **`krdict`**: one `type = "krdict"` source. Each 한국어기초사전 sense comes
  with translations in 11 languages. `target_lang` picks the one to show
  (`"영어"`, `"일본어"`, `"중국어"`, `"프랑스어"`, `"스페인어"`, ...), so a Korean-Japanese
  dictionary is just another config entry.
- **`krdict-reverse`**: the same source turned around. The `target_lang`
  translation terms of each sense (`eat; have; consume`) become headwords
  listing the Korean entries that use them. Parenthesised context and long
  proverb paraphrases are left out. Results link to the Korean headword, so
  the matching `krdict` dictionary should be installed alongside.

Builders always produce StarDict. Other formats are converted from it with
PyGlossary's standard writers, so builders don't need format-specific code.

A build fails, and nothing is released, if any check fails in any format or the
entry count is below `min_entries`.

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
- **Dictionary data**:
  - Wiktionary dictionaries: written by Wiktionary contributors, licensed under
    [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) and the
    [GFDL](https://www.gnu.org/licenses/fdl-1.3.html).
  - 한국어기초사전: © 국립국어원, licensed under
    [CC BY-SA 2.0 KR](https://creativecommons.org/licenses/by-sa/2.0/kr/). Only
    text is used. NIKL's pronunciation audio, images and video have separate
    terms and are not included.

  Every released zip includes a `README.txt`, and every slob includes license
  tags and a description, with the source and license notice. If you share
  modified dictionaries, use the same license.
