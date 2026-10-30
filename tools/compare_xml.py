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
import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from binconv.cli import section_path  # noqa: E402
from binconv.formats import for_stem  # noqa: E402


def load_section(folder: Path, section: str) -> Any | None:
    """Read ``<folder>/<section>.json`` (``None`` when the file is missing)."""

    path = folder / section_path(section)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def codec_record_tag(folder: Path, section: str) -> str | None:
    """Repeated XML element for *section*, as declared by its codec."""

    codec = for_stem(folder.name)
    return None if codec is None else codec.record_tags.get(section)


def xml_elements(path: Path, record: str) -> list[ET.Element]:
    """Every element holding one record (the root itself is never a record)."""

    root = ET.parse(path).getroot()
    return [element for element in root.iter(record) if element is not root]


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
    if isinstance(left, float):
        try:
            other = float(right.replace(",", "."))
        except ValueError:
            return False
        if other == left:
            return True
        # The C# exporters write `float.ToString()`, which keeps only as many
        # digits as the f32 needs; compare the f32 the text denotes.
        single = struct.unpack("<f", struct.pack("<f", left))[0]
        if single != left:
            return False
        return single == struct.unpack("<f", struct.pack("<f", other))[0]
    if isinstance(left, int):
        try:
            return float(right.replace(",", ".")) == float(left)
        except ValueError:
            return False
    return str(left) == right


def compare_value(
    value: Any,
    element: ET.Element,
    path: str,
    nested: bool,
    problems: list[str],
    missing: set[str],
    extra: set[str],
    prefix: str = "",
    ignore: frozenset[str] = frozenset(),
) -> None:
    """Compare one JSON value with the XML element holding it."""

    if isinstance(value, list):
        if not nested:
            return
        children = list(element)
        if len(children) != len(value):
            problems.append(f"{path}: {len(value)} item(s), XML has {len(children)}")
        for index, (left, right) in enumerate(zip(value, children)):
            compare_value(
                left, right, f"{path}[{index}]", nested, problems, missing, extra,
                f"{prefix}{index}.", ignore,
            )
        return

    if isinstance(value, dict):
        children: dict[str, list[ET.Element]] = {}
        for child in element:
            children.setdefault(child.tag, []).append(child)
        for name, item in value.items():
            if name in ignore:
                continue
            candidates = children.get(name)
            if not candidates:
                extra.add(prefix + name if prefix else name)
                continue
            if isinstance(item, list) and len(candidates) > 1:
                # A few exporters repeat the wrapper element once per record
                # (<MainNewItems><ProductID/></MainNewItems>) instead of nesting
                # every record inside one wrapper element.
                if nested:
                    if len(candidates) != len(item):
                        problems.append(
                            f"{path}.{name}: {len(item)} item(s), XML has "
                            f"{len(candidates)}"
                        )
                    for index, (left, right) in enumerate(zip(item, candidates)):
                        compare_value(
                            left, right, f"{path}.{name}[{index}]", nested, problems,
                            missing, extra, f"{prefix}{name}[{index}].", ignore,
                        )
                continue
            if isinstance(item, (list, dict)):
                if nested:
                    compare_value(
                        item, candidates[0], f"{path}.{name}", nested, problems,
                        missing, extra, f"{prefix}{name}.", ignore,
                    )
                continue
            if item is None and len(candidates) == 1 and not (candidates[0].text or ""):
                continue
            texts = [candidate.text or "" for candidate in candidates]
            if any(same_value(item, text) for text in texts):
                continue
            problems.append(f"{path}.{name}: {item!r} != {texts[0]!r} (xml)")
        for name in sorted(set(children) - set(value) - ignore):
            missing.add(prefix + name if prefix else name)
        return

    element_text = element.text or ""
    if not same_value(value, element_text):
        problems.append(f"{path}: {value!r} != {element_text!r} (xml)")


def compare(
    folder: Path,
    xml_path: Path,
    section: str,
    record: str | None = None,
    limit: int = 10,
    nested: bool = False,
    ignore: frozenset[str] = frozenset(),
) -> int:
    """Compare one JSON section with the XML document the old tool produced.

    ``nested`` descends into JSON lists/dicts (``EventItems``, ``MensalItems``,
    ...), matching every item against the children of the same named element.
    ``ignore`` names fields that are *known* to differ from the XML because the
    original reader was wrong (see the codec docstrings).
    """

    value = load_section(folder, section)
    if value is None:
        print(f"section {section!r} not found (missing {folder / section_path(section)})")
        return 2

    tag = record or codec_record_tag(folder, section) or detect_record_tag(xml_path)
    elements = xml_elements(xml_path, tag)
    print(f"{folder.name}[{section}]: {len(value)} record(s), {xml_path.name}: {len(elements)}")

    problems: list[str] = []
    missing: set[str] = set()
    extra: set[str] = set()
    if len(value) != len(elements):
        problems.append(f"record count differs ({len(value)} vs {len(elements)})")
    for index, (left, right) in enumerate(zip(value, elements)):
        compare_value(
            left, right, f"record {index}", nested, problems, missing, extra,
            ignore=ignore,
        )

    for message in problems[:limit]:
        print(f"  {message}")
    if len(problems) > limit:
        print(f"  ... {len(problems) - limit} more difference(s)")

    for name in sorted(missing):
        print(f"  in XML but not in JSON: {name}")
    for name in sorted(extra):
        print(f"  in JSON but not in XML: {name}")
    if problems:
        print(f"  {len(problems)} difference(s)")
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


def scan(
    folder: Path,
    xml_dir: Path,
    limit: int = 3,
    nested: bool = False,
    ignore: frozenset[str] = frozenset(),
) -> int:
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
        failures += compare(folder, xml_path, section, None, limit, nested, ignore)
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json", type=Path, help="format folder (json/ItemList)")
    parser.add_argument("xml", type=Path, help="XML document or folder for --scan")
    parser.add_argument("--section")
    parser.add_argument("--record", help="repeated XML element (default: from the codec)")
    parser.add_argument("--scan", action="store_true", help="compare every XML in the folder")
    parser.add_argument("--nested", action="store_true", help="also compare nested item lists")
    parser.add_argument(
        "--ignore",
        default="",
        help="comma separated fields known to differ (old reader bugs)",
    )
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args(argv)

    ignore = frozenset(name.strip() for name in args.ignore.split(",") if name.strip())

    if args.scan:
        return scan(args.json, args.xml, args.limit, args.nested, ignore)

    if not args.section:
        parser.error("--section is required unless --scan is used")
    return compare(
        args.json, args.xml, args.section, args.record, args.limit, args.nested, ignore
    )


if __name__ == "__main__":
    sys.exit(main())
