"""Compare a decompiled JSON section against the XML produced by the old tool.

The original WinForms app wrote one XML document per section; those files are
the ground truth for the decoders.  The converter mirrors that layout, so a
section is just ``<json folder>/<Section>.json``.  This helper walks both sides
in document order and reports the first differences.

Usage:
    python tools/compare_xml.py json/ItemList PROGRAM/XML/ItemList/ItemList.xml --section ItemList
    python tools/compare_xml.py json/ItemList PROGRAM/XML/ItemList --scan
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from binconv.cli import section_path  # noqa: E402


def load_section(folder: Path, section: str) -> Any | None:
    """Read ``<folder>/<section>.json`` (``None`` when the file is missing)."""

    path = folder / section_path(section)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def xml_records(path: Path, record: str) -> list[dict[str, list[str]]]:
    """Collect every record's child elements as ``name -> [values]``.

    Some names repeat inside one record (the original tool reused tags such as
    ``unk``), so each name maps to the list of values it occurred with.
    """

    root = ET.parse(path).getroot()
    records = []
    for element in root.iter(record):
        values: dict[str, list[str]] = {}
        for child in element:
            values.setdefault(child.tag, []).append(child.text or "")
        records.append(values)
    return records


def json_records(section: Any) -> list[dict[str, Any]]:
    records = []
    for item in section:
        records.append(dict(item))
    return records


def _normalise(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def same_value(left: Any, right: str) -> bool:
    if isinstance(left, str):
        # XML parsers normalise CRLF *and* lone CR to LF; the binary keeps the
        # original bytes, so compare after the same normalisation.
        if _normalise(left) == _normalise(right):
            return True
        # Raw byte fields are base64 in JSON and hex in the original XML.
        try:
            blob = base64.b64decode(left, validate=True)
        except (binascii.Error, ValueError):
            return False
        try:
            return bytes.fromhex(right) == blob
        except ValueError:
            return False
    if isinstance(left, bool):
        return str(left).lower() == right.lower()
    if isinstance(left, (int, float)):
        try:
            return float(right.replace(",", ".")) == float(left)
        except ValueError:
            return False
    return str(left) == right


def compare(
    folder: Path, xml_path: Path, section: str, record: str, limit: int = 10
) -> int:
    value = load_section(folder, section)
    if value is None:
        print(f"section {section!r} not found (missing {folder / section_path(section)})")
        return 2

    ours = json_records(value)
    theirs = xml_records(xml_path, record)
    print(f"{folder.name}[{section}]: {len(ours)} record(s), {xml_path.name}: {len(theirs)}")
    if len(ours) != len(theirs):
        print("  record count differs")
        return 1

    problems = 0
    missing_names: set[str] = set()
    extra_names: set[str] = set()
    for index, (left, right) in enumerate(zip(ours, theirs)):
        for name, candidates in right.items():
            if name not in left:
                missing_names.add(name)
        for name in left:
            if name not in right:
                extra_names.add(name)
        for name, value in left.items():
            if isinstance(value, (list, dict)):
                continue
            candidates = right.get(name)
            if candidates is None:
                continue
            if value is None and candidates and not candidates[0]:
                continue
            if any(same_value(value, candidate) for candidate in candidates):
                continue
            problems += 1
            if problems <= limit:
                print(
                    f"  record {index} field {name}: {value!r} != "
                    f"{candidates[0]!r} (xml)"
                )
            break

    for name in sorted(missing_names):
        print(f"  in XML but not in JSON: {name}")
    for name in sorted(extra_names):
        print(f"  in JSON but not in XML: {name}")
    if problems:
        print(f"  {problems} record(s) differ")
        return 1
    print("  all values match")
    return 0


def detect_record_tag(path: Path) -> str:
    """Guess the repeated record element of an XML document."""

    root = ET.parse(path).getroot()
    counts: dict[str, int] = {}
    for element in root.iter():
        if len(element):
            counts[element.tag] = counts.get(element.tag, 0) + 1
    if counts:
        return max(counts, key=counts.get)
    children = [child.tag for child in root]
    return max(set(children), key=children.count)


def scan(folder: Path, xml_dir: Path, limit: int = 3) -> int:
    """Compare every XML document in *xml_dir* with the same named section."""

    failures = 0
    for xml_path in sorted(xml_dir.rglob("*.xml")):
        relative = xml_path.relative_to(xml_dir).with_suffix("").as_posix()
        section = relative if load_section(folder, relative) is not None else xml_path.stem
        value = load_section(folder, section)
        if value is None:
            print(f"{section}: no such section (skipped)")
            continue
        if not isinstance(value, list):
            continue
        print(f"=== {section} ===")
        failures += compare(
            folder, xml_path, section, detect_record_tag(xml_path), limit
        )
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json", type=Path, help="format folder (json/ItemList)")
    parser.add_argument("xml", type=Path, help="XML document or folder for --scan")
    parser.add_argument("--section")
    parser.add_argument("--record")
    parser.add_argument("--scan", action="store_true", help="compare every XML in the folder")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args(argv)

    if args.scan:
        return scan(args.json, args.xml, args.limit)

    if not args.section:
        parser.error("--section is required unless --scan is used")
    record = args.record or detect_record_tag(args.xml)
    return compare(args.json, args.xml, args.section, record, args.limit)


if __name__ == "__main__":
    sys.exit(main())
