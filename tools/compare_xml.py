"""Compare a decompiled JSON section against the XML produced by the old tool.

The original WinForms app wrote one XML document per section; those files are
the ground truth for the decoders.  The converter mirrors that layout, so a
section is just ``<json folder>/<Section>.json``.  This helper walks both sides
in document order and reports the first differences.

Usage:
    python tools/compare_xml.py json/ItemList PROGRAM/XML/ItemList/ItemList.xml --section ItemList
    python tools/compare_xml.py json/ItemList PROGRAM/XML/ItemList --scan
    python tools/compare_xml.py json/ExtraExchange PROGRAM/XML/ExtraExchange.xml \
        --section ExtraExchangeNPC --nested --alias Unknow=usMaterialType

``--alias OLD=NEW`` maps an XML element name (``OLD``) to the JSON key it was
renamed to (``NEW``), so a json schema that no longer mirrors the converter can
still be checked field by field.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import struct
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from binconv.cli import section_path  # noqa: E402
from binconv.formats import for_stem  # noqa: E402

#: ``{json key: xml element name}``; empty unless ``--alias`` is used.
EMPTY_ALIAS: Mapping[str, str] = {}


def parse_alias(values: list[str]) -> dict[str, str]:
    """Turn ``--alias XML=json`` pairs into the ``{json: xml}`` lookup."""

    alias: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise SystemExit(f"--alias expects OLD=NEW, got {value!r}")
        xml_name, json_name = (part.strip() for part in value.split("=", 1))
        if not xml_name or not json_name:
            raise SystemExit(f"--alias expects OLD=NEW, got {value!r}")
        alias[json_name] = xml_name
    return alias


@dataclass(frozen=True)
class Check:
    """One documented comparison: an XML document (or folder) and its section."""

    path: str
    section: str | None = None  # None: compare every XML document in the folder
    nested: bool = False
    ignore: frozenset[str] = frozenset()
    alias: Mapping[str, str] = field(default_factory=dict)
    exclude: frozenset[str] = frozenset()  # folder scan: document stems to skip
    folder: str | None = None  # json/<folder>, when the section lives elsewhere
    known: str = ""  # documented divergence: reported, not counted as a failure


#: The shipped data, checked against the documents the old tool produced.
#: ``ignore``/``alias`` only list divergences that are explained in the README:
#: ``alias`` renames a field the client named, ``ignore`` drops padding the old
#: exporter split into several elements (see ``reference/README.md``).
CHECKS: dict[str, tuple[Check, ...]] = {
    "Achieve": (
        Check(
            "PROGRAM/XML/Achieve.xml",
            "Achieve",
            ignore=frozenset({"s_szName", "s_szComment", "s_szTitle"}),
        ),
        Check("PROGRAM/XML/AchieveUnknow.xml", "AchieveUnknow"),
    ),
    "Buff": (
        Check("PROGRAM/XML/Buff/Buff.xml", "Buff", ignore=frozenset({"s_nConditionLv"})),
    ),
    # CashShop's reference XMLs are a 51-document flattening of the six JSON
    # sections (``AvatarInfo/Bottom/Bottom.xml`` ...), so they cannot be matched
    # by section name here; ``tools/verify_cashshop.py`` walks that tree.
    "DMBase": (
        Check(
            "reference/xml/DMBase/CsBaseMapInfo.xml",
            "CsBaseMapInfo",
            alias={"_pad1": "unk"},
            ignore=frozenset({"_pad0"}),
        ),
        Check(
            "reference/xml/DMBase/DigimonBaseInfo.xml",
            "DigimonBaseInfo",
            alias={"s_nAttack": "At", "_pad0": "Unknow1"},
            ignore=frozenset({"Ht", "Unknow2", "_pad1", "s_nHitRate"}),
        ),
        Check(
            "reference/xml/DMBase/DigimonEvoMaxSkill.xml",
            "DigimonEvoMaxSkill",
            ignore=frozenset({"nSubCount"}),
        ),
        Check(
            "reference/xml/DMBase/EvolutionBaseApply.xml",
            "EvolutionBaseApply",
            ignore=frozenset({"NameSize"}),
        ),
        Check("reference/xml/DMBase/ExpansionData.xml", "ExpansionData"),
        Check("reference/xml/DMBase/Guild.xml", "Guild"),
        Check(
            "reference/xml/DMBase/JumpBooster.xml",
            "JumpBooster",
            ignore=frozenset({"mapcount"}),
        ),
        Check("reference/xml/DMBase/Limit.xml", "Limit"),
        Check("reference/xml/DMBase/PaneltyInfo.xml", "PaneltyInfo"),
        Check("reference/xml/DMBase/Party.xml", "Party"),
        Check("reference/xml/DMBase/Store.xml", "Store"),
        Check(
            "reference/xml/DMBase/TamerBaseInfo.xml",
            "TamerBaseInfo",
            alias={"s_nAttack": "At", "_pad0": "Unknow1"},
            ignore=frozenset({"Ht", "Unknow2", "_pad1", "s_nHitRate"}),
        ),
    ),
    "Event": (
        Check("PROGRAM/XML/Event/AttendenceTime.xml", "AttendenceTime"),
        Check(
            "PROGRAM/XML/Event/Event.xml",
            "Event",
            nested=True,
            known=(
                "the exporter truncated 14 multi-line 'Name' values (it stopped at "
                "the first NUL); the JSON keeps the full text"
            ),
        ),
        Check("PROGRAM/XML/Event/Event100Days.xml", "Event100Days", nested=True),
        Check("PROGRAM/XML/Event/MensalEvent.xml", "MensalEvent", nested=True),
        Check("PROGRAM/XML/Event/MonthlyEvent.xml", "MonthlyEvent", nested=True),
        Check("PROGRAM/XML/Event/TimeEvent.xml", "TimeEvent", nested=True),
    ),
    "ExtraExchange": (
        Check(
            "PROGRAM/XML/ExtraExchange.xml",
            "ExtraExchangeNPC",
            nested=True,
            alias={"usMaterialType": "Unknow", "usWayType": "Unknow1"},
        ),
    ),
    "ItemExchange": (
        Check(
            "PROGRAM/XML/ItemList/ItemExchange.xml",
            "ItemExchange",
            folder="ItemList",
            ignore=frozenset({"unk1", "unk2"}),
            alias={"_pad0": "unk"},
        ),
    ),
    # ``ItemMaking`` is not compared: the exporter flattens the 10 recipe groups
    # into 1395 ``(m_dwItemIdx, m_nItemNum)`` rows, while the JSON keeps the
    # file's group + category map (see the known gaps in README.md).
    "ItemList": (
        Check(
            "PROGRAM/XML/ItemList/AcessorysEnchant.xml",
            "AcessorysEnchant",
            ignore=frozenset({"Factor1"}),
        ),
        Check("PROGRAM/XML/ItemList/ElementItem.xml", "ElementItem"),
        Check("PROGRAM/XML/ItemList/ElementItem1.xml", "ElementItem1"),
        Check(
            "PROGRAM/XML/ItemList/ItemAcessorys.xml",
            "ItemAcessorys",
            alias={"index": "Option"},
            ignore=frozenset({"Item"}),
        ),
        Check("PROGRAM/XML/ItemList/ItemCoolTime.xml", "ItemCoolTime"),
        Check("PROGRAM/XML/ItemList/ItemDisplay.xml", "ItemDisplay"),
        Check("PROGRAM/XML/ItemList/ItemList.xml", "ItemList"),
        Check("PROGRAM/XML/ItemList/ItemLook.xml", "ItemLook"),
        Check("PROGRAM/XML/ItemList/ItemMakingGroupList.xml", "ItemMakingGroupList"),
        Check("PROGRAM/XML/ItemList/ItemRank.xml", "ItemRank"),
        Check(
            "PROGRAM/XML/ItemList/ItemRankEffectList.xml",
            "ItemRankEffectList",
            alias={"index": "Item"},
            ignore=frozenset({"nIntervals"}),
        ),
        Check("PROGRAM/XML/ItemList/ItemTap.xml", "ItemTap"),
        Check("PROGRAM/XML/ItemList/ItemTypeName.xml", "ItemTypeName"),
        Check("PROGRAM/XML/ItemList/ItemXai.xml", "ItemXai"),
    ),
    "MapList": (Check("PROGRAM/XML/MapList.xml", "MapList"),),
    "MapNpc": (Check("PROGRAM/XML/MapNpc.xml", "MapNpc"),),
    "MapObject": (
        Check(
            "PROGRAM/XML/MapObject.xml",
            "MapObject",
            nested=True,
            ignore=frozenset({"Size", "FactorSize"}),
        ),
    ),
    "MapPortal": (
        Check(
            "PROGRAM/XML/MapPortal.xml",
            "MapPortal",
            nested=True,
            ignore=frozenset({"pMapGroup"}),
        ),
    ),
    "Quest": (Check("PROGRAM/XML/Quest.xml", "Quest"),),
    "Ride": (Check("PROGRAM/XML/Ride/Ride.xml", "Ride"),),
    "UIText": (Check("PROGRAM/XML/UIText.xml", "UIText"),),
    "WorldMap": (
        Check(
            "PROGRAM/XML/WorldMap.xml",
            "WorldMapInfo",
            ignore=frozenset({"s_szComment"}),
        ),
        Check(
            "PROGRAM/XML/AreaMap.xml",
            "AreaMapInfo",
            ignore=frozenset({"d_szComment"}),
        ),
    ),
}


def check_names() -> list[str]:
    return sorted(CHECKS)


def run_checks(root: Path, formats: list[str], limit: int = 10) -> int:
    """Run the documented checks for *formats* (``all`` for every entry)."""

    if "all" in formats:
        formats = check_names()
    missing = [name for name in formats if name not in CHECKS]
    if missing:
        print(f"no documented checks for {', '.join(missing)}")
        print(f"known: {', '.join(check_names())}")
        return 2

    failures = 0
    known_gaps = 0
    for name in formats:
        for check in CHECKS[name]:
            folder = root / "json" / (check.folder or name)
            target = root / check.path
            print(f"--- {name}: {check.path} ---")
            if check.section is None:
                failed = scan(
                    folder, target, limit, check.nested, check.ignore, check.alias,
                    check.exclude,
                )
            else:
                failed = compare(
                    folder, target, check.section, None, limit, check.nested,
                    check.ignore, check.alias,
                )
            if failed and check.known:
                known_gaps += 1
                print(f"  known gap: {check.known}")
            else:
                failures += failed
    print(
        f"{failures} difference(s) in {len(formats)} format(s), "
        f"{known_gaps} documented gap(s)"
    )
    return 1 if failures else 0


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


#: XML 1.0 cannot carry these characters at all (the old exporter dropped them).
XML_INVALID = "".join(chr(code) for code in range(0x20) if chr(code) not in "\t\n\r")


def _xml_lost_information(ours: str, xml: str) -> bool:
    """True when the only difference is information an XML document cannot hold.

    Two cases show up in the reference documents: C0 control characters the old
    exporter dropped (``\\x01`` inside a ``Buff`` comment) and trailing
    whitespace lost from the text node.
    """

    stripped = ours.translate({ord(char): None for char in XML_INVALID})
    return stripped.rstrip() == xml.rstrip()


def same_value(left: Any, right: str) -> bool:
    if isinstance(left, str):
        # XML parsers normalise CRLF *and* lone CR to LF; the binary keeps the
        # original bytes, so compare after the same normalisation.
        ours, theirs = _normalise(left), _normalise(right)
        if ours == theirs or _xml_lost_information(ours, theirs):
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


def looks_like_records(
    candidates: list[ET.Element], items: list[Any], alias: Mapping[str, str] = EMPTY_ALIAS
) -> bool:
    """True when the XML elements *are* the records, not a wrapper around them.

    Several exporters repeat the record element once per item
    (``<MapSourceObject>``, ``<MainNewItems><ProductID/></MainNewItems>``)
    instead of nesting them in a wrapper element such as ``<CashItems><Item/>``.
    A wrapper is recognised because its children are named after the record type
    while a record's children carry the record's own field names.
    """

    if not items or not all(isinstance(item, dict) for item in items):
        return False
    keys = {alias.get(key, key) for key in items[0]}
    return all({child.tag for child in candidate} & keys for candidate in candidates)


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
    alias: Mapping[str, str] = EMPTY_ALIAS,
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
                f"{prefix}{index}.", ignore, alias,
            )
        return

    if isinstance(value, dict):
        children: dict[str, list[ET.Element]] = {}
        for child in element:
            children.setdefault(child.tag, []).append(child)
        for name, item in value.items():
            if name in ignore:
                continue
            candidates = children.get(alias.get(name, name))
            if not candidates:
                # An empty list has nothing to compare and the exporter simply
                # omits the element, so it is not an "extra" field.
                if not (isinstance(item, list) and not item):
                    extra.add(prefix + name if prefix else name)
                continue
            if isinstance(item, list) and looks_like_records(candidates, item, alias):
                # The record element is repeated once per item instead of being
                # nested inside a wrapper element (see looks_like_records).
                if nested:
                    if len(candidates) != len(item):
                        problems.append(
                            f"{path}.{name}: {len(item)} item(s), XML has "
                            f"{len(candidates)}"
                        )
                    for index, (left, right) in enumerate(zip(item, candidates)):
                        compare_value(
                            left, right, f"{path}.{name}[{index}]", nested, problems,
                            missing, extra, f"{prefix}{name}[{index}].", ignore, alias,
                        )
                continue
            if isinstance(item, (list, dict)):
                if nested:
                    compare_value(
                        item, candidates[0], f"{path}.{name}", nested, problems,
                        missing, extra, f"{prefix}{name}.", ignore, alias,
                    )
                continue
            if item is None and len(candidates) == 1 and not (candidates[0].text or ""):
                continue
            texts = [candidate.text or "" for candidate in candidates]
            if any(same_value(item, text) for text in texts):
                continue
            problems.append(f"{path}.{name}: {item!r} != {texts[0]!r} (xml)")
        known = {alias.get(name, name) for name in value} | set(ignore)
        for name in sorted(set(children) - known):
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
    alias: Mapping[str, str] = EMPTY_ALIAS,
) -> int:
    """Compare one JSON section with the XML document the old tool produced.

    ``nested`` descends into JSON lists/dicts (``EventItems``, ``MensalItems``,
    ...), matching every item against the children of the same named element.
    ``ignore`` names fields that are *known* to differ from the XML because the
    original reader was wrong (see the codec docstrings).  ``alias`` maps a JSON
    key to the XML element name it is stored under in the original document.
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
            ignore=ignore, alias=alias,
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
    alias: Mapping[str, str] = EMPTY_ALIAS,
    exclude: frozenset[str] = frozenset(),
) -> int:
    """Compare every XML document in *xml_dir* with the same named section."""

    failures = 0
    for xml_path in sorted(xml_dir.rglob("*.xml")):
        if xml_path.stem in exclude:
            continue
        relative = xml_path.relative_to(xml_dir).with_suffix("").as_posix()
        section = relative if load_section(folder, relative) is not None else xml_path.stem
        value = load_section(folder, section)
        if value is None:
            # A document without a section would silently compare nothing, so it
            # counts as a failure: list the section explicitly in CHECKS instead.
            print(f"{section}: no JSON section (list it explicitly in CHECKS)")
            failures += 1
            continue
        if not isinstance(value, list):
            continue
        print(f"=== {section} ===")
        failures += compare(folder, xml_path, section, None, limit, nested, ignore, alias)
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    # The game data is UTF-16 Korean/Chinese; printing it to a cp1252 console
    # must not crash the comparison.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "json", nargs="?", type=Path, help="format folder (json/ItemList)"
    )
    parser.add_argument(
        "xml", nargs="?", type=Path, help="XML document or folder for --scan"
    )
    parser.add_argument("--section")
    parser.add_argument("--record", help="repeated XML element (default: from the codec)")
    parser.add_argument("--scan", action="store_true", help="compare every XML in the folder")
    parser.add_argument("--nested", action="store_true", help="also compare nested item lists")
    parser.add_argument(
        "--format",
        action="append",
        default=[],
        metavar="NAME",
        help="run the documented checks for NAME (repeatable, or 'all')",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root for --format (default: this checkout)",
    )
    parser.add_argument(
        "--ignore",
        default="",
        help="comma separated fields known to differ (old reader bugs)",
    )
    parser.add_argument(
        "--alias",
        action="append",
        default=[],
        metavar="OLD=NEW",
        help="XML element name OLD is stored as the JSON key NEW (repeatable)",
    )
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args(argv)

    if args.format:
        names = [part.strip() for value in args.format for part in value.split(",")]
        return run_checks(args.root, [name for name in names if name], args.limit)

    if args.json is None or args.xml is None:
        parser.error("json and xml are required unless --format is used")

    ignore = frozenset(name.strip() for name in args.ignore.split(",") if name.strip())
    alias = parse_alias(args.alias)

    if args.scan:
        return scan(args.json, args.xml, args.limit, args.nested, ignore, alias)

    if not args.section:
        parser.error("--section is required unless --scan is used")
    return compare(
        args.json, args.xml, args.section, args.record, args.limit, args.nested,
        ignore, alias,
    )


if __name__ == "__main__":
    sys.exit(main())
