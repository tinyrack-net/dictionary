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

Sources:
{sources}

License
-------
{licenses}
If you redistribute or modify this dictionary, keep this notice and share your
changes under the same terms.

Build tooling: https://github.com/tinyrack-net/dictionary (GPL-3.0-or-later)
"""

WIKTIONARY_LICENSE = """\
Wiktionary content is available under the Creative Commons
Attribution-ShareAlike 4.0 International License (CC BY-SA 4.0) and the GNU
Free Documentation License (GFDL). Data extracted by kaikki.org (Wiktextract).
  https://creativecommons.org/licenses/by-sa/4.0/
  https://en.wiktionary.org/wiki/Wiktionary:Copyrights
  https://kaikki.org/
"""

KRDICT_LICENSE = """\
한국어기초사전 (Basic Korean Dictionary) © 국립국어원 (National Institute of
Korean Language), licensed under Creative Commons Attribution-ShareAlike 2.0
Korea (CC BY-SA 2.0 KR). Multimedia (pronunciation audio, images, video) is not
included.
  https://krdict.korean.go.kr/
  https://creativecommons.org/licenses/by-sa/2.0/kr/
"""


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def attribution(ctx: BuildContext) -> str:
    metas = list(ctx.sources.values())
    sources = "\n".join(f"- {m.url}\n  {m.credit()}" for m in metas)
    licenses = []
    if any(not m.is_krdict for m in metas):
        licenses.append(WIKTIONARY_LICENSE)
    if any(m.is_krdict for m in metas):
        licenses.append(KRDICT_LICENSE)
    return ATTRIBUTION.format(
        name=ctx.bookname, rule="=" * len(ctx.bookname), sources=sources, licenses="\n".join(licenses)
    )


def _zip_dir(ctx: BuildContext, format_id: str, zip_path: Path) -> list[Path]:
    """Zip a format's output folder as ``<id>/...`` together with README.txt."""
    d = ctx.dictionary
    files = sorted(p for p in ctx.format_dir(format_id).iterdir() if p.is_file())
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as z:
        for p in files:
            # .dict.dz and .slob are already compressed; deflate the rest.
            compress = zipfile.ZIP_STORED if p.suffix in {".dz", ".slob"} else zipfile.ZIP_DEFLATED
            z.write(p, f"{d.id}/{p.name}", compress_type=compress)
        z.writestr(f"{d.id}/README.txt", attribution(ctx), compress_type=zipfile.ZIP_DEFLATED)
    return files


def package(ctx: BuildContext, format_id: str, result: VerifyResult, dist_dir: Path) -> dict:
    """Write the release asset for one format and return its manifest entry.

    StarDict is a folder of files, so it ships as a zip. A slob is a single
    self-describing file that apps open directly, so it ships as is. Its name
    has no date, so the slob ``uri`` tag (derived from the file name) stays
    stable and apps keep bookmarks and history across updates.
    """
    d = ctx.dictionary
    dist_dir.mkdir(parents=True, exist_ok=True)

    if format_id == "slob":
        asset = dist_dir / f"{d.id}.slob"
        asset.write_bytes(ctx.output_path("slob").read_bytes())
        files = [ctx.output_path("slob")]
    else:
        asset = dist_dir / f"{d.id}-{format_id}.zip"
        files = _zip_dir(ctx, format_id, asset)

    return {
        "id": d.id,
        "name": ctx.bookname,
        "format": format_id,
        "entries": result.entries,
        "synonyms": result.synonyms,
        "data_date": ctx.data_date,
        "sources": [asdict(m) for m in ctx.sources.values()],
        "asset": asset.name,
        "size": asset.stat().st_size,
        "sha256": sha256(asset),
        "files": {p.name: {"size": p.stat().st_size, "sha256": sha256(p)} for p in files},
    }


def write_release_manifest(dist_dir: Path, manifests: list[dict]) -> Path:
    path = dist_dir / "manifest.json"
    path.write_text(
        json.dumps({"dictionaries": manifests}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return path
