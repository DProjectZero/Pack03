"""Compare every flat section of a JSON folder with its original XML file.

A thin wrapper around ``compare_xml`` that walks an XML folder, skips the
sections you are not interested in and prints a summary.

Usage:
    python tools/verify_sections.py json/ItemList PROGRAM/XML/ItemList \
        --skip ServerItemList
"""

from __future__ import annotations

import argparse
import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import compare_xml  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json", type=Path, help="format folder (json/ItemList)")
    parser.add_argument("xml_dir", type=Path)
    parser.add_argument("--skip", default="", help="comma separated section names to skip")
    parser.add_argument("--limit", type=int, default=2)
    args = parser.parse_args(argv)

    skip = {name.strip() for name in args.skip.split(",") if name.strip()}

    failures = 0
    for xml_path in sorted(args.xml_dir.rglob("*.xml")):
        relative = xml_path.relative_to(args.xml_dir).with_suffix("").as_posix()
        section = relative
        if compare_xml.load_section(args.json, relative) is None:
            section = xml_path.stem
        if section in skip:
            continue
        value = compare_xml.load_section(args.json, section)
        if value is None:
            print(f"{section}: no such section (skipped)")
            continue
        if not isinstance(value, list):
            print(f"{section}: nested section (skipped)")
            continue
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            result = compare_xml.compare(
                args.json, xml_path, section, compare_xml.detect_record_tag(xml_path), args.limit
            )
        failures += result
        print(f"=== {section} === {'OK' if result == 0 else 'DIFF'}")
        if result:
            print(buffer.getvalue().rstrip())

    print(f"\n{failures} section(s) with differences")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
