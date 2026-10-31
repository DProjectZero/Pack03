"""``DMBase.bin`` -- tamer/digimon base stats and the global game tables.

Ported from ``reference/csharp/DMBase.cs`` and audited against the client
(``dmz-client/LibProj/CsFileTable/BaseMng.cpp::CsBaseMng::SaveBin`` plus the
structs in ``Base.h``, ``BaseMng.h`` and ``DigimonSkillOpenTable.h``).  One file,
twelve sections, in file order::

    TamerBaseInfo       count, 40 byte CsBase::sINFO per tamer level
    DigimonBaseInfo     count, same struct per digimon level
    CsBaseMapInfo       count, 12 byte sINFO (map id, shout sec, bool + padding)
    JumpBooster         count, item id + count + map ids
    Party               sPARTY, one float, *no count*
    Guild               count, 44 byte sGuild
    Limit               sLIMIT, *no count*
    Store               sBASE_INFO (3 floats) + count + sOBJECT_INFO[]
    PaneltyInfo         count, sPLAY_PANELTY (level, exp, drop)
    EvolutionBaseApply  count, int key + wstring name + int value
    DigimonEvoMaxSkill  count, int key + start level + int list
    ExpansionData       count, int key + rank + int list

Notes from the audit:

* The ``#ifdef GUILD_RENEWAL`` blocks (``sGUILDBASE``/``CsGuild_Skill``) that
  ``BaseMng.cpp`` writes between ``PaneltyInfo`` and ``EvolutionBaseApply`` are
  **not** in this build's file: the twelve sections above consume all 85 340
  bytes exactly, so the extra blocks would break the parse.
* ``sPERSON_STORE`` has ``CONSIGNMENT_BALLOON_CASH`` enabled (the
  ``TCHAR s_szFileName[MAX_FILENAME]`` is in the file) and
  ``CONSIGNMENT_CREATE_RESTRICT`` disabled (no ``s_fNpcDist``).
* ``sLIMIT`` has ``NEW_SHARESTASH`` but not ``CROSSWARS_SYSTEM``: four ``SHORT``
  fields, then the two ``unsigned int`` costs.
* ``sINFO`` and ``sPLAY_PANELTY`` are written with ``fwrite``, so the struct's
  alignment padding is part of every record: ``_pad0`` (2 bytes before the
  ``__int64`` exp, 0xFFFF in the data), ``_pad1`` (4 trailing bytes, 18/12) and
  the ``CsBaseMapInfo`` padding.  They hold uninitialised stack bytes the
  exporter never assigned.
* ``s_nAttack``/``s_nHitRate`` are two ``USHORT``; the old reader merged them
  into one int32 (``At``) and reported the trailing padding as ``Ht`` and
  ``Unknow2``.  The hit rate is 0 in all 960 records, so the attack value is
  unchanged, but ``Ht`` no longer pretends to be a stat.
* ``sPLAY_PANELTY`` is ``level, exp, drop``; the old reader swapped exp and
  drop (its XML export swapped them back, hiding it).  Both columns hold the
  same values in the shipped data.

The original C# notes still apply:

* ``Party``, ``Limit`` and ``Store`` are single records: the reader reads them
  once with no count, so ``compile`` insists on exactly one record.
* ``JumpBooster`` stores the map ids as ``int32 count`` + ids.  The C# *writer*
  uses ``jumpbooster.dwMapID`` (a field the reader never fills) instead of the
  ``JumpMaps`` list it just read, so the old tool threw a
  ``NullReferenceException`` there; JSON follows the reader.
* ``DigimonEvoMaxSkill.nSubCount`` and ``Jumpbooster.mapcount`` are derived
  counts in the original code; JSON stores only the arrays, so they cannot get
  out of sync with their data.
* ``TamerBaseInfo``/``DigimonBaseInfo`` arrays in the C# reader are allocated
  with ``count + 1`` slots and filled from index 1 (slot 0 stays null, and the
  XML export skips it); the count itself is the number of real records.
"""

from __future__ import annotations

from typing import Any, Sequence

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, field, read_records, write_records
from ..fields import read_fields, read_text, write_fields, write_text

#: ``CsBase::sINFO`` -- 40 bytes, shared by the tamer and digimon tables::
#:
#:     DWORD   s_dwID            0 .. 4
#:     USHORT  s_nLevel          4 .. 6
#:     <align 2 bytes>           6 .. 8   (uninitialised, 0xFFFF in the data)
#:     __int64 s_dwExp           8 .. 16
#:     int     s_nHP, s_nDS     16 .. 24
#:     USHORT  s_nMoveSpeed .. s_nCritical   24 .. 32
#:     USHORT  s_nAttack        32 .. 34
#:     USHORT  s_nHitRate       34 .. 36
#:     <trailing padding>       36 .. 40  (uninitialised, 18/12 in the data)
#:
#: The old reader took ``s_nAttack``+``s_nHitRate`` as one int32 (``At``) and
#: reported the trailing padding as ``Ht``/``Unknow2``; the hit rate is 0 in
#: every record, so ``At`` and ``s_nAttack`` held the same number.
BASE_STAT_FIELDS = [
    ("Id", "i32"),
    ("Level", "u16"),
    ("_pad0", "u16"),
    ("Exp", "i64"),
    ("Hp", "i32"),
    ("Ds", "i32"),
    ("Ms", "u16"),
    ("De", "u16"),
    ("Ev", "u16"),
    ("Ct", "u16"),
    ("s_nAttack", "u16"),
    ("s_nHitRate", "u16"),
    ("_pad1", "u32"),
]

#: ``CsBaseMapInfo::sINFO`` -- 12 bytes: two DWORDs, a ``bool`` and padding.
CS_BASE_MAP_FIELDS = [
    ("s_nMapID", "i32"),
    ("s_nShoutSec", "i32"),
    ("s_bEnableCheckMacro", "u8"),
    ("_pad0", "u8"),
    ("_pad1", "u16"),
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

#: ``CsBase::sLIMIT`` -- four SHORTs (``NEW_SHARESTASH`` without
#: ``CROSSWARS_SYSTEM``, which is what this build exported) and two ``unsigned
#: int`` costs.
LIMIT_FIELDS = [
    ("s_nMaxTacticsHouse", "u16"),
    ("s_nMaxWareHouse", "u16"),
    ("s_nUnionStore", "u16"),
    ("s_nMaxShareStash", "u16"),
    ("s_nConsume_XG", "u32"),
    ("s_nCharge_XG", "u32"),
]

STORE_FIELDS = [
    ("s_fPerson_Charge", "f32"),
    ("s_fEmployment_Charge", "f32"),
    ("s_fStoreDist", "f32"),
]

#: ``sPERSON_STORE::sOBJECT_INFO`` -- the ``TCHAR s_szFileName[MAX_FILENAME]``
#: exists because this build has ``CONSIGNMENT_BALLOON_CASH``; there is no
#: ``s_fNpcDist`` in ``sBASE_INFO`` because ``CONSIGNMENT_CREATE_RESTRICT`` is off
#: (both confirmed by the exact 85 340 byte parse).
STORE_ITEM_FIELDS = [
    ("s_nItemID", "i32"),
    ("s_nDigimonID", "i32"),
    ("s_fScale", "f32"),
    ("s_nSlotCount", "i32"),
    ("s_szFileName", ("w", 64)),
]

#: ``CsBaseMng::sPLAY_PANELTY`` -- ``s_nPaneltyLevel, s_nExp, s_nDrop``.  The old
#: reader swapped the last two (its XML even re-swapped them), which is
#: invisible in the shipped data because both columns hold the same value.
PANELTY_FIELDS = [
    ("s_nPaneltyLevel", "i32"),
    ("s_nExp", "i32"),
    ("s_nDrop", "i32"),
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
