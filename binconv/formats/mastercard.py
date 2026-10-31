"""``MasterCard.bin`` -- the seal master cards, leader abilities and UI asset paths.

Layout from the client, ``Master_Card.h`` / ``Master_CardMng.h`` read by
``Master_CardMng.cpp::_LoadBin`` (lines 645-748) and ``LoadBinFilter``
(lines 938-956).  Eight sections::

    1) CsMaster_Card::sINFO                     268 bytes
        DWORD s_nID
        TCHAR s_szName[64]                            128 bytes
        DWORD s_nDigimonID
        USHORT s_nIcon
        <2 bytes of struct padding>
        DWORD s_nLeader
        USHORT s_nScale
        <2 bytes of struct padding>
        GradeInfo s_stGradeInfo[6]                     20 bytes each
            DWORD  s_nItem
            USHORT s_nIcon, s_nMax, s_nIdentiQuantity
            USHORT s_nEff1, s_nEff1val, s_nEff2, s_nEff2val
            <2 bytes of struct tail padding>

    2) CsMaster_CardLeader::sINFO                44 bytes
        DWORD  s_nID, s_nDigimonID
        USHORT s_nPetID
        <2 bytes of struct padding>
        DWORD  s_nAni1, s_nAni2, s_nSpecial1, s_nSpecial2
        DWORD  s_nAbil1, s_nAbil2, s_nAbil3, s_nAbil4

    3) CsMaster_CardLeaderAbility::sINFO         40 bytes
        USHORT s_nID
        <2 bytes of struct padding>
        sTerms s_stTerms[3]                        12 bytes each
            DWORD s_nterm, s_ntermval, s_nEff

    4) neSealMaster::sDigimonImgPath
        DWORD  s_nDigimon
        string s_szDigimonSealImgPath              int32 length + bytes

    5) neSealMaster::sPlatePath
        int    s_nID
        wstring s_szName                           int32 chars + UTF-16LE
        string s_szNifFilePath
        string s_szGradeBackImagePath

    6) neSealMaster::sElemental        int s_nType + string s_nFilePath
    7) neSealMaster::sAttribtue        int s_nType + string s_nFilePath
    8) CsMaster_Filter::sINFO          DWORD s_nMapGroupID, s_nMapAreaID, s_nSealItemID

The shipped file holds 95 cards, 95 leaders, 2 leader abilities, 96 digimon image
paths (the first row is a ``digimon 0`` / ``"0"`` placeholder), 6 plate paths, 1
elemental, 1 attribute and 6 filter rows (41 200 bytes), which decodes exactly to
EOF.  Note the record sizes: ``sINFO`` of the leader is 44 bytes but the ability
record is only 40 -- a 44-byte ability stride misreads the following section by
one byte per row.
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, field, read_records, write_records
from ..fields import read_fields, write_fields

CARD_GRADE_COUNT = 6
LEADER_ABILITY_TERMS = 3

CARD_FIELDS = [
    ("ID", "u32"),
    ("Name", ("w", 64)),
    ("DigimonID", "u32"),
    ("Icon", "u16"),
    ("_pad0", "u16"),
    ("Leader", "u32"),
    ("Scale", "u16"),
    ("_pad1", "u16"),
]

GRADE_FIELDS = [
    ("Item", "u32"),
    ("Icon", "u16"),
    ("Max", "u16"),
    ("IdentiQuantity", "u16"),
    ("Eff1", "u16"),
    ("Eff1val", "u16"),
    ("Eff2", "u16"),
    ("Eff2val", "u16"),
    ("_pad0", "u16"),
]

LEADER_FIELDS = [
    ("ID", "u32"),
    ("DigimonID", "u32"),
    ("PetID", "u16"),
    ("_pad0", "u16"),
    ("Ani1", "u32"),
    ("Ani2", "u32"),
    ("Special1", "u32"),
    ("Special2", "u32"),
    ("Abil1", "u32"),
    ("Abil2", "u32"),
    ("Abil3", "u32"),
    ("Abil4", "u32"),
]

ABILITY_FIELDS = [("ID", "u16"), ("_pad0", "u16")]

TERM_FIELDS = [("term", "u32"), ("termval", "u32"), ("Eff", "u32")]

TEXT_ENCODING = "cp949"


def _read_text(reader: Reader) -> str:
    length = reader.i32()
    if length < 0 or length > (len(reader.data) - reader.pos):
        raise FormatError(
            f"{reader.name}: implausible string length {length} at offset {reader.pos - 4}"
        )
    return reader.raw(length).decode(TEXT_ENCODING, "replace")


def _write_text(writer: Writer, value: Any, where: str) -> None:
    if not isinstance(value, str):
        raise FormatError(f"{where}: expected a string")
    data = value.encode(TEXT_ENCODING)
    writer.i32(len(data))
    writer.raw(data)


def _read_wide(reader: Reader) -> str:
    length = reader.i32()
    if length < 0 or length * 2 > (len(reader.data) - reader.pos):
        raise FormatError(
            f"{reader.name}: implausible wide string length {length} "
            f"at offset {reader.pos - 4}"
        )
    return reader.wstring(length)


def _write_wide(writer: Writer, value: Any, where: str) -> None:
    if not isinstance(value, str):
        raise FormatError(f"{where}: expected a string")
    writer.i32(len(value))
    writer.wstring(value, len(value))


def _read_card(reader: Reader) -> dict[str, Any]:
    card = read_fields(reader, CARD_FIELDS)
    card["Grade"] = [read_fields(reader, GRADE_FIELDS) for _ in range(CARD_GRADE_COUNT)]
    return card


def _write_card(writer: Writer, card: dict[str, Any]) -> None:
    where = "MasterCard"
    write_fields(writer, CARD_FIELDS, card)
    grades = card.get("Grade")
    if not isinstance(grades, list) or len(grades) != CARD_GRADE_COUNT:
        raise FormatError(f"{where}: 'Grade' must be a list of {CARD_GRADE_COUNT}")
    for grade in grades:
        write_fields(writer, GRADE_FIELDS, grade)


def _read_leader(reader: Reader) -> dict[str, Any]:
    return read_fields(reader, LEADER_FIELDS)


def _write_leader(writer: Writer, leader: dict[str, Any]) -> None:
    write_fields(writer, LEADER_FIELDS, leader)


def _read_ability(reader: Reader) -> dict[str, Any]:
    ability = read_fields(reader, ABILITY_FIELDS)
    ability["Term"] = [read_fields(reader, TERM_FIELDS) for _ in range(LEADER_ABILITY_TERMS)]
    return ability


def _write_ability(writer: Writer, ability: dict[str, Any]) -> None:
    where = "LeaderAbility"
    write_fields(writer, ABILITY_FIELDS, ability)
    terms = ability.get("Term")
    if not isinstance(terms, list) or len(terms) != LEADER_ABILITY_TERMS:
        raise FormatError(f"{where}: 'Term' must be a list of {LEADER_ABILITY_TERMS}")
    for term in terms:
        write_fields(writer, TERM_FIELDS, term)


def _read_image_path(reader: Reader) -> dict[str, Any]:
    return {"Digimon": reader.u32(), "DigimonSealImgPath": _read_text(reader)}


def _write_image_path(writer: Writer, record: dict[str, Any]) -> None:
    where = "DigimonImgPath"
    writer.u32(field(record, "Digimon", where))
    _write_text(writer, field(record, "DigimonSealImgPath", where), where)


def _read_plate_path(reader: Reader) -> dict[str, Any]:
    return {
        "ID": reader.i32(),
        "Name": _read_wide(reader),
        "NifFilePath": _read_text(reader),
        "GradeBackImagePath": _read_text(reader),
    }


def _write_plate_path(writer: Writer, record: dict[str, Any]) -> None:
    where = "PlatePath"
    writer.i32(field(record, "ID", where))
    _write_wide(writer, field(record, "Name", where), where)
    _write_text(writer, field(record, "NifFilePath", where), where)
    _write_text(writer, field(record, "GradeBackImagePath", where), where)


def _read_type_path(reader: Reader) -> dict[str, Any]:
    return {"Type": reader.i32(), "FilePath": _read_text(reader)}


def _write_type_path(writer: Writer, record: dict[str, Any]) -> None:
    where = "TypePath"
    writer.i32(field(record, "Type", where))
    _write_text(writer, field(record, "FilePath", where), where)


def _read_filter(reader: Reader) -> dict[str, Any]:
    return {
        "MapGroupID": reader.u32(),
        "MapAreaID": reader.u32(),
        "SealItemID": reader.u32(),
    }


def _write_filter(writer: Writer, record: dict[str, Any]) -> None:
    where = "MasterFilter"
    for name in ("MapGroupID", "MapAreaID", "SealItemID"):
        writer.u32(field(record, name, where))


class MasterCardCodec(Codec):
    name = "MasterCard"
    filenames = ("mastercard", "master_card")
    sections = (
        "MasterCard",
        "Leader",
        "LeaderAbility",
        "DigimonImgPath",
        "PlatePath",
        "Elemental",
        "Attribute",
        "Filter",
    )
    record_tags = {
        "MasterCard": "Card",
        "Leader": "Leader",
        "LeaderAbility": "Ability",
        "DigimonImgPath": "ImagePath",
        "PlatePath": "PlatePath",
        "Elemental": "Elemental",
        "Attribute": "Attribute",
        "Filter": "Filter",
    }

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        sections = {"MasterCard": read_records(reader, _read_card)}
        sections["Leader"] = read_records(reader, _read_leader)
        sections["LeaderAbility"] = read_records(reader, _read_ability)
        sections["DigimonImgPath"] = read_records(reader, _read_image_path)
        sections["PlatePath"] = read_records(reader, _read_plate_path)
        sections["Elemental"] = read_records(reader, _read_type_path)
        sections["Attribute"] = read_records(reader, _read_type_path)
        sections["Filter"] = read_records(reader, _read_filter)
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": sections}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        write_records(writer, self._items(sections, "MasterCard"), _write_card)
        write_records(writer, self._items(sections, "Leader"), _write_leader)
        write_records(writer, self._items(sections, "LeaderAbility"), _write_ability)
        write_records(writer, self._items(sections, "DigimonImgPath"), _write_image_path)
        write_records(writer, self._items(sections, "PlatePath"), _write_plate_path)
        write_records(writer, self._items(sections, "Elemental"), _write_type_path)
        write_records(writer, self._items(sections, "Attribute"), _write_type_path)
        write_records(writer, self._items(sections, "Filter"), _write_filter)
        return writer.getvalue()

