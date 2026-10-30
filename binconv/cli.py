"""Command line interface for ``binconv.py``."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Iterator, Sequence

from . import __version__, formats
from .binary import FormatError
from .codec import compare_roundtrip

BIN_SUFFIXES = (".bin", ".dat")
DEFAULT_BIN_DIR = "bin"
DEFAULT_JSON_DIR = "json"
DEFAULT_OUT_DIR = "bin_out"


def _iter_files(root: Path, suffixes: Sequence[str], recursive: bool) -> Iterator[Path]:
    pattern = "**/*" if recursive else "*"
    for path in sorted(root.glob(pattern)):
        if path.is_file() and path.suffix.lower() in suffixes:
            yield path


def _human(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"


def _resolve_codecs(only: str | None) -> dict[str, Any] | None:
    """Map of selected codecs by name, or ``None`` when no filter was given."""

    if not only:
        return None
    selected: dict[str, Any] = {}
    for raw in only.split(","):
        name = raw.strip()
        if not name:
            continue
        codec = formats.by_name(name)
        if codec is None:
            matches = [c for c in formats.all_codecs() if c.name.lower() == name.lower()]
            codec = matches[0] if matches else None
        if codec is None:
            raise SystemExit(f"unknown format {name!r} (see: python binconv.py list-formats)")
        selected[codec.name] = codec
    return selected


def _write_json(target: Path, value: Any, compact: bool) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="\n") as handle:
        if compact:
            json.dump(value, handle, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(value, handle, ensure_ascii=False, indent="\t")
        handle.write("\n")


def section_path(name: str) -> Path:
    """Map a section name to its JSON file (``/`` separates sub folders)."""

    parts = [part for part in name.replace("\\", "/").split("/") if part]
    if not parts:
        raise FormatError(f"invalid section name {name!r}")
    return Path(*parts[:-1]) / f"{parts[-1]}.json"


def write_sections(folder: Path, sections: dict[str, Any], compact: bool) -> list[Path]:
    """Write one JSON file per section, mirroring the original XML layout."""

    written = []
    for name, value in sections.items():
        target = folder / section_path(name)
        _write_json(target, value, compact)
        written.append(target)
    return written


def read_sections(folder: Path, recursive: bool = True) -> dict[str, Any]:
    """Load every ``*.json`` below *folder* keyed by its relative path."""

    pattern = "**/*.json" if recursive else "*.json"
    sections: dict[str, Any] = {}
    for path in sorted(folder.glob(pattern)):
        if not path.is_file():
            continue
        key = path.relative_to(folder).with_suffix("").as_posix()
        with path.open("r", encoding="utf-8") as handle:
            sections[key] = json.load(handle)
    return sections


def _decompile_file(source: Path, folder: Path, codec, compact: bool) -> tuple[str, str]:
    data = source.read_bytes()
    sections = codec.decode(data, source.name)["sections"]
    written = write_sections(folder, sections, compact)

    reencoded = codec.encode(sections)
    status, differing = compare_roundtrip(data, reencoded)
    if status == "mismatch":
        return ("WARN", f"re-encoded output differs in {differing} byte(s) of {len(data)}")
    if codec.decode(reencoded, source.name)["sections"] != sections:
        return ("WARN", "re-encoded output does not decode back to the same data")

    detail = f"{_human(len(data))} -> {len(written)} file(s)"
    if status == "padding":
        detail += f", {differing} padding byte(s) normalised"
    else:
        detail += ", exact round-trip"
    return ("OK", detail)


def _compile_folder(folder: Path, target: Path, codec, recursive: bool) -> tuple[str, str]:
    sections = read_sections(folder, recursive)
    if not sections:
        raise FormatError(f"no .json files in {folder}")

    missing = [name for name in codec.sections if name not in sections]
    if missing:
        raise FormatError(f"missing section file(s): {', '.join(missing)}")
    unknown = sorted(set(sections) - set(codec.sections))

    data = codec.encode(sections)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)

    detail = f"{_human(len(data))}, {len(codec.sections)} section(s)"
    if unknown:
        detail += f", ignored {', '.join(unknown)}"
    return ("OK", detail)


def _run(args: argparse.Namespace) -> int:
    source_root = Path(args.src)
    out_root = Path(args.out)
    if not source_root.is_dir():
        raise SystemExit(f"--src directory not found: {source_root}")
    if source_root.resolve() == out_root.resolve():
        raise SystemExit("--src and --out must differ")

    selected = _resolve_codecs(args.only)
    if args.command == "decompile":
        units = _decompile_units(source_root, args.recursive)
        kind = "bin/dat"
    else:
        units = _compile_units(source_root)
        kind = "format folder"
    label_width = 34

    if not units:
        print(f"nothing to do: no {kind} found under {source_root}")
        return 0

    print(f"{args.command}: {len(units)} item(s) from {source_root} -> {out_root}")
    header = f"{'item':{label_width}} {'format':12} {'status':6} detail"
    print(header)
    print("-" * (len(header) + 24))

    counts = {"OK": 0, "WARN": 0, "SKIP": 0, "FAIL": 0}
    started = time.perf_counter()
    for label, codec, payload in units:
        if codec is None:
            counts["SKIP"] += 1
            print(f"{label:{label_width}} {'-':12} {'SKIP':6} unsupported format")
            continue
        if selected is not None and codec.name not in selected:
            counts["SKIP"] += 1
            print(f"{label:{label_width}} {codec.name:12} {'SKIP':6} filtered out by --only")
            continue

        try:
            if args.command == "decompile":
                source: Path = payload
                folder = out_root / source.relative_to(source_root).with_suffix("")
                if not args.overwrite and folder.is_dir() and any(folder.rglob("*.json")):
                    counts["SKIP"] += 1
                    print(
                        f"{label:{label_width}} {codec.name:12} {'SKIP':6} "
                        f"{folder} already has JSON (use --overwrite)"
                    )
                    continue
                status, detail = _decompile_file(source, folder, codec, args.compact)
            else:
                folder = payload
                target = out_root / codec.bin_name
                if target.exists() and not args.overwrite:
                    counts["SKIP"] += 1
                    print(
                        f"{label:{label_width}} {codec.name:12} {'SKIP':6} "
                        f"{target} exists (use --overwrite)"
                    )
                    continue
                status, detail = _compile_folder(folder, target, codec, True)
        except (FormatError, OSError, ValueError, KeyError) as error:
            counts["FAIL"] += 1
            print(f"{label:{label_width}} {codec.name:12} {'FAIL':6} {error}")
            continue

        counts[status] += 1
        print(f"{label:{label_width}} {codec.name:12} {status:6} {detail}")

    elapsed = time.perf_counter() - started
    total = (
        f"{counts['OK']} ok, {counts['WARN']} warning(s), "
        f"{counts['SKIP']} skipped, {counts['FAIL']} failed"
    )
    print("-" * (len(header) + 24))
    print(f"done in {elapsed:.1f}s: {total}")
    return 1 if counts["FAIL"] else 0


def _decompile_units(root: Path, recursive: bool) -> list[tuple[str, Any, Path]]:
    units = []
    for path in _iter_files(root, BIN_SUFFIXES, recursive):
        codec = formats.for_filename(path.name)
        units.append((str(path.relative_to(root)), codec, path))
    return units


def _compile_units(root: Path) -> list[tuple[str, Any, Path]]:
    """One unit per format folder below *root* (e.g. ``json/ItemList``)."""

    units = []
    for path in sorted(root.iterdir()):
        if not path.is_dir():
            continue
        units.append((path.name, formats.for_stem(path.name), path))
    for path in sorted(root.glob("*.json")):
        units.append((path.name, None, path))
    return units


def _add_common(parser: argparse.ArgumentParser, command: str) -> None:
    decompiling = command == "decompile"
    parser.add_argument(
        "--src",
        default=DEFAULT_BIN_DIR if decompiling else DEFAULT_JSON_DIR,
        help=(
            "input folder (searched recursively)"
            if decompiling
            else "input folder holding one sub folder per format (json/ItemList, ...)"
        ),
    )
    parser.add_argument(
        "--out",
        default=DEFAULT_JSON_DIR if decompiling else DEFAULT_OUT_DIR,
        help=(
            "output folder; every bin gets a sub folder with one .json per section"
            if decompiling
            else "output folder for the recompiled bins (created when missing)"
        ),
    )
    parser.add_argument("--only", help="comma separated list of formats, e.g. Buff,Ride")
    parser.add_argument(
        "--compact",
        action="store_true",
        help="write single line JSON instead of the default tab indented output",
    )
    parser.add_argument("--overwrite", action="store_true", help="replace existing output files")
    parser.add_argument(
        "--no-recursive",
        dest="recursive",
        action="store_false",
        help="decompile only: do not descend into sub folders of --src",
    )
    parser.set_defaults(recursive=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="binconv.py",
        description="Convert the game's binary tables to JSON and back.",
    )
    parser.add_argument("--version", action="version", version=f"binconv {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    decompile = sub.add_parser("decompile", help="bin/ -> json/")
    _add_common(decompile, "decompile")

    compile_ = sub.add_parser("compile", help="json/ -> bin_out/")
    _add_common(compile_, "compile")

    sub.add_parser("list-formats", help="list the supported formats")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "list-formats":
        return _list_formats()
    return _run(args)


def _list_formats() -> int:
    print(f"{'format':14} {'output':16} {'input file names':30} sections")
    print("-" * 84)
    for codec in formats.all_codecs():
        files = ", ".join(f"{name}.bin" for name in codec.filenames)
        print(f"{codec.name:14} {codec.bin_name:16} {files:30} {len(codec.sections)}")
    print(f"\n{len(list(formats.all_codecs()))} format(s) supported")
    return 0


