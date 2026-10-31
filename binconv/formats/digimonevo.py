"""``DigimonEvo.bin`` -- the evolution trees and the battle-evolution table.

Layout from the client, ``CDigimonEvolution.cpp::SaveBin`` /
``_LoadBin`` with ``DigimonEvolveInfo.h`` (``CDigimonEvolveInfo::sINFO``),
``DigimonEvolveObj.h`` (``CDigimonEvolveObj``) and ``CDigimonEvolution.h``
(``sBATTLE_EVO_INFO``)::

    int32 nCount                                  ; 140 evolution trees
    per tree:
        CDigimonEvolveInfo::sINFO    8 bytes      ; DWORD s_nDigimonID, s_nBattleEvoType
        int32 nEvoCount
        nEvoCount x CDigimonEvolveObj            ; 328 bytes each
    int32 nBattleEvoCount                         ; 5
    nBattleEvoCount x sBATTLE_EVO_INFO           ; 50 bytes each

``CDigimonEvolveObj`` (328 bytes, MSVC layout, ``MAX_EVOLUTION`` = 9,
``MAX_EVO_EFFECT_LEN`` = 32, ``MAX_JOINT_TACTICS_LEN`` = 3)::

    DWORD  m_dwID, USHORT m_nEvoSlot, <pad>
    SEvolutionInfo m_nEvolutionList[9]   {USHORT nSlot, USHORT nType, DWORD dwDigimonID}
    CsPoint m_IconPos                    {int x, int y}
    USHORT m_nEnableSlot, m_nOpenQualification, m_nOpenLevel, m_nOpenQuest,
           m_nOpenItemTypeS, m_nOpenItemNum, m_nUseItem, m_nUseItemNum,
           m_nIntimacy, m_nOpenCrest, m_EvoCard1, m_EvoCard2, m_EvoCard3,
           m_nEvoDigimental, m_nEvoTamerDS, m_nDummy
    int    m_bRender
    CsPoint m_TargetStartPos, int m_nStartHegiht, int m_nStartRot
    CsPoint m_TargetEndPos,   int m_nEndHegiht,   int m_nEndRot
    int    m_nSpeed, DWORD m_dwAni
    <4 bytes of struct padding: double must be 8 byte aligned>
    double m_fStartTime, m_fEndTime
    int    m_nR, m_nG, m_nB
    char   m_szLevel[32], m_szEnchant[32], m_szSize[32]
    int    m_nEvolutionTree, DWORD m_nJoGressQuestCheck
    USHORT m_nChipsetType, m_nChipsetTypeC, m_nChipsetNum, m_nChipsetTypeP,
           m_nJoGressesNum
    <2 bytes of struct padding: int array must be 4 byte aligned>
    int    m_nJoGress_Tacticses[3]
    <4 bytes of struct tail padding>

``sBATTLE_EVO_INFO`` is ``USHORT s_nMaxEP`` followed by six
``sELEMENT { bool s_bEnable; <pad>; USHORT s_nEvolStep, s_nReqEvoEP, s_nDecEP; }``
(8 bytes each), i.e. 50 bytes.

The shipped file holds 140 trees with 639 evolution objects and 5 battle-evo rows
(211 530 bytes = 4 + sum(12 + n * 328) + 4 + 5 * 50), which is exactly the size on
disk.  ``m_IconPos``/``m_TargetStartPos``/``m_TargetEndPos`` are ``CsPoint``
pairs; they are flattened to ``_X``/``_Y`` keys so the JSON stays flat.
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, field, read_records, write_records

MAX_EVOLUTION = 9
MAX_EVO_EFFECT_LEN = 32
MAX_JOINT_TACTICS_LEN = 3
BATTLE_EVO_ELEMENT_CNT = 6

EVO_OBJ_TAIL_U16 = (
    "m_nEnableSlot",
    "m_nOpenQualification",
    "m_nOpenLevel",
    "m_nOpenQuest",
    "m_nOpenItemTypeS",
    "m_nOpenItemNum",
    "m_nUseItem",
    "m_nUseItemNum",
    "m_nIntimacy",
    "m_nOpenCrest",
    "m_EvoCard1",
    "m_EvoCard2",
    "m_EvoCard3",
    "m_nEvoDigimental",
    "m_nEvoTamerDS",
    "m_nDummy",
)

CHIPSET_U16 = (
    "m_nChipsetType",
    "m_nChipsetTypeC",
    "m_nChipsetNum",
    "m_nChipsetTypeP",
    "m_nJoGressesNum",
)


def _read_evo_obj(reader: Reader) -> dict[str, Any]:
    obj: dict[str, Any] = {
        "m_dwID": reader.u32(),
        "m_nEvoSlot": reader.u16(),
        "_pad0": reader.u16(),
        "m_nEvolutionList": [
            {
                "Slot": reader.u16(),
                "Type": reader.u16(),
                "DigimonID": reader.u32(),
            }
            for _ in range(MAX_EVOLUTION)
        ],
        "m_IconPos_X": reader.i32(),
        "m_IconPos_Y": reader.i32(),
    }
    for name in EVO_OBJ_TAIL_U16:
        obj[name] = reader.u16()
    obj["m_bRender"] = reader.i32()
    obj["m_TargetStartPos_X"] = reader.i32()
    obj["m_TargetStartPos_Y"] = reader.i32()
    obj["m_nStartHegiht"] = reader.i32()
    obj["m_nStartRot"] = reader.i32()
    obj["m_TargetEndPos_X"] = reader.i32()
    obj["m_TargetEndPos_Y"] = reader.i32()
    obj["m_nEndHegiht"] = reader.i32()
    obj["m_nEndRot"] = reader.i32()
    obj["m_nSpeed"] = reader.i32()
    obj["m_dwAni"] = reader.u32()
    obj["_pad1"] = reader.u32()
    obj["m_fStartTime"] = reader.f64()
    obj["m_fEndTime"] = reader.f64()
    obj["m_nR"] = reader.i32()
    obj["m_nG"] = reader.i32()
    obj["m_nB"] = reader.i32()
    obj["m_szLevel"] = reader.cstring("ascii", MAX_EVO_EFFECT_LEN)
    obj["m_szEnchant"] = reader.cstring("ascii", MAX_EVO_EFFECT_LEN)
    obj["m_szSize"] = reader.cstring("ascii", MAX_EVO_EFFECT_LEN)
    obj["m_nEvolutionTree"] = reader.i32()
    obj["m_nJoGressQuestCheck"] = reader.u32()
    for name in CHIPSET_U16:
        obj[name] = reader.u16()
    obj["_pad2"] = reader.u16()
    obj["m_nJoGress_Tacticses"] = [reader.i32() for _ in range(MAX_JOINT_TACTICS_LEN)]
    obj["_pad3"] = reader.u32()
    return obj


def _write_evo_obj(writer: Writer, obj: dict[str, Any]) -> None:
    where = "DigimonEvo"
    writer.u32(field(obj, "m_dwID", where))
    writer.u16(field(obj, "m_nEvoSlot", where))
    writer.u16(field(obj, "_pad0", where))
    entries = obj.get("m_nEvolutionList")
    if not isinstance(entries, list) or len(entries) != MAX_EVOLUTION:
        raise FormatError(
            f"{where}: 'm_nEvolutionList' must be a list of {MAX_EVOLUTION} entries"
        )
    for entry in entries:
        writer.u16(field(entry, "Slot", where))
        writer.u16(field(entry, "Type", where))
        writer.u32(field(entry, "DigimonID", where))
    writer.i32(field(obj, "m_IconPos_X", where))
    writer.i32(field(obj, "m_IconPos_Y", where))
    for name in EVO_OBJ_TAIL_U16:
        writer.u16(field(obj, name, where))
    writer.i32(field(obj, "m_bRender", where))
    writer.i32(field(obj, "m_TargetStartPos_X", where))
    writer.i32(field(obj, "m_TargetStartPos_Y", where))
    writer.i32(field(obj, "m_nStartHegiht", where))
    writer.i32(field(obj, "m_nStartRot", where))
    writer.i32(field(obj, "m_TargetEndPos_X", where))
    writer.i32(field(obj, "m_TargetEndPos_Y", where))
    writer.i32(field(obj, "m_nEndHegiht", where))
    writer.i32(field(obj, "m_nEndRot", where))
    writer.i32(field(obj, "m_nSpeed", where))
    writer.u32(field(obj, "m_dwAni", where))
    writer.u32(field(obj, "_pad1", where))
    writer.f64(field(obj, "m_fStartTime", where))
    writer.f64(field(obj, "m_fEndTime", where))
    writer.i32(field(obj, "m_nR", where))
    writer.i32(field(obj, "m_nG", where))
    writer.i32(field(obj, "m_nB", where))
    writer.cstring(field(obj, "m_szLevel", where), "ascii", MAX_EVO_EFFECT_LEN)
    writer.cstring(field(obj, "m_szEnchant", where), "ascii", MAX_EVO_EFFECT_LEN)
    writer.cstring(field(obj, "m_szSize", where), "ascii", MAX_EVO_EFFECT_LEN)
    writer.i32(field(obj, "m_nEvolutionTree", where))
    writer.u32(field(obj, "m_nJoGressQuestCheck", where))
    for name in CHIPSET_U16:
        writer.u16(field(obj, name, where))
    writer.u16(field(obj, "_pad2", where))
    tactics = obj.get("m_nJoGress_Tacticses")
    if not isinstance(tactics, list) or len(tactics) != MAX_JOINT_TACTICS_LEN:
        raise FormatError(
            f"{where}: 'm_nJoGress_Tacticses' must be a list of {MAX_JOINT_TACTICS_LEN}"
        )
    for value in tactics:
        writer.i32(value)
    writer.u32(field(obj, "_pad3", where))


def _read_tree(reader: Reader) -> dict[str, Any]:
    tree: dict[str, Any] = {
        "DigimonID": reader.u32(),
        "BattleEvoType": reader.u32(),
    }
    count = reader.i32()
    if count < 0 or count > (len(reader.data) - reader.pos):
        raise FormatError(
            f"{reader.name}: implausible evolution count {count} at offset {reader.pos - 4}"
        )
    tree["EvolveObj"] = [_read_evo_obj(reader) for _ in range(count)]
    return tree


def _write_tree(writer: Writer, tree: dict[str, Any]) -> None:
    where = "DigimonEvo"
    writer.u32(field(tree, "DigimonID", where))
    writer.u32(field(tree, "BattleEvoType", where))
    objects = tree.get("EvolveObj")
    if not isinstance(objects, list):
        raise FormatError(f"{where}: 'EvolveObj' must be a list")
    writer.i32(len(objects))
    for obj in objects:
        _write_evo_obj(writer, obj)


def _read_battle_evo(reader: Reader) -> dict[str, Any]:
    record: dict[str, Any] = {"MaxEP": reader.u16()}
    record["Element"] = [
        {
            "Enable": reader.u8(),
            "_pad0": reader.u8(),
            "EvolStep": reader.u16(),
            "ReqEvoEP": reader.u16(),
            "DecEP": reader.u16(),
        }
        for _ in range(BATTLE_EVO_ELEMENT_CNT)
    ]
    return record


def _write_battle_evo(writer: Writer, record: dict[str, Any]) -> None:
    where = "BattleEvo"
    writer.u16(field(record, "MaxEP", where))
    elements = record.get("Element")
    if not isinstance(elements, list) or len(elements) != BATTLE_EVO_ELEMENT_CNT:
        raise FormatError(
            f"{where}: 's_Element' must be a list of {BATTLE_EVO_ELEMENT_CNT} entries"
        )
    for element in elements:
        writer.u8(field(element, "Enable", where))
        writer.u8(field(element, "_pad0", where))
        writer.u16(field(element, "EvolStep", where))
        writer.u16(field(element, "ReqEvoEP", where))
        writer.u16(field(element, "DecEP", where))


class DigimonEvoCodec(Codec):
    name = "DigimonEvo"
    filenames = ("digimonevo",)
    sections = ("DigimonEvo", "BattleEvo")
    record_tags = {"DigimonEvo": "DigimonEvolve", "BattleEvo": "BattleEvo"}

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        sections = {"DigimonEvo": read_records(reader, _read_tree)}
        sections["BattleEvo"] = read_records(reader, _read_battle_evo)
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": sections}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        write_records(writer, self._items(sections, "DigimonEvo"), _write_tree)
        write_records(writer, self._items(sections, "BattleEvo"), _write_battle_evo)
        return writer.getvalue()


