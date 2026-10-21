"""Command line interface: tinydict fetch | build | release-tag."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
import time
from pathlib import Path

from . import glossary
from .builders import get_builder, make_context
from .config import Config, ConfigError, load_config
from .package import package, write_release_manifest
from .sources import fetch, load_meta
from .verify import verify

log = logging.getLogger("tinydict")


def _cmd_fetch(cfg: Config, args: argparse.Namespace) -> int:
    for source in cfg.sources_for(cfg.select(args.ids)):
        fetch(args.cache_dir, source, metadata_only=args.metadata_only)
    return 0


def _cmd_build(cfg: Config, args: argparse.Namespace) -> int:
    manifests = []
    failed = []
    for d in cfg.select(args.ids):
        t0 = time.monotonic()
        log.info("== %s (%s)", d.id, d.builder)
        ctx = make_context(cfg, d, args.cache_dir, args.build_dir)
        get_builder(d.builder)(ctx)
        result = verify(d, ctx.ifo_path)
        log.info("%s: %d entries, %d alternate keys", d.id, result.entries, result.synonyms)
        if not result.ok:
            for e in result.errors:
                log.error("%s: %s", d.id, e)
            failed.append(d.id)
            continue
        manifests.append(package(ctx, result, args.dist_dir))
        log.info("%s: done in %.0fs", d.id, time.monotonic() - t0)
    if manifests:
        path = write_release_manifest(args.dist_dir, manifests)
        log.info("wrote %s", path)
    if failed:
        log.error("verification failed: %s", ", ".join(failed))
        return 1
    return 0


def _cmd_release_tag(cfg: Config, args: argparse.Namespace) -> int:
    """Print a release tag derived from source data dates and the build config.

    The tag changes when any source is re-extracted, or when the dictionary
    config, the build code or the locked dependencies change, so CI can skip
    builds when the output would be the same.
    """
    dicts = cfg.select(args.ids)
    metas = [load_meta(args.cache_dir, s) for s in cfg.sources_for(dicts)]
    date = max((m.extracted or "0000-00-00") for m in metas)
    fingerprint = hashlib.sha256()
    for m in metas:
        fingerprint.update(f"{m.id}:{m.etag}:{m.size}\n".encode())
    inputs = [cfg.path, *sorted(Path(__file__).parent.rglob("*.py"))]
    lock = cfg.path.parent / "uv.lock"
    if lock.exists():
        inputs.append(lock)
    for path in inputs:
        # Normalize line endings so Windows checkouts produce the same tag.
        fingerprint.update(path.read_bytes().replace(b"\r\n", b"\n"))
    print(f"{date}-{fingerprint.hexdigest()[:8]}")
    return 0


def _cmd_release_notes(cfg: Config, args: argparse.Namespace) -> int:
    """Print Markdown release notes from dist/manifest.json."""
    manifest = json.loads((args.dist_dir / "manifest.json").read_text(encoding="utf-8"))
    lines = [
        "| Dictionary | Entries | Lookup keys | File | Size |",
        "| --- | ---: | ---: | --- | ---: |",
    ]
    sources: dict[str, dict] = {}
    for d in manifest["dictionaries"]:
        lines.append(
            f"| {d['name']} | {d['entries']:,} | {d['entries'] + d['synonyms']:,} "
            f"| `{d['asset']}` | {d['size'] / 1e6:.1f} MB |"
        )
        for s in d["sources"]:
            sources[s["id"]] = s
    lines += ["", "**Sources** (kaikki.org / Wiktextract)", ""]
    for s in sources.values():
        lines.append(f"- `{s['id']}`: {s['wiktionary']} dump {s['dump']}, extracted {s['extracted']}")
    lines += [
        "",
        "Each zip holds a StarDict dictionary folder. Unzip it into your dictionary app's folder "
        "(GoldenDict-ng, OSS-Dict, KOReader, ...). `manifest.json` lists SHA-256 checksums.",
        "",
        "Dictionary content: Wiktionary contributors, CC BY-SA 4.0 / GFDL.",
    ]
    print("\n".join(lines))
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tinydict", description=__doc__)
    p.add_argument("-c", "--config", type=Path, default=Path("dictionaries.toml"))
    p.add_argument("--cache-dir", type=Path, default=Path(".cache"))
    p.add_argument("--build-dir", type=Path, default=Path("build"))
    p.add_argument("--dist-dir", type=Path, default=Path("dist"))
    p.add_argument("-v", "--verbose", action="store_true", help="show PyGlossary logs")
    sub = p.add_subparsers(dest="command", required=True)
    for name, func, help_ in (
        ("fetch", _cmd_fetch, "download source data (skips unchanged files)"),
        ("build", _cmd_build, "build, verify and package dictionaries"),
        ("release-tag", _cmd_release_tag, "print the release tag for fetched sources"),
        ("release-notes", _cmd_release_notes, "print Markdown release notes for dist/"),
    ):
        s = sub.add_parser(name, help=help_)
        s.add_argument("ids", nargs="*", help="dictionary ids (default: all)")
        s.set_defaults(func=func)
        if name == "fetch":
            s.add_argument(
                "--metadata-only", action="store_true", help="only refresh meta.json (no download)"
            )
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    glossary.quiet(args.verbose)
    try:
        cfg = load_config(args.config)
        return args.func(cfg, args)
    except (ConfigError, FileNotFoundError, OSError) as e:
        log.error("%s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
