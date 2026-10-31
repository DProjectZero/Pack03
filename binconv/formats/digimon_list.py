"""``Digimon_List.bin`` -- the digimon base table (``CsDigimon::sINFO``).

Layout from the client, ``dmz-client/LibProj/CsFileTable/Digimon.h`` (lines 21-84);
``DIGIMON_MAX_SKILL_COUNT`` is 4 and ``sizeof(sINFO)`` is the 572 byte stride of
the shipped file::

    DWORD  s_dwDigimonID
    DWORD  s_dwModelID
    TCHAR  s_szName[64]                 128 bytes
    char   s_cSoundDirName[64]
    float  s_fSelectScale
    TCHAR  s_szEvoEffectDir[64]         128 bytes
    int    s_eEvolutionType
    int    s_eAttributeType
    int    s_eFamilyType[3]
    int    s_eBaseNatureType
    int    s_eBaseNatureTypes[3]
    DWORD  s_dwBaseLevel
    USHORT s_nBaseStat_{HP,DS,DefPower,Evasion,MoveSpeed,CriticalRate,
                        AttPower,AttSpeed,AttRange,HitRate}     10 x 2 bytes
    BYTE   s_nDigimonType
    <1 byte of struct padding>
    USHORT s_dwCharSize
    sSKILL s_Skill[4]                   {DWORD s_dwID; int s_nReqPrevSkillLevel}
    float  s_fWakkLen, s_fRunLen, s_fARunLen
    TCHAR  s_szForm[64]                 128 bytes
    int    s_nDigimonRank

The shipped file holds 634 records (4 + 634 * 572 = 362 652 bytes, the exact file
size).  The single pad byte after ``s_nDigimonType`` is kept as ``_pad0`` so a
recompile stays byte identical.
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, field, read_records, write_records

DIGIMON_SKILL_COUNT = 4
FAMILY_COUNT = 3
NATURE_ALT_COUNT = 3

STAT_NAMES = (
    "s_nBaseStat_HP",
    "s_nBaseStat_DS",
    "s_nBaseStat_DefPower",
    "s_nBaseStat_Evasion",
    "s_nBaseStat_MoveSpeed",
    "s_nBaseStat_CriticalRate",
    "s_nBaseStat_AttPower",
    "s_nBaseStat_AttSpeed",
    "s_nBaseStat_AttRange",
    "s_nBaseStat_HitRate",
)


def _read_digimon(reader: Reader) -> dict[str, Any]:
    record: dict[str, Any] = {
        "s_dwDigimonID": reader.u32(),
        "s_dwModelID": reader.u32(),
        "s_szName": reader.wstring(64),
        "s_cSoundDirName": reader.cstring("ascii", 64),
        "s_fSelectScale": reader.f32(),
        "s_szEvoEffectDir": reader.wstring(64),
        "s_eEvolutionType": reader.i32(),
        "s_eAttributeType": reader.i32(),
        "s_eFamilyType": [reader.i32() for _ in range(FAMILY_COUNT)],
        "s_eBaseNatureType": reader.i32(),
        "s_eBaseNatureTypes": [reader.i32() for _ in range(NATURE_ALT_COUNT)],
        "s_dwBaseLevel": reader.u32(),
    }
    for name in STAT_NAMES:
        record[name] = reader.u16()
    record["s_nDigimonType"] = reader.u8()
    record["_pad0"] = reader.u8()
    record["s_dwCharSize"] = reader.u16()
    record["s_Skill"] = [
        {"s_dwID": reader.u32(), "s_nReqPrevSkillLevel": reader.i32()}
        for _ in range(DIGIMON_SKILL_COUNT)
    ]
    record["s_fWakkLen"] = reader.f32()
    record["s_fRunLen"] = reader.f32()
    record["s_fARunLen"] = reader.f32()
    record["s_szForm"] = reader.wstring(64)
    record["s_nDigimonRank"] = reader.i32()
    return record


def _write_int_list(writer: Writer, record: dict[str, Any], name: str, count: int) -> None:
    values = record.get(name)
    if not isinstance(values, list) or len(values) != count:
        raise FormatError(f"Digimon_List: {name!r} must be a list of {count} numbers")
    for value in values:
        writer.i32(value)


def _write_digimon(writer: Writer, record: dict[str, Any]) -> None:
    where = "Digimon_List"
    writer.u32(field(record, "s_dwDigimonID", where))
    writer.u32(field(record, "s_dwModelID", where))
    writer.wstring(field(record, "s_szName", where), 64)
    writer.cstring(field(record, "s_cSoundDirName", where), "ascii", 64)
    writer.f32(field(record, "s_fSelectScale", where))
    writer.wstring(field(record, "s_szEvoEffectDir", where), 64)
    writer.i32(field(record, "s_eEvolutionType", where))
    writer.i32(field(record, "s_eAttributeType", where))
    _write_int_list(writer, record, "s_eFamilyType", FAMILY_COUNT)
    writer.i32(field(record, "s_eBaseNatureType", where))
    _write_int_list(writer, record, "s_eBaseNatureTypes", NATURE_ALT_COUNT)
    writer.u32(field(record, "s_dwBaseLevel", where))
    for name in STAT_NAMES:
        writer.u16(field(record, name, where))
    writer.u8(field(record, "s_nDigimonType", where))
    writer.u8(field(record, "_pad0", where))
    writer.u16(field(record, "s_dwCharSize", where))
    skills = record.get("s_Skill")
    if not isinstance(skills, list) or len(skills) != DIGIMON_SKILL_COUNT:
        raise FormatError(
            f"{where}: 's_Skill' must be a list of {DIGIMON_SKILL_COUNT} entries"
        )
    for skill in skills:
        writer.u32(field(skill, "s_dwID", where))
        writer.i32(field(skill, "s_nReqPrevSkillLevel", where))
    writer.f32(field(record, "s_fWakkLen", where))
    writer.f32(field(record, "s_fRunLen", where))
    writer.f32(field(record, "s_fARunLen", where))
    writer.wstring(field(record, "s_szForm", where), 64)
    writer.i32(field(record, "s_nDigimonRank", where))



class DigimonListCodec(Codec):
    name = "Digimon_List"
    filenames = ("digimon_list",)
    sections = ("Digimon_List",)
    record_tags = {"Digimon_List": "Digimon"}

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        records = read_records(reader, _read_digimon)
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": {"Digimon_List": records}}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        write_records(writer, self._items(sections, "Digimon_List"), _write_digimon)
        return writer.getvalue()
