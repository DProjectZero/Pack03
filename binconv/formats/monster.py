"""``Monster.bin`` -- the monster catalog, level→hit table, monster skills and shapes.

Layout from the client, ``CsFileTable/Monster.h``
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
    ("MonsterID", "u32"),
    ("ModelID", "u32"),
    ("Name", ("w", 64)),
    ("PenName", ("w", 34)),
    ("Title", ("w", 64)),
    ("Level", "u16"),
    ("EXP", "u16"),
    ("Battle", "u16"),
    ("_pad0", "u16"),
    ("HP", "i32"),
    ("DS", "i32"),
    ("DefPower", "u16"),
    ("Evasion", "u16"),
    ("MoveSpeed", "u16"),
    ("WalkSpeed", "u16"),
    ("CriticalRate", "u16"),
    ("AttPower", "u16"),
    ("AttSpeed", "u16"),
    ("AttRange", "u16"),
    ("HitRate", "u16"),
    ("Sight", "u16"),
    ("HuntRange", "u16"),
    ("_pad1", "u16"),
    ("Scale", "f32"),
    ("Class", "u16"),
    ("Icon1", "u16"),
    ("Icon2", "u16"),
    ("Icon3", "u16"),
    ("Icon4", "u16"),
    ("Icon5", "u16"),
    ("Icon6", "u16"),
    ("Exp_Min", "u16"),
    ("Exp_Max", "u16"),
    ("_pad2", "u16"),
]

HIT_FIELDS = [("LV", "i32"), ("HT", "i32")]

MONSTER_SKILL_FIELDS = [
    ("Skill_IDX", "u16"),
    ("_pad0", "u16"),
    ("MonsterID", "u32"),
    ("CoolTime", "u32"),
    ("CastTime", "u16"),
    ("CastCheck", "u16"),
    ("Target_Cnt", "u16"),
    ("Target_MinCnt", "u16"),
    ("Target_MaxCnt", "u16"),
    ("Use_Terms", "u16"),
    ("SkillType", "u16"),
    ("_pad1", "u16"),
    ("Eff_Val_Min", "u32"),
    ("Eff_Val_Max", "u32"),
    ("RangeIdx", "u16"),
    ("_pad2", "u16"),
    ("SequenceID", "u32"),
    ("Ani_Delay", "u16"),
    ("Velocity", "u16"),
    ("Accel", "u16"),
    ("EffectFactor0", "u16"),
    ("EffectFactor1", "u16"),
    ("EffectFactor2", "u16"),
    ("EffectFactorValue0", "u32"),
    ("EffectFactorValue1", "u32"),
    ("EffectFactorValue2", "u32"),
    ("TalkID", "u32"),
    ("ActiveType", "u32"),
    ("NoticeTime", "f32"),
    ("NoticeEff_Name", ("c", "ascii", 64)),
]

MONSTER_SKILL_TERMS_FIELDS = [
    ("IDX", "u16"),
    ("Direction", "u16"),
    ("Range", "u32"),
    ("TargetingType", "u16"),
    ("RefCode", "u16"),
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

