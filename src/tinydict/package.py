"""Package built dictionaries into release assets."""

from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import asdict
from pathlib import Path

from .builders import BuildContext
from .verify import VerifyResult

ATTRIBUTION = """\
{name}
{rule}

Built from Wiktionary data extracted by kaikki.org using Wiktextract.

Sources:
{sources}

License
-------
The dictionary content comes from Wiktionary and is available under the
Creative Commons Attribution-ShareAlike 4.0 International License (CC BY-SA 4.0)
and the GNU Free Documentation License (GFDL). If you redistribute or modify
this dictionary, keep this notice and share your changes under the same terms.

  https://creativecommons.org/licenses/by-sa/4.0/
  https://en.wiktionary.org/wiki/Wiktionary:Copyrights
  https://kaikki.org/

Build tooling: https://github.com/tinyrack-net/dictionary (GPL-3.0-or-later)
"""


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def package(ctx: BuildContext, result: VerifyResult, dist_dir: Path) -> dict:
    d = ctx.dictionary
    dist_dir.mkdir(parents=True, exist_ok=True)
    sources = "\n".join(
        f"- {m.url}\n  {m.wiktionary or 'Wiktionary'} dump {m.dump or '?'}, extracted {m.extracted or '?'}"
        for m in ctx.sources.values()
    )
    readme = ATTRIBUTION.format(name=ctx.bookname, rule="=" * len(ctx.bookname), sources=sources)

    zip_path = dist_dir / f"{d.id}-stardict.zip"
    files = sorted(p for p in ctx.output_dir.iterdir() if p.is_file())
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as z:
        for p in files:
            # .dict.dz is already compressed; deflate the rest.
            compress = zipfile.ZIP_STORED if p.suffix == ".dz" else zipfile.ZIP_DEFLATED
            z.write(p, f"{d.id}/{p.name}", compress_type=compress)
        z.writestr(f"{d.id}/README.txt", readme, compress_type=zipfile.ZIP_DEFLATED)

    manifest = {
        "id": d.id,
        "name": ctx.bookname,
        "format": "stardict",
        "entries": result.entries,
        "synonyms": result.synonyms,
        "data_date": ctx.data_date,
        "sources": [asdict(m) for m in ctx.sources.values()],
        "asset": zip_path.name,
        "size": zip_path.stat().st_size,
        "sha256": sha256(zip_path),
        "files": {p.name: {"size": p.stat().st_size, "sha256": sha256(p)} for p in files},
    }
    return manifest


def write_release_manifest(dist_dir: Path, manifests: list[dict]) -> Path:
    path = dist_dir / "manifest.json"
    path.write_text(
        json.dumps({"dictionaries": manifests}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return path
