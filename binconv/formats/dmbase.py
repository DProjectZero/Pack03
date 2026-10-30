"""``DMBase.bin`` -- tamer/digimon base stats and the global game tables.

Ported from ``reference/csharp/DMBase.cs``.  One file, twelve sections, in file
order::

    TamerBaseInfo       count, 40 byte stat block per tamer level
    DigimonBaseInfo     count, same 40 byte stat block per digimon level
    CsBaseMapInfo       count, 12 byte macro check record
    JumpBooster         count, item id + list of map ids
    Party               one float, *no count*
    Guild               count, 44 byte guild level record
    Limit               one record, *no count*
    Store               three floats + item list, *no count*
    PaneltyInfo         count, level / drop / exp
    EvolutionBaseApply  count, evolution type + length prefixed name + value
    DigimonEvoMaxSkill  count, evolution type + skill levels
    ExpansionData       count, expansion conditions

Notes:

* ``Party``, ``Limit`` and ``Store`` are single records: the reader reads them
  once with no count, so ``compile`` insists on exactly one record.
* ``JumpBooster`` stores the map ids as ``int32 count`` + ids.  The C# *writer*
  uses ``jumpbooster.dwMapID`` (a field the reader never fills) instead of the
  ``JumpMaps`` list it just read, so the old tool threw a
  ``NullReferenceException`` there; JSON follows the reader.
* ``PaneltyInfo`` is read as level/drop/exp but the old XML export writes
  level/exp/drop -- JSON keeps the read order, the XML comparison ignores the
  order and compares by element name.
* ``DigimonEvoMaxSkill.nSubCount`` and ``Jumpbooster.mapcount`` are derived
  counts in the original code; JSON stores only the arrays, so they cannot get
  out of sync with their data.
* ``TamerBaseInfo``/``DigimonBaseInfo`` arrays in the C# reader are allocated
  with ``count + 1`` slots and filled from index 1 (slot 0 stays null, and the
  XML export skips it); the count itself is the number of real records.
"""

from __future__ import annotations

from typing import Any, Sequence

from ..binary import FormatError, Reader, UTF16, Writer
from ..codec import Codec, field, read_records, write_records
from ..fields import read_fields, read_text, write_fields, write_text

#: ``Id`` .. ``Unknow2``; the tamer and digimon tables share the layout.
BASE_STAT_FIELDS = [
    ("Id", "i32"),
    ("Level", "u16"),
    ("Unknow1", "u16"),
    ("Exp", "i64"),
    ("Hp", "i32"),
    ("Ds", "i32"),
    ("Ms", "u16"),
    ("De", "u16"),
    ("Ev", "u16"),
    ("Ct", "u16"),
    ("At", "i32"),
    ("Ht", "u16"),
    ("Unknow2", "u16"),
]

CS_BASE_MAP_FIELDS = [
    ("s_nMapID", "i32"),
    ("s_nShoutSec", "i32"),
    ("s_bEnableCheckMacro", "u16"),
    ("unk", "u16"),
]

GUILD_FIELDS = [
    ("s_nLevel", "i32"),
    ("s_nFame", "u32"),
    ("s_nItemNo1", "i32"),
    ("s_nItemCount1", "i32"),
    ("s_nItemNo2", "i32"),
    ("s_nItemCount2", "i32"),
    ("s_nMasterLevel", "i32"),
    ("s_nNeedPerson", "i32"),
    ("s_nMaxGuildPerson", "i32"),
    ("s_nIncMember", "i32"),
    ("s_nMaxGuild2Master", "i32"),
]

PARTY_FIELDS = [("distc", "f32")]

LIMIT_FIELDS = [
    ("s_nMaxTacticsHouse", "u16"),
    ("s_nMaxWareHouse", "u16"),
    ("s_nUnionStore", "u16"),
    ("s_nMaxShareStash", "u16"),
    ("s_nConsume_XG", "i32"),
    ("s_nCharge_XG", "i32"),
]

STORE_FIELDS = [
    ("s_fPerson_Charge", "f32"),
    ("s_fEmployment_Charge", "f32"),
    ("s_fStoreDist", "f32"),
]

STORE_ITEM_FIELDS = [
    ("s_nItemID", "i32"),
    ("s_nDigimonID", "i32"),
    ("s_fScale", "f32"),
    ("s_nSlotCount", "i32"),
    ("s_szFileName", ("z", UTF16, 128)),
]

PANELTY_FIELDS = [
    ("s_nPaneltyLevel", "i32"),
    ("s_nDrop", "i32"),
    ("s_nExp", "i32"),
]

EXPANSION_HEAD_FIELDS = [
    ("nOpenItemSubType", "i32"),
    ("nExpansionRank", "i32"),
]

EVO_MAX_SKILL_HEAD_FIELDS = [
    ("nEvoType", "i32"),
    ("s_SkillExpStartLv", "i32"),
]


# -- helpers -----------------------------------------------------------
def _read_int_list(reader: Reader, what: str) -> list[int]:
    count = reader.i32()
    if count < 0 or count > (len(reader.data) - reader.pos) // 4:
        raise FormatError(
            f"{reader.name}: implausible {what} count {count} at offset {reader.pos - 4}"
        )
    return [reader.i32() for _ in range(count)]


def _write_int_list(writer: Writer, values: Any, what: str) -> None:
    if not isinstance(values, list):
        raise FormatError(f"{what} must be a list of integers")
    writer.i32(len(values))
    for value in values:
        writer.i32(value)


def _list(record: dict[str, Any], name: str, where: str) -> list[Any]:
    try:
        value = record[name]
    except KeyError:
        raise FormatError(f"{where}: missing required list {name!r}") from None
    if not isinstance(value, list):
        raise FormatError(f"{where}: {name!r} must be a list")
    return value


def _one(records: Sequence[dict[str, Any]], where: str) -> dict[str, Any]:
    """Return the single record of an uncounted section."""

    items = list(records)
    if len(items) != 1:
        raise FormatError(
            f"{where}: the file stores exactly one record, got {len(items)}"
        )
    return items[0]


# -- fixed layouts -----------------------------------------------------
def _read_base_stat(reader: Reader) -> dict[str, Any]:
    return read_fields(reader, BASE_STAT_FIELDS)


def _write_base_stat(writer: Writer, record: dict[str, Any]) -> None:
    write_fields(writer, BASE_STAT_FIELDS, record)


def _read_cs_base_map(reader: Reader) -> dict[str, Any]:
    return read_fields(reader, CS_BASE_MAP_FIELDS)


def _write_cs_base_map(writer: Writer, record: dict[str, Any]) -> None:
    write_fields(writer, CS_BASE_MAP_FIELDS, record)


def _read_guild(reader: Reader) -> dict[str, Any]:
    return read_fields(reader, GUILD_FIELDS)


def _write_guild(writer: Writer, record: dict[str, Any]) -> None:
    write_fields(writer, GUILD_FIELDS, record)


def _read_panelty(reader: Reader) -> dict[str, Any]:
    return read_fields(reader, PANELTY_FIELDS)


def _write_panelty(writer: Writer, record: dict[str, Any]) -> None:
    write_fields(writer, PANELTY_FIELDS, record)


# -- JumpBooster -------------------------------------------------------
def _read_jumpbooster(reader: Reader) -> dict[str, Any]:
    record = {"dwItemID": reader.i32()}
    record["dwMapIDs"] = _read_int_list(reader, "map id")
    return record


def _write_jumpbooster(writer: Writer, record: dict[str, Any]) -> None:
    writer.i32(field(record, "dwItemID", "JumpBooster"))
    _write_int_list(writer, _list(record, "dwMapIDs", "JumpBooster"), "JumpBooster.dwMapIDs")


# -- Store -------------------------------------------------------------
def _read_store_item(reader: Reader) -> dict[str, Any]:
    return read_fields(reader, STORE_ITEM_FIELDS)


def _read_store(reader: Reader) -> dict[str, Any]:
    record = read_fields(reader, STORE_FIELDS)
    record["StoreItems"] = read_records(reader, _read_store_item)
    return record


def _write_store(writer: Writer, record: dict[str, Any]) -> None:
    write_fields(writer, STORE_FIELDS, record)
    write_records(writer, _list(record, "StoreItems", "Store"), _write_store_item)


def _write_store_item(writer: Writer, record: dict[str, Any]) -> None:
    write_fields(writer, STORE_ITEM_FIELDS, record)


# -- EvolutionBaseApply ------------------------------------------------
def _read_evolution(reader: Reader) -> dict[str, Any]:
    record = {"EvolutionType": reader.i32(), "EvolutionName": read_text(reader)}
    record["EvolutionApplyValue"] = reader.i32()
    return record


def _write_evolution(writer: Writer, record: dict[str, Any]) -> None:
    writer.i32(field(record, "EvolutionType", "EvolutionBaseApply"))
    write_text(writer, field(record, "EvolutionName", "EvolutionBaseApply"))
    writer.i32(field(record, "EvolutionApplyValue", "EvolutionBaseApply"))


# -- DigimonEvoMaxSkill / ExpansionData --------------------------------
def _read_evo_max_skill(reader: Reader) -> dict[str, Any]:
    record = read_fields(reader, EVO_MAX_SKILL_HEAD_FIELDS)
    record["s_SkillMaxLvs"] = _read_int_list(reader, "skill level")
    return record


def _write_evo_max_skill(writer: Writer, record: dict[str, Any]) -> None:
    write_fields(writer, EVO_MAX_SKILL_HEAD_FIELDS, record)
    _write_int_list(
        writer,
        _list(record, "s_SkillMaxLvs", "DigimonEvoMaxSkill"),
        "DigimonEvoMaxSkill.s_SkillMaxLvs",
    )


def _read_expansion(reader: Reader) -> dict[str, Any]:
    record = read_fields(reader, EXPANSION_HEAD_FIELDS)
    record["nEvoType"] = _read_int_list(reader, "evolution type")
    return record


def _write_expansion(writer: Writer, record: dict[str, Any]) -> None:
    write_fields(writer, EXPANSION_HEAD_FIELDS, record)
    _write_int_list(
        writer, _list(record, "nEvoType", "ExpansionData"), "ExpansionData.nEvoType"
    )


class DMBaseCodec(Codec):
    name = "DMBase"
    filenames = ("dmbase",)
    sections = (
        "TamerBaseInfo",
        "DigimonBaseInfo",
        "CsBaseMapInfo",
        "JumpBooster",
        "Party",
        "Guild",
        "Limit",
        "Store",
        "PaneltyInfo",
        "EvolutionBaseApply",
        "DigimonEvoMaxSkill",
        "ExpansionData",
    )
    record_tags = {
        "TamerBaseInfo": "DMBaseInfo",
        "DigimonBaseInfo": "DigiBaseInfo",
        "CsBaseMapInfo": "CsBaseMapInfo",
        "JumpBooster": "Jumpbooster",
        "Party": "Party",
        "Guild": "Guild",
        "Limit": "Limit",
        "Store": "Store",
        "PaneltyInfo": "PaneltyInfo",
        "EvolutionBaseApply": "EvolutionBaseApply",
        "DigimonEvoMaxSkill": "DigimonEvoMaxSkillLevel",
        "ExpansionData": "ExpansionCondition",
    }

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        sections: dict[str, Any] = {
            "TamerBaseInfo": read_records(reader, _read_base_stat),
            "DigimonBaseInfo": read_records(reader, _read_base_stat),
            "CsBaseMapInfo": read_records(reader, _read_cs_base_map),
            "JumpBooster": read_records(reader, _read_jumpbooster),
            "Party": [read_fields(reader, PARTY_FIELDS)],
            "Guild": read_records(reader, _read_guild),
            "Limit": [read_fields(reader, LIMIT_FIELDS)],
            "Store": [_read_store(reader)],
            "PaneltyInfo": read_records(reader, _read_panelty),
            "EvolutionBaseApply": read_records(reader, _read_evolution),
            "DigimonEvoMaxSkill": read_records(reader, _read_evo_max_skill),
            "ExpansionData": read_records(reader, _read_expansion),
        }
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": sections}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        write_records(writer, self._items(sections, "TamerBaseInfo"), _write_base_stat)
        write_records(writer, self._items(sections, "DigimonBaseInfo"), _write_base_stat)
        write_records(writer, self._items(sections, "CsBaseMapInfo"), _write_cs_base_map)
        write_records(writer, self._items(sections, "JumpBooster"), _write_jumpbooster)
        write_fields(writer, PARTY_FIELDS, _one(self._items(sections, "Party"), "Party"))
        write_records(writer, self._items(sections, "Guild"), _write_guild)
        write_fields(writer, LIMIT_FIELDS, _one(self._items(sections, "Limit"), "Limit"))
        _write_store(writer, _one(self._items(sections, "Store"), "Store"))
        write_records(writer, self._items(sections, "PaneltyInfo"), _write_panelty)
        write_records(
            writer, self._items(sections, "EvolutionBaseApply"), _write_evolution
        )
        write_records(
            writer, self._items(sections, "DigimonEvoMaxSkill"), _write_evo_max_skill
        )
        write_records(writer, self._items(sections, "ExpansionData"), _write_expansion)
        return writer.getvalue()
