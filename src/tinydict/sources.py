"""Download source datasets (kaikki.org, 한국어기초사전) and record their metadata."""

from __future__ import annotations

import gzip
import json
import logging
import re
import shutil
import urllib.request
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .config import KRDICT_BASE, Source

log = logging.getLogger(__name__)

USER_AGENT = "tinydict (+https://github.com/tinyrack-net/dictionary)"
_EXTRACTED_RE = re.compile(r"extracted on (\d{4}-\d{2}-\d{2}) from the (\w+) dump dated (\d{4}-\d{2}-\d{2})")
# e.g. attachment;filename=전체 내려받기_한국어기초사전_json_20261019.zip
_KRDICT_DATE_RE = re.compile(r"_(\d{4})(\d{2})(\d{2})\.zip")


@dataclass
class SourceMeta:
    id: str
    url: str
    size: int
    etag: str | None
    last_modified: str | None
    extracted: str | None = None
    wiktionary: str | None = None
    dump: str | None = None

    @property
    def is_krdict(self) -> bool:
        return self.url.startswith(KRDICT_BASE)

    def credit(self) -> str:
        """One-line attribution for this source."""
        if self.is_krdict:
            return f"한국어기초사전 (National Institute of Korean Language), released {self.extracted or '?'}"
        return (
            f"{self.wiktionary or 'Wiktionary'} dump {self.dump or '?'}, "
            f"extracted {self.extracted or '?'} by kaikki.org/Wiktextract"
        )

    @property
    def license(self) -> str:
        return "CC BY-SA 2.0 KR" if self.is_krdict else "CC BY-SA 4.0 / GFDL"


def _request(url: str, method: str = "GET") -> urllib.request.Request:
    return urllib.request.Request(url, method=method, headers={"User-Agent": USER_AGENT})


def parse_page_dates(html: str) -> dict[str, str | None]:
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    m = _EXTRACTED_RE.search(text)
    if not m:
        return {"extracted": None, "wiktionary": None, "dump": None}
    return {"extracted": m.group(1), "wiktionary": m.group(2), "dump": m.group(3)}


def parse_krdict_date(content_disposition: str | None) -> str | None:
    """Release date from the krdict download's file name (header is UTF-8 bytes)."""
    if not content_disposition:
        return None
    # The date is ASCII, so it survives however urllib decoded the UTF-8 file name.
    m = _KRDICT_DATE_RE.search(content_disposition)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def source_dir(cache_dir: Path, source: Source) -> Path:
    return cache_dir / "sources" / source.id


def data_path(cache_dir: Path, source: Source) -> Path:
    return source_dir(cache_dir, source) / source.data_name


def load_meta(cache_dir: Path, source: Source) -> SourceMeta:
    path = source_dir(cache_dir, source) / "meta.json"
    if not path.exists():
        raise FileNotFoundError(f"source {source.id!r} not fetched; run `tinydict fetch` first")
    return SourceMeta(**json.loads(path.read_text(encoding="utf-8")))


def fetch(cache_dir: Path, source: Source, metadata_only: bool = False) -> SourceMeta:
    """Record remote metadata and download the data unless the cached copy matches.

    ``meta.json`` always describes the remote file. ``data.etag`` records which
    remote version ``data.jsonl.gz`` holds, so a metadata-only refresh never
    makes stale data look current.
    """
    folder = source_dir(cache_dir, source)
    folder.mkdir(parents=True, exist_ok=True)
    data = data_path(cache_dir, source)
    meta_path = folder / "meta.json"
    data_etag = folder / "data.etag"

    with urllib.request.urlopen(_request(source.data_url, "HEAD"), timeout=60) as r:
        size = int(r.headers["Content-Length"])
        etag = r.headers.get("ETag")
        last_modified = r.headers.get("Last-Modified")
        disposition = r.headers.get("Content-Disposition")

    if source.type == "krdict":
        released = parse_krdict_date(disposition)
        if released is None:
            raise OSError(f"{source.id}: cannot read release date from {disposition!r}")
        # No ETag is published; the release date identifies the version.
        etag = etag or f"krdict-{released}"
        dates = {"extracted": released, "wiktionary": None, "dump": released}
    else:
        with urllib.request.urlopen(_request(source.page_url), timeout=60) as r:
            dates = parse_page_dates(r.read().decode("utf-8", errors="replace"))

    meta = SourceMeta(
        id=source.id,
        url=source.data_url,
        size=size,
        etag=etag,
        last_modified=last_modified,
        **dates,
    )

    meta_path.write_text(json.dumps(asdict(meta), indent=2), encoding="utf-8")
    if metadata_only:
        log.info("%s: remote extracted %s, %.1f MB", source.id, meta.extracted, size / 1e6)
        return meta

    if (
        data.exists()
        and data_etag.exists()
        and data_etag.read_text(encoding="utf-8") == (etag or "")
        and data.stat().st_size == size
    ):
        log.info("%s: up to date (%s)", source.id, meta.extracted)
        return meta

    data_etag.unlink(missing_ok=True)
    log.info("%s: downloading %s (%.1f MB)", source.id, source.data_url, size / 1e6)
    tmp = data.with_suffix(".part")
    with urllib.request.urlopen(_request(source.data_url), timeout=60) as r, tmp.open("wb") as f:
        shutil.copyfileobj(r, f, length=1 << 20)
    if tmp.stat().st_size != size:
        raise OSError(f"{source.id}: size mismatch {tmp.stat().st_size} != {size}")
    tmp.replace(data)
    data_etag.write_text(etag or "", encoding="utf-8")
    log.info("%s: done (extracted %s, dump %s)", source.id, meta.extracted, meta.dump)
    return meta


def iter_entries(path: Path) -> Iterator[dict[str, Any]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def iter_lines(path: Path) -> Iterator[str]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as f:
        yield from f
