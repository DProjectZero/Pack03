"""``CharCreateTable.bin`` -- the character/digimon creation lists.

Ported from ``reference/csharp/CharCreateTable.cs`` and checked against the client
(``dmz-client/LibProj/CsFileTable/CharacterCreateListInfo.cpp``,
``_LoadBin``/``_LoadFilePack``)::

    int32 count, then per selectable tamer:
        int32   dwTamerID          m_dwTalbeID
        bool    m_bShow
        bool    m_bEnable
        int32   m_nSeasonType
        string  m_sVoiceFile       int32 byteCount + ASCII bytes
        int32   m_nIconIdx
        int32   CountDC            nCostumeCount
        int32[CountDC] ItemID      dwCostumeID

    int32 count, then per selectable digimon:
        int32   m_digimonID        m_dwTalbeID
        bool    d_bShow
        bool    d_bEnable
        string  m_sVoiceFile       int32 byteCount + ASCII bytes

Nothing is written with ``fwrite`` here, so there is no alignment padding: every
field is read one at a time on both sides.  ``m_sVoiceFile`` is a ``std::string``
(int32 length + bytes), not a fixed buffer, and the old reader cut it at the first
NUL (``CleanString``) -- the client keeps what the length says, so a NUL inside the
length would be dropped on re-encode (none of the shipped values has one).

No XML for this table exists in this pack, so the port is verified by the exact
round-trip plus the client read order.
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, field, read_records, write_records

TAMER_FIELDS = [
    ("TamerID", "i32"),
    ("m_bShow", "u8"),
    ("m_bEnable", "u8"),
    ("m_nSeasonType", "i32"),
]

DIGIMON_FIELDS = [
    ("m_digimonID", "i32"),
    ("d_bShow", "u8"),
    ("d_bEnable", "u8"),
]


def _read_text(reader: Reader) -> str:
    size = reader.i32()
    if size < 0 or size > (len(reader.data) - reader.pos):
        raise FormatError(
            f"{reader.name}: implausible voice size {size} at offset {reader.pos - 4}"
        )
    return reader.raw(size).decode("ascii", "replace")


def _write_text(writer: Writer, value: Any, where: str) -> None:
    if not isinstance(value, str):
        raise FormatError(f"{where} must be a string")
    data = value.encode("ascii", "replace")
    writer.i32(len(data))
    writer.raw(data)


def _read_tamer(reader: Reader) -> dict[str, Any]:
    record: dict[str, Any] = {
        "TamerID": reader.i32(),
        "m_bShow": reader.u8(),
        "m_bEnable": reader.u8(),
        "m_nSeasonType": reader.i32(),
    }
    record["m_sVoiceFile"] = _read_text(reader)
    record["m_nIconIdx"] = reader.i32()
    count = reader.i32()
    if count < 0 or count > len(reader.data):
        raise FormatError(f"{reader.name}: implausible costume count {count}")
    record["CountDC"] = count
    record["ItemID"] = [reader.i32() for _ in range(count)]
    return record


def _write_tamer(writer: Writer, record: dict[str, Any]) -> None:
    where = "CharacterList"
    writer.i32(field(record, "TamerID", where))
    writer.u8(field(record, "m_bShow", where))
    writer.u8(field(record, "m_bEnable", where))
    writer.i32(field(record, "m_nSeasonType", where))
    _write_text(writer, field(record, "m_sVoiceFile", where), f"{where}.m_sVoiceFile")
    writer.i32(field(record, "m_nIconIdx", where))
    items = record.get("ItemID")
    if not isinstance(items, list):
        raise FormatError(f"{where}: 'ItemID' must be a list")
    writer.i32(len(items))
    for item in items:
        writer.i32(item)


def _read_digimon(reader: Reader) -> dict[str, Any]:
    record: dict[str, Any] = {
        "m_digimonID": reader.i32(),
        "d_bShow": reader.u8(),
        "d_bEnable": reader.u8(),
    }
    record["m_sVoiceFile"] = _read_text(reader)
    return record


def _write_digimon(writer: Writer, record: dict[str, Any]) -> None:
    where = "DigimonList"
    writer.i32(field(record, "m_digimonID", where))
    writer.u8(field(record, "d_bShow", where))
    writer.u8(field(record, "d_bEnable", where))
    _write_text(writer, field(record, "m_sVoiceFile", where), f"{where}.m_sVoiceFile")


class CharCreateTableCodec(Codec):
    name = "CharCreateTable"
    filenames = ("charcreatetable",)
    sections = ("CharacterList", "DigimonList")
    record_tags = {"CharacterList": "Character", "DigimonList": "Digimon"}

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        sections = {"CharacterList": read_records(reader, _read_tamer)}
        sections["DigimonList"] = read_records(reader, _read_digimon)
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": sections}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        write_records(writer, self._items(sections, "CharacterList"), _write_tamer)
        write_records(writer, self._items(sections, "DigimonList"), _write_digimon)
        return writer.getvalue()
