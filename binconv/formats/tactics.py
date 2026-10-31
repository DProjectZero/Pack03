"""``Tactics.bin`` -- the tactics ("Data") enhancement tables.

Layout from the client, ``TacticsMng.cpp::_LoadBin`` (lines 750-986) plus
``Tactics.h`` / ``TacticsExplain.h`` / ``TacticsEnchant.h`` / ``TacticsTranscend.h``.
Nine sections::

    1) Tactics                 int32 nCount; per row: DWORD key + CsTactics::sINFO
        int   s_nDigimonID
        int   s_nReqItemS_Type[DATA_MAX]      DATA_MAX is 2 in this build
        USHORT s_nReqItemCount[DATA_MAX]      (DATA_LV1 + DATA_LV2)
        BYTE  s_nLimitLevel[DATA_MAX]
        BYTE  s_nViewWarning[DATA_MAX]
        -> 20-byte record, 24 bytes including the key

    2) TacticsExplain          DWORD key + CsTacticsExplain::sINFO
        DWORD s_dwTacticsMonID
        TCHAR s_szTacticsName[64]
        TCHAR s_szTacticsExplain[512]

    3) EnchantItem             DWORD dwItemCode, int nLowLevel, int nHighLevel,
                               DWORD dwNeedMoney
    4) EnchantStat             int key + int32 nSub; per sub: 7 ints
                               (nLowEnchantLv, nHighEnchantLv, nDigimonGrowMinLv,
                                nDigimonGrowMaxLv, nNormalEnchantMinValue,
                                nNormalEnchantMaxValue, nSpecialEnchantValue)
    5) (unnamed)               one int: nEnchentDefaultCorrect
    6) SameTypeCorrect         int key + int32 nSub; per sub: int growth, float value
    7) TransInfo               int key + int32 nSub; per sub: int currentGrowth,
                               8 ints (need digimon lv, enchant lv, evo min/max type,
                               scale, next growth, hatch lv min/max),
                               DWORD transCost, DWORD maxExp
    8) TransEvo                DWORD digimon + int32 nTypes; per type: int useType +
                               int32 nMaterials; per material: int needCount,
                               DWORD itemType, DWORD minExp
    9) ExpDigimon              DWORD digimon + int32 nSub; per sub: int growth,
                               DWORD fixedFigure

The shipped 228 264-byte file holds 2 422 tactics rows, 140 explanations, 26
enchant items, 5 enchant stat groups, 6 same-type groups, transcend and exp rows
as stored; it decodes exactly to EOF.
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, field, read_records, write_records
from ..fields import read_fields, write_fields

DATA_MAX = 2  # CsTactics::DATA_GRADE_FLAG with TACTICS_USE_DATA_LV1 + LV2

TACTICS_FIELDS = [("s_nDigimonID", "i32")]

EXPLAIN_FIELDS = [
    ("s_dwTacticsMonID", "u32"),
    ("s_szTacticsName", ("w", 64)),
    ("s_szTacticsExplain", ("w", 512)),
]

ENCHANT_ITEM_FIELDS = [
    ("dwItemCode", "u32"),
    ("nLowLevel", "i32"),
    ("nHighLevel", "i32"),
    ("dwNeedMoney", "u32"),
]

ENCHANT_STAT_FIELDS = [
    ("nLowEnchantLv", "i32"),
    ("nHighEnchantLv", "i32"),
    ("nDigimonGrowMinLv", "i32"),
    ("nDigimonGrowMaxLv", "i32"),
    ("nNormalEnchantMinValue", "i32"),
    ("nNormalEnchantMaxValue", "i32"),
    ("nSpecialEnchantValue", "i32"),
]

TRANS_INFO_FIELDS = [
    ("nNeedDigimonLv", "i32"),
    ("nNeedEnchantLv", "i32"),
    ("nNeedEvoMinType", "i32"),
    ("nNeedEvoMaxType", "i32"),
    ("nNeedScale", "i32"),
    ("nNextDigimonGrowth", "i32"),
    ("nNeedHatchLvMin", "i32"),
    ("nNeedHatchLvMax", "i32"),
    ("dwTransCost", "u32"),
    ("dwMaxExp", "u32"),
]

TRANSCEND_MATERIAL_FIELDS = [
    ("nNeedCount", "i32"),
    ("dwItemType", "u32"),
    ("dwMinExp", "u32"),
]


def _read_count(reader: Reader, label: str) -> int:
    count = reader.i32()
    if count < 0 or count > (len(reader.data) - reader.pos):
        raise FormatError(
            f"{reader.name}: implausible {label} count {count} at offset {reader.pos - 4}"
        )
    return count


def _write_count(writer: Writer, rows: Any, label: str) -> None:
    if not isinstance(rows, list):
        raise FormatError(f"Tactics: {label!r} must be a list")
    writer.i32(len(rows))


def _read_tactics(reader: Reader) -> dict[str, Any]:
    record = {"dwID": reader.u32()}
    record.update(read_fields(reader, TACTICS_FIELDS))
    record["s_nReqItemS_Type"] = [reader.i32() for _ in range(DATA_MAX)]
    record["s_nReqItemCount"] = [reader.u16() for _ in range(DATA_MAX)]
    record["s_nLimitLevel"] = [reader.u8() for _ in range(DATA_MAX)]
    record["s_nViewWarning"] = [reader.u8() for _ in range(DATA_MAX)]
    return record


def _write_tactics(writer: Writer, record: dict[str, Any]) -> None:
    where = "Tactics"
    writer.u32(field(record, "dwID", where))
    write_fields(writer, TACTICS_FIELDS, record)
    for name, write_one in (
        ("s_nReqItemS_Type", writer.i32),
        ("s_nReqItemCount", writer.u16),
        ("s_nLimitLevel", writer.u8),
        ("s_nViewWarning", writer.u8),
    ):
        values = record.get(name)
        if not isinstance(values, list) or len(values) != DATA_MAX:
            raise FormatError(f"{where}: {name!r} must be a list of {DATA_MAX}")
        for value in values:
            write_one(value)


def _read_explain(reader: Reader) -> dict[str, Any]:
    explain = {"dwID": reader.u32()}
    explain.update(read_fields(reader, EXPLAIN_FIELDS))
    return explain


def _write_explain(writer: Writer, explain: dict[str, Any]) -> None:
    writer.u32(field(explain, "dwID", "Explain"))
    write_fields(writer, EXPLAIN_FIELDS, explain)


def _read_enchant_item(reader: Reader) -> dict[str, Any]:
    return read_fields(reader, ENCHANT_ITEM_FIELDS)


def _write_enchant_item(writer: Writer, record: dict[str, Any]) -> None:
    write_fields(writer, ENCHANT_ITEM_FIELDS, record)


def _read_stat_group(reader: Reader) -> dict[str, Any]:
    group = {"nStatIdx": reader.i32()}
    count = _read_count(reader, "enchant stat")
    group["Row"] = [read_fields(reader, ENCHANT_STAT_FIELDS) for _ in range(count)]
    return group


def _write_stat_group(writer: Writer, group: dict[str, Any]) -> None:
    writer.i32(field(group, "nStatIdx", "EnchantStat"))
    rows = group.get("Row")
    _write_count(writer, rows, "Row")
    for row in rows:
        write_fields(writer, ENCHANT_STAT_FIELDS, row)


def _read_same_type(reader: Reader) -> dict[str, Any]:
    group = {"nSameType": reader.i32()}
    count = _read_count(reader, "same type")
    group["Row"] = [
        {"nGrowth": reader.i32(), "nValue": reader.f32()} for _ in range(count)
    ]
    return group


def _write_same_type(writer: Writer, group: dict[str, Any]) -> None:
    where = "SameTypeCorrect"
    writer.i32(field(group, "nSameType", where))
    rows = group.get("Row")
    _write_count(writer, rows, "Row")
    for row in rows:
        writer.i32(field(row, "nGrowth", where))
        writer.f32(field(row, "nValue", where))


def _read_trans_info(reader: Reader) -> dict[str, Any]:
    group = {"nTargetGrowth": reader.i32()}
    count = _read_count(reader, "trans info")
    rows = []
    for _ in range(count):
        row = {"nCurrentGrowth": reader.i32()}
        row.update(read_fields(reader, TRANS_INFO_FIELDS))
        rows.append(row)
    group["Row"] = rows
    return group


def _write_trans_info(writer: Writer, group: dict[str, Any]) -> None:
    where = "TransInfo"
    writer.i32(field(group, "nTargetGrowth", where))
    rows = group.get("Row")
    _write_count(writer, rows, "Row")
    for row in rows:
        writer.i32(field(row, "nCurrentGrowth", where))
        write_fields(writer, TRANS_INFO_FIELDS, row)


def _read_trans_evo(reader: Reader) -> dict[str, Any]:
    record = {"dwDigimonIndex": reader.u32()}
    type_count = _read_count(reader, "trans evo type")
    types = []
    for _ in range(type_count):
        entry = {"nItemUseType": reader.i32()}
        material_count = _read_count(reader, "trans material")
        entry["Material"] = [
            read_fields(reader, TRANSCEND_MATERIAL_FIELDS) for _ in range(material_count)
        ]
        types.append(entry)
    record["Type"] = types
    return record


def _write_trans_evo(writer: Writer, record: dict[str, Any]) -> None:
    where = "TransEvo"
    writer.u32(field(record, "dwDigimonIndex", where))
    types = record.get("Type")
    _write_count(writer, types, "Type")
    for entry in types:
        writer.i32(field(entry, "nItemUseType", where))
        materials = entry.get("Material")
        _write_count(writer, materials, "Material")
        for material in materials:
            write_fields(writer, TRANSCEND_MATERIAL_FIELDS, material)


def _read_exp_digimon(reader: Reader) -> dict[str, Any]:
    record = {"dwDigimonIDX": reader.u32()}
    count = _read_count(reader, "exp digimon")
    record["Row"] = [
        {"nDigimonGrowth": reader.i32(), "dwFixedFigyre": reader.u32()} for _ in range(count)
    ]
    return record


def _write_exp_digimon(writer: Writer, record: dict[str, Any]) -> None:
    where = "ExpDigimon"
    writer.u32(field(record, "dwDigimonIDX", where))
    rows = record.get("Row")
    _write_count(writer, rows, "Row")
    for row in rows:
        writer.i32(field(row, "nDigimonGrowth", where))
        writer.u32(field(row, "dwFixedFigyre", where))


class TacticsCodec(Codec):
    name = "Tactics"
    filenames = ("tactics",)
    sections = (
        "Tactics",
        "Explain",
        "EnchantItem",
        "EnchantStat",
        "Correct",
        "SameType",
        "TransInfo",
        "TransEvo",
        "ExpDigimon",
    )
    record_tags = {
        "Tactics": "Tactics",
        "Explain": "Explain",
        "EnchantItem": "EnchantItem",
        "EnchantStat": "EnchantStat",
        "Correct": "Correct",
        "SameType": "SameType",
        "TransInfo": "TransInfo",
        "TransEvo": "TransEvo",
        "ExpDigimon": "ExpDigimon",
    }

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        sections = {"Tactics": read_records(reader, _read_tactics)}
        sections["Explain"] = read_records(reader, _read_explain)
        sections["EnchantItem"] = read_records(reader, _read_enchant_item)
        sections["EnchantStat"] = read_records(reader, _read_stat_group)
        sections["Correct"] = {"nEnchentDefaultCorrect": reader.i32()}
        sections["SameType"] = read_records(reader, _read_same_type)
        sections["TransInfo"] = read_records(reader, _read_trans_info)
        sections["TransEvo"] = read_records(reader, _read_trans_evo)
        sections["ExpDigimon"] = read_records(reader, _read_exp_digimon)
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": sections}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        write_records(writer, self._items(sections, "Tactics"), _write_tactics)
        write_records(writer, self._items(sections, "Explain"), _write_explain)
        write_records(writer, self._items(sections, "EnchantItem"), _write_enchant_item)
        write_records(writer, self._items(sections, "EnchantStat"), _write_stat_group)
        correct = sections.get("Correct")
        if not isinstance(correct, dict):
            raise FormatError("Tactics: 'Correct' must be an object")
        writer.i32(field(correct, "nEnchentDefaultCorrect", "Correct"))
        write_records(writer, self._items(sections, "SameType"), _write_same_type)
        write_records(writer, self._items(sections, "TransInfo"), _write_trans_info)
        write_records(writer, self._items(sections, "TransEvo"), _write_trans_evo)
        write_records(writer, self._items(sections, "ExpDigimon"), _write_exp_digimon)
        return writer.getvalue()



