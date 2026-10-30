"""Compare ``json/CashShop`` with the XML documents the old tool produced.

``CashShop.bin`` is the first format whose XML output is *nested*: every shop
gets its own folder (``Main``, ``TamerInfo1``, ...) and each category list is a
separate document.  The JSON mirrors that structure as one list per document
kind -- ``TamerInfo.json`` holds one record per shop and its category lists
(``ExpansionItems``, ``ExpItems``, ...) are nested inside each record.

This helper walks the XML tree, maps every document to its JSON path and checks
the values with ``compare_xml.compare_value`` (so numbers, floats and CRLF
normalisation behave exactly like the flat comparisons).

Usage:
    python tools/verify_cashshop.py json/CashShop reference/xml/CashShop
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import compare_xml  # noqa: E402

from binconv.formats.cashshop import CashShopCodec  # noqa: E402

#: The codec declares which XML element holds one record of each section: the
#: document root for the shop documents, the repeated element for ``WebData``.
CODEC = CashShopCodec()

#: Document folder (without the shop index) -> JSON section.
SECTIONS = {
    "Main": "Main",
    "TamerInfo": "TamerInfo",
    "DigimonInfo": "DigimonInfo",
    "AvatarInfo": "AvatarInfo",
    "PackageInfo": "PackageInfo",
}

#: Category document stem -> list field of the shop document record.
LISTS = {
    "Expansion": "ExpansionItems",
    "Exp": "ExpItems",
    "Moviment": "MovimentItems",
    "Chat": "ChatItems",
    "Etc": "EtcItems",
    "DigiEgg": "DigiEgg",
    "Evolution": "EvolutionItems",
    "Hatch": "HatchItems",
    "Reinforced": "ReinforcedItems",
    "Riding": "RidingItems",
    "Head": "HeadItems",
    "Top": "TopItems",
    "Bottom": "BottomItems",
    "Gloves": "GlovesItems",
    "Shoes": "ShoesItems",
    "Fashion": "FashionItems",
    "Costume": "CostumeItems",
    "PackageItems": "PackageItems",
}

#: Fields the old XML export wrote from `CASHINFO` members the reader never
#: fills (or from derived values), so they are empty / absent in the file.
EXPECTED_XML_ONLY = {
    "bActive",
    "cashshop_id",
    "CashName",
    "CategoryNameSize",
    "Desc",
    "dwProductID",
    "m_mapWebData",
    "packageItems",
    "PackageName",
    "szEndTime",
    "szStartTime",
    "UnknowItemsTitle",
    # The category lists live in their own documents, so they never appear
    # inside the shop document itself.
    *LISTS.values(),
}

#: ``WebData`` lists ``CashWebDataInfo`` records; the original class calls the
#: member ``CashWebInfo`` while the exporter uses the type name as element.
WEB_INFO_FIELD = "CashWebInfo"
WEB_INFO_TAG = "CashWebDataInfo"


def split_folder(name: str) -> tuple[str, int]:
    """``TamerInfo1`` -> ``("TamerInfo", 1)``, ``Main`` -> ``("Main", 0)``."""

    digits = ""
    while name and name[-1].isdigit():
        digits = name[-1] + digits
        name = name[:-1]
    return name, int(digits) if digits else 0


def report(label: str, problems: list[str], missing: set[str], extra: set[str]) -> bool:
    """Print one document's result; returns ``False`` when it differs."""

    unexpected = unexpected_fields(missing, extra)
    ok = not problems and not unexpected
    print(f"{label}: {'OK' if ok else 'DIFF'}")
    for message in problems[:5]:
        print(f"  {message}")
    if len(problems) > 5:
        print(f"  ... {len(problems) - 5} more difference(s)")
    for name in sorted(unexpected):
        print(f"  unexpected field: {name}")
    return ok


def unexpected_fields(missing: set[str], extra: set[str]) -> set[str]:
    """Fields that differ but are not one of the known empty ones."""

    return {
        name
        for name in missing | extra
        if name.split("[")[0].split(".")[-1] not in EXPECTED_XML_ONLY
    }


def compare_document(
    value: Any, element: ET.Element, label: str
) -> tuple[list[str], set[str], set[str]]:
    """Compare a whole XML document with one JSON record."""

    problems: list[str] = []
    missing: set[str] = set()
    extra: set[str] = set()
    compare_xml.compare_value(value, element, label, True, problems, missing, extra)
    return problems, missing, extra


def compare_list(
    values: list[Any], elements: list[ET.Element], label: str
) -> tuple[list[str], set[str], set[str]]:
    """Compare a list of JSON records with repeated XML elements."""

    problems: list[str] = []
    missing: set[str] = set()
    extra: set[str] = set()
    if len(elements) != len(values):
        problems.append(f"{len(values)} item(s), XML has {len(elements)}")
    for position, (left, right) in enumerate(zip(values, elements)):
        compare_xml.compare_value(
            left, right, f"{label}[{position}]", True, problems, missing, extra
        )
    return problems, missing, extra


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json", type=Path, help="format folder (json/CashShop)")
    parser.add_argument("xml_dir", type=Path, help="XML tree (reference/xml/CashShop)")
    parser.add_argument(
        "--verbose", action="store_true", help="print one line per document"
    )
    args = parser.parse_args(argv)

    sections: dict[str, Any] = {}
    for name in CashShopCodec().sections:
        value = compare_xml.load_section(args.json, name)
        if value is None:
            print(f"missing section {name!r} below {args.json}")
            return 2
        sections[name] = value

    totals: dict[str, list[int]] = {}
    failures = 0
    for path in sorted(args.xml_dir.rglob("*.xml")):
        parts = path.relative_to(args.xml_dir).parts
        if parts[0] == "WebData":
            # A single document holding every banner table.  The exporter names
            # the banner elements after the *type* (CashWebDataInfo) while the
            # class calls the list CashWebInfo, so the key is renamed for the
            # comparison.
            banners = [
                {
                    (WEB_INFO_TAG if key == WEB_INFO_FIELD else key): value
                    for key, value in record.items()
                }
                for record in sections["WebData"]
            ]
            problems, missing, extra = compare_list(
                banners,
                compare_xml.xml_elements(path, CODEC.record_tags["WebData"]),
                "WebData",
            )
            kind = "WebData"
        else:
            kind, index = split_folder(parts[0])
            section = SECTIONS.get(kind)
            if section is None:
                print(f"{path}: unknown document folder {parts[0]!r}")
                failures += 1
                continue
            records = sections[section]
            if index >= len(records):
                print(f"{path}: no {section} record {index}")
                failures += 1
                continue
            kind = section
            root = ET.parse(path).getroot()
            if path.stem.startswith("CashShop"):
                # The record of a shop document is the document itself, so the
                # codec's tag has to be the root element name.
                expected = CODEC.record_tags[section]
                if root.tag != expected:
                    print(f"{path}: root element is {root.tag!r}, expected {expected!r}")
                    failures += 1
                    continue
                problems, missing, extra = compare_document(
                    records[index], root, f"{section}[{index}]"
                )
            else:
                field = LISTS.get(path.stem)
                if field is None or field not in records[index]:
                    print(f"{path}: no JSON list for document {path.stem!r}")
                    failures += 1
                    continue
                problems, missing, extra = compare_list(
                    records[index][field], list(root), f"{section}[{index}].{field}"
                )

        bucket = totals.setdefault(kind, [0, 0, 0])
        bucket[0] += 1
        if problems or unexpected_fields(missing, extra):
            bucket[1] += 1
            failures += 1
            report(f"{kind}: {path.relative_to(args.xml_dir).as_posix()}",
                   problems, missing, extra)
        else:
            bucket[2] += 1
            if args.verbose:
                report(f"{kind}: {path.relative_to(args.xml_dir).as_posix()}",
                       problems, missing, extra)

    print(f"{'document':14} {'checked':>8} {'diff':>6} {'ok':>6}")
    for kind, (checked, bad, good) in totals.items():
        print(f"{kind:14} {checked:8} {bad:6} {good:6}")
    print(f"\n{sum(v[0] for v in totals.values())} document(s), {failures} with differences")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
