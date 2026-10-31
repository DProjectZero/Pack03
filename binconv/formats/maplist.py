"""``MapList.bin`` -- the map table.

Ported from ``reference/csharp/MapList.cs`` (``MapData.ReadMoApDataFromBinary``)
and verified against the client loader ``CsMapListMng::_LoadBin``
(``dmz-client/LibProj/CsFileTable/MapListMng.cpp``) and ``CsMapList::sINFO``
(``MapList.h``)::

    int32 count, then per record:
        DWORD   s_dwMapID
        string  s_cMapName          int32 byteCount + ASCII bytes
        string  s_cMapPath          int32 byteCount + ASCII bytes
        string  s_cBGSound          int32 byteCount + ASCII bytes
        int32   s_nWidth, s_nHeight
        wstring s_szMapDiscript_Eng int32 charCount + charCount * 2 bytes
        wstring s_szMapDiscript     int32 charCount + charCount * 2 bytes
        DWORD   s_dwResurrectionMapID
        USHORT  s_nMapRegionID, s_nFatigue_Type, s_nFatigue_DeBuff,
                s_nFatigue_StartTime, s_nFatigue_AddTime
        SHORT   s_nFatigue_AddPoint, s_nCamera_Max_Level
        bool    s_bXgConsumeType, s_bBattleTagUse

JSON uses the XML element names (``MapName``, ``FatigueType``, ...) so the
original ``MapList.xml`` compares field by field.  The ASCII fields are trimmed
like the old reader did (no shipped value needs it, so the round-trip stays
byte-exact); the two ``DWORD`` ids are unsigned.
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, field, read_records, write_records
from ..fields import read_text, write_text


def _read_ascii(reader: Reader) -> str:
    """``int32 size`` + *size* ASCII bytes, trimmed (``Encoding.ASCII...Trim()``)."""

    size = reader.i32()
    if size < 0 or size > (len(reader.data) - reader.pos):
        raise FormatError(
            f"{reader.name}: implausible string size {size} at offset {reader.pos - 4}"
        )
    return reader.raw(size).decode("ascii", "replace").strip()


def _write_ascii(writer: Writer, value: Any, where: str) -> None:
    if not isinstance(value, str):
        raise FormatError(f"{where} must be a string")
    data = value.strip().encode("ascii", "replace")
    writer.i32(len(data))
    writer.raw(data)


def _read_map(reader: Reader) -> dict[str, Any]:
    return {
        "MapID": reader.u32(),
        "MapName": _read_ascii(reader),
        "MapPath": _read_ascii(reader),
        "BGSound": _read_ascii(reader),
        "Width": reader.i32(),
        "Height": reader.i32(),
        "MapDescription_Eng": read_text(reader),
        "MapDescription": read_text(reader),
        "ResurrectionMapID": reader.u32(),
        "MapRegionID": reader.u16(),
        "FatigueType": reader.u16(),
        "FatigueDeBuff": reader.u16(),
        "FatigueStartTime": reader.u16(),
        "FatigueAddTime": reader.u16(),
        "FatigueAddPoint": reader.i16(),
        "CameraMaxLevel": reader.i16(),
        "XgConsumeType": reader.u8(),
        "BattleTagUse": reader.u8(),
    }


def _write_map(writer: Writer, record: dict[str, Any]) -> None:
    where = "MapList"
    writer.u32(field(record, "MapID", where))
    _write_ascii(writer, field(record, "MapName", where), f"{where}.MapName")
    _write_ascii(writer, field(record, "MapPath", where), f"{where}.MapPath")
    _write_ascii(writer, field(record, "BGSound", where), f"{where}.BGSound")
    writer.i32(field(record, "Width", where))
    writer.i32(field(record, "Height", where))
    write_text(writer, field(record, "MapDescription_Eng", where))
    write_text(writer, field(record, "MapDescription", where))
    writer.u32(field(record, "ResurrectionMapID", where))
    writer.u16(field(record, "MapRegionID", where))
    writer.u16(field(record, "FatigueType", where))
    writer.u16(field(record, "FatigueDeBuff", where))
    writer.u16(field(record, "FatigueStartTime", where))
    writer.u16(field(record, "FatigueAddTime", where))
    writer.i16(field(record, "FatigueAddPoint", where))
    writer.i16(field(record, "CameraMaxLevel", where))
    writer.u8(field(record, "XgConsumeType", where))
    writer.u8(field(record, "BattleTagUse", where))


class MapListCodec(Codec):
    name = "MapList"
    filenames = ("maplist",)
    sections = ("MapList",)
    record_tags = {"MapList": "Map"}

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        records = read_records(reader, _read_map)
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": {"MapList": records}}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        write_records(writer, self._items(sections, "MapList"), _write_map)
        return writer.getvalue()
