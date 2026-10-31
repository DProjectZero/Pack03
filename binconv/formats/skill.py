"""``Skill.bin`` -- skill definitions, tamer skills and area checks.

Layout from the client, ``CsFileTable/Skill.h`` plus
``_SkillDefine.h`` (``SKILL_NAME_LEN`` 32, ``SKILL_COMMENT_LEN`` 256,
``SKILL_APPLY_MAX_COUNT`` 3, ``DIGIMON_MAX_SKILL_COUNT`` unaffected here), written
by ``SkillMng.cpp::SaveBin`` (lines 536-587).  Three counted sections::

    CsSkill::sINFO                     736 bytes
        DWORD  s_dwID
        TCHAR  s_szName[32]                      64 bytes
        TCHAR  s_szComment[256]                 512 bytes
        sAPPLY s_Apply[3]                         24 bytes each:
            int    s_nA, s_nInvoke_Rate, s_nB, s_nC
            USHORT s_nBuffCode, s_nID
            SHORT  s_nIncrease_B_Point
            <2 bytes of struct padding>
        USHORT s_nLevelupPoint, s_nMaxLevel
        USHORT s_nAttributeType, s_nNatureType, s_nFamilyType
        USHORT s_nUseHP, s_nUseDS
        USHORT s_nIcon, s_nTarget, s_nAttType
        float  s_fAttRange, s_fAttRange_MinDmg, s_fAttRange_NorDmg, s_fAttRange_MaxDmg
        USHORT s_nAttSphere
        <2 bytes of struct padding: float must be 4 byte aligned>
        float  s_fCastingTime, s_fDamageTime
        USHORT s_nDamageDay
        <2 bytes of struct padding>
        float  s_nDistanceTime      (declared float even though the name says n)
        float  s_fCooldownTime
        USHORT s_nCooldownDay
        <2 bytes of struct padding>
        float  s_fSkill_Velocity, s_fSkill_Accel
        USHORT s_nSkillType, s_nLimitLevel, s_nSkillGroup, s_nSkillRank,
               s_nMemorySkill, s_nReq_Item

    CsTamerSkill::sTSkill_INFO          36 bytes
        USHORT s_nIndex, <pad>, DWORD s_dwSkillCode, USHORT s_nType, <pad>,
        DWORD s_dwFactor1, s_dwFactor2, s_dwTamer_SeqID, s_dwDigimon_SeqID,
        USHORT s_nUseState, s_nUse_Are_Check, s_nAvailable, <pad>

    CsAreaCheck::sArea_Check            64 bytes
        DWORD s_dwIndex, USHORT s_nArea[30]

The shipped file holds 5322 / 64 / 93 records and is exactly 3 925 260 bytes
(4 + 5322 * 736 + 4 + 64 * 36 + 4 + 93 * 64), which pins the 736 byte stride.

Two traps the old ``the XML dump/Skill`` export fell into: it has no padding field
before ``s_fCastingTime`` (so its float values there are misaligned) and it prints
the padding shorts as ``ink``/``unk``/``unknow``.  The JSON keeps the client's
padding as ``_pad0``..``_pad3`` so a recompile is byte identical.  Duplicate skill
ids are *kept*: the pack contains rows with the same id and dropping them (as the
server's loader does) would change the file.
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, field, read_records, write_records
from ..fields import read_fields, write_fields

SKILL_APPLY_COUNT = 3
AREA_CHECK_AREA_COUNT = 30

SKILL_HEAD_FIELDS = [
    ("ID", "u32"),
    ("Name", ("w", 32)),
    ("Comment", ("w", 256)),
]

SKILL_TAIL_FIELDS = [
    ("LevelupPoint", "u16"),
    ("MaxLevel", "u16"),
    ("AttributeType", "u16"),
    ("NatureType", "u16"),
    ("FamilyType", "u16"),
    ("UseHP", "u16"),
    ("UseDS", "u16"),
    ("Icon", "u16"),
    ("Target", "u16"),
    ("AttType", "u16"),
    ("AttRange", "f32"),
    ("AttRange_MinDmg", "f32"),
    ("AttRange_NorDmg", "f32"),
    ("AttRange_MaxDmg", "f32"),
    ("AttSphere", "u16"),
    ("_pad0", "u16"),
    ("CastingTime", "f32"),
    ("DamageTime", "f32"),
    ("DamageDay", "u16"),
    ("_pad1", "u16"),
    ("DistanceTime", "f32"),
    ("CooldownTime", "f32"),
    ("CooldownDay", "u16"),
    ("_pad2", "u16"),
    ("Skill_Velocity", "f32"),
    ("Skill_Accel", "f32"),
    ("SkillType", "u16"),
    ("LimitLevel", "u16"),
    ("SkillGroup", "u16"),
    ("SkillRank", "u16"),
    ("MemorySkill", "u16"),
    ("Req_Item", "u16"),
]

TAMER_SKILL_FIELDS = [
    ("Index", "u16"),
    ("_pad0", "u16"),
    ("SkillCode", "u32"),
    ("Type", "u16"),
    ("_pad1", "u16"),
    ("Factor1", "u32"),
    ("Factor2", "u32"),
    ("Tamer_SeqID", "u32"),
    ("Digimon_SeqID", "u32"),
    ("UseState", "u16"),
    ("Use_Are_Check", "u16"),
    ("Available", "u16"),
    ("_pad2", "u16"),
]


def _read_apply(reader: Reader) -> dict[str, Any]:
    return {
        "A": reader.i32(),
        "Invoke_Rate": reader.i32(),
        "B": reader.i32(),
        "C": reader.i32(),
        "BuffCode": reader.u16(),
        "ID": reader.u16(),
        "Increase_B_Point": reader.i16(),
        "_pad0": reader.u16(),
    }


def _write_apply(writer: Writer, apply: dict[str, Any]) -> None:
    where = "Skill"
    writer.i32(field(apply, "A", where))
    writer.i32(field(apply, "Invoke_Rate", where))
    writer.i32(field(apply, "B", where))
    writer.i32(field(apply, "C", where))
    writer.u16(field(apply, "BuffCode", where))
    writer.u16(field(apply, "ID", where))
    writer.i16(field(apply, "Increase_B_Point", where))
    writer.u16(field(apply, "_pad0", where))


def _read_skill(reader: Reader) -> dict[str, Any]:
    record = read_fields(reader, SKILL_HEAD_FIELDS)
    record["Apply"] = [_read_apply(reader) for _ in range(SKILL_APPLY_COUNT)]
    record.update(read_fields(reader, SKILL_TAIL_FIELDS))
    return record


def _write_skill(writer: Writer, record: dict[str, Any]) -> None:
    where = "Skill"
    write_fields(writer, SKILL_HEAD_FIELDS, record)
    applies = record.get("Apply")
    if not isinstance(applies, list) or len(applies) != SKILL_APPLY_COUNT:
        raise FormatError(f"{where}: 's_Apply' must be a list of {SKILL_APPLY_COUNT} entries")
    for apply in applies:
        _write_apply(writer, apply)
    write_fields(writer, SKILL_TAIL_FIELDS, record)


def _read_tamer_skill(reader: Reader) -> dict[str, Any]:
    return read_fields(reader, TAMER_SKILL_FIELDS)


def _write_tamer_skill(writer: Writer, record: dict[str, Any]) -> None:
    write_fields(writer, TAMER_SKILL_FIELDS, record)


def _read_area_check(reader: Reader) -> dict[str, Any]:
    return {
        "Index": reader.u32(),
        "Area": [reader.u16() for _ in range(AREA_CHECK_AREA_COUNT)],
    }


def _write_area_check(writer: Writer, record: dict[str, Any]) -> None:
    where = "AreaCheck"
    writer.u32(field(record, "Index", where))
    areas = record.get("Area")
    if not isinstance(areas, list) or len(areas) != AREA_CHECK_AREA_COUNT:
        raise FormatError(
            f"{where}: 's_nArea' must be a list of {AREA_CHECK_AREA_COUNT} numbers"
        )
    for area in areas:
        writer.u16(area)


class SkillCodec(Codec):
    name = "Skill"
    filenames = ("skill",)
    sections = ("Skill", "TamerSkill", "AreaCheck")
    record_tags = {"Skill": "SkillData", "TamerSkill": "TamerSkill", "AreaCheck": "AreaCheck"}

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        sections = {"Skill": read_records(reader, _read_skill)}
        sections["TamerSkill"] = read_records(reader, _read_tamer_skill)
        sections["AreaCheck"] = read_records(reader, _read_area_check)
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": sections}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        write_records(writer, self._items(sections, "Skill"), _write_skill)
        write_records(writer, self._items(sections, "TamerSkill"), _write_tamer_skill)
        write_records(writer, self._items(sections, "AreaCheck"), _write_area_check)
        return writer.getvalue()

