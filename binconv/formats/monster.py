"""``Monster.bin`` -- the monster catalog, level→hit table, monster skills and shapes.

Layout from the client, ``dmz-client/LibProj/CsFileTable/Monster.h``
(``CsMonster::sINFO``, ``CsMonsterSkill::sINFO``, ``CsMonsterSkillTerms::sINFO``)
read by ``MonsterMng.cpp::_LoadBin`` (lines 621-665).  Four counted sections::

    CsMonster::sINFO                396 bytes   (2138 records)
        DWORD  s_dwMonsterID, s_dwModelID
        TCHAR  s_szName[64]                     128 bytes
        TCHAR  s_szPenName[34]                   68 bytes
        TCHAR  s_szTitle[64]                    128 bytes
        USHORT s_nLevel, s_nEXP, s_nBattle
        <2 bytes of struct padding: int s_nHP must be 4 byte aligned>
        int    s_nHP, s_nDS
        USHORT s_nDefPower, s_nEvasion, s_nMoveSpeed, s_nWalkSpeed,
               s_nCritcalRate, s_nAttPower, s_nAttSpeed, s_nAttRange,
               s_nHitRate, s_nSight, s_nHuntRange
        <2 bytes of struct padding: float must be 4 byte aligned>
        float  s_fScale
        USHORT s_nClass, s_nIcon1..s_nIcon6, s_Exp_Min, s_Exp_Max
        <2 bytes of struct tail padding>

    level->hit                      8 bytes     (100 records, ``int nLV; int nHT``)

    CsMonsterSkill::sINFO           144 bytes   (2044 records)
        USHORT s_nSkill_IDX, <pad>, DWORD s_dwMonsterID, DWORD s_dwCoolTime,
        USHORT s_nCastTime, s_nCastCheck, s_nTarget_Cnt, s_nTarget_MinCnt,
        s_nTarget_MaxCnt, s_nUse_Terms, s_nSkillType, <pad>,
        DWORD s_dwEff_Val_Min, s_dwEff_Val_Max, USHORT s_nRangeIdx, <pad>,
        DWORD s_dwSequenceID, USHORT s_nAni_Delay, s_nValocity, s_nAccel,
        USHORT s_nEff_Factor[3], DWORD s_dwEff_Fact_Val[3],
        UINT s_nTalkId, UINT s_nActiveType, FLOAT s_fNoticeTime,
        char s_szNoticeEff_Name[64]

    CsMonsterSkillTerms::sINFO      12 bytes    (31 records)
        USHORT s_nIDX, s_nDirection, UINT s_nRange, s_nTargetingType, s_nRefCode

The shipped file is exactly 1 142 172 bytes (4 + 2138 * 396 + 4 + 100 * 8 +
4 + 2044 * 144 + 4 + 31 * 12).  ``CsMonsterDrop`` declared in ``Monster.h`` is
*not* in the bin: its loader (``_LoadExcelDrop``) is commented out in the client
and ``SaveBin`` has no entry for it.
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, read_records, write_records
from ..fields import read_fields, write_fields

MONSTER_FIELDS = [
    ("s_dwMonsterID", "u32"),
    ("s_dwModelID", "u32"),
    ("s_szName", ("w", 64)),
    ("s_szPenName", ("w", 34)),
    ("s_szTitle", ("w", 64)),
    ("s_nLevel", "u16"),
    ("s_nEXP", "u16"),
    ("s_nBattle", "u16"),
    ("_pad0", "u16"),
    ("s_nHP", "i32"),
    ("s_nDS", "i32"),
    ("s_nDefPower", "u16"),
    ("s_nEvasion", "u16"),
    ("s_nMoveSpeed", "u16"),
    ("s_nWalkSpeed", "u16"),
    ("s_nCritcalRate", "u16"),
    ("s_nAttPower", "u16"),
    ("s_nAttSpeed", "u16"),
    ("s_nAttRange", "u16"),
    ("s_nHitRate", "u16"),
    ("s_nSight", "u16"),
    ("s_nHuntRange", "u16"),
    ("_pad1", "u16"),
    ("s_fScale", "f32"),
    ("s_nClass", "u16"),
    ("s_nIcon1", "u16"),
    ("s_nIcon2", "u16"),
    ("s_nIcon3", "u16"),
    ("s_nIcon4", "u16"),
    ("s_nIcon5", "u16"),
    ("s_nIcon6", "u16"),
    ("s_Exp_Min", "u16"),
    ("s_Exp_Max", "u16"),
    ("_pad2", "u16"),
]

HIT_FIELDS = [("nLV", "i32"), ("nHT", "i32")]

MONSTER_SKILL_FIELDS = [
    ("s_nSkill_IDX", "u16"),
    ("_pad0", "u16"),
    ("s_dwMonsterID", "u32"),
    ("s_dwCoolTime", "u32"),
    ("s_nCastTime", "u16"),
    ("s_nCastCheck", "u16"),
    ("s_nTarget_Cnt", "u16"),
    ("s_nTarget_MinCnt", "u16"),
    ("s_nTarget_MaxCnt", "u16"),
    ("s_nUse_Terms", "u16"),
    ("s_nSkillType", "u16"),
    ("_pad1", "u16"),
    ("s_dwEff_Val_Min", "u32"),
    ("s_dwEff_Val_Max", "u32"),
    ("s_nRangeIdx", "u16"),
    ("_pad2", "u16"),
    ("s_dwSequenceID", "u32"),
    ("s_nAni_Delay", "u16"),
    ("s_nValocity", "u16"),
    ("s_nAccel", "u16"),
    ("s_nEff_Factor0", "u16"),
    ("s_nEff_Factor1", "u16"),
    ("s_nEff_Factor2", "u16"),
    ("s_dwEff_Fact_Val0", "u32"),
    ("s_dwEff_Fact_Val1", "u32"),
    ("s_dwEff_Fact_Val2", "u32"),
    ("s_nTalkId", "u32"),
    ("s_nActiveType", "u32"),
    ("s_fNoticeTime", "f32"),
    ("s_szNoticeEff_Name", ("c", "ascii", 64)),
]

MONSTER_SKILL_TERMS_FIELDS = [
    ("s_nIDX", "u16"),
    ("s_nDirection", "u16"),
    ("s_nRange", "u32"),
    ("s_nTargetingType", "u16"),
    ("s_nRefCode", "u16"),
]


def _field_table(fields: list[tuple[str, Any]]) -> tuple[Any, Any]:
    def read(reader: Reader) -> dict[str, Any]:
        return read_fields(reader, fields)

    def write(writer: Writer, record: dict[str, Any]) -> None:
        write_fields(writer, fields, record)

    return read, write


SECTIONS = {
    "Monster": _field_table(MONSTER_FIELDS),
    "MonsterHit": _field_table(HIT_FIELDS),
    "MonsterSkill": _field_table(MONSTER_SKILL_FIELDS),
    "MonsterSkillTerms": _field_table(MONSTER_SKILL_TERMS_FIELDS),
}


class MonsterCodec(Codec):
    name = "Monster"
    filenames = ("monster",)
    sections = ("Monster", "MonsterHit", "MonsterSkill", "MonsterSkillTerms")
    record_tags = {
        "Monster": "Monster",
        "MonsterHit": "Hit",
        "MonsterSkill": "MonsterSkill",
        "MonsterSkillTerms": "MonsterSkillTerms",
    }

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        sections = {
            name: read_records(reader, read) for name, (read, _) in SECTIONS.items()
        }
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": sections}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        for name, (_, write) in SECTIONS.items():
            write_records(writer, self._items(sections, name), write)
        return writer.getvalue()

