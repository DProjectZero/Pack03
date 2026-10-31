"""``MapRegion.bin`` -- the region, evolution-limit and buff zones of every map.

Layout from the client, ``CsFileTable/MapRegion.h``
(``CsMapRegion::sINFO``, ``CsMap_LimitEvo::sINFO``, ``CsMap_BuffRegion::sINFO``)
written per group by ``MapRegionMng.cpp``.  Three counted group sections follow
each other; every group is ``int32 count`` followed by its records::

    CsMapRegion::sINFO          604 bytes
        DWORD  s_dwMapID
        int    s_nCenterX, s_nCenterY, s_nRadius
        TCHAR  s_szDiscript[128]        256 bytes
        TCHAR  s_szDiscript_Eng[128]    256 bytes
        char   s_cBGSound[64]
        USHORT s_nFatigue_Type, s_nFatigue_DeBuff,
               s_nFatigue_StartTime, s_nFatigue_AddTime
        SHORT  s_nFatigue_AddPoint
        <2 bytes of struct tail padding>

    CsMap_LimitEvo::sINFO        16 bytes
        DWORD  s_dwMapID, int s_nCenterX, s_nCenterY, s_nRadius

    CsMap_BuffRegion::sINFO      52 bytes
        int regionIdx, DWORD mapidx, int centerx, centery, radius, act,
            buffidx, time, layerno, applytype, requirement_1, requirement_2,
            objuniqid

The shipped file holds 88 region groups (435 rows), 8 limit groups (21 rows) and
10 buff groups (65 rows); the decode ends exactly at EOF.  Group counts are not
stored in the JSON: they are derived from the number of groups.
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, field
from ..fields import read_fields, write_fields

REGION_FIELDS = [
    ("MapID", "u32"),
    ("CenterX", "i32"),
    ("CenterY", "i32"),
    ("Radius", "i32"),
    ("Discript", ("w", 128)),
    ("Discript_Eng", ("w", 128)),
    ("BGSound", ("c", "ascii", 64)),
    ("Fatigue_Type", "u16"),
    ("Fatigue_DeBuff", "u16"),
    ("Fatigue_StartTime", "u16"),
    ("Fatigue_AddTime", "u16"),
    ("Fatigue_AddPoint", "i16"),
    ("_pad0", "u16"),
]

LIMIT_EVO_FIELDS = [
    ("MapID", "u32"),
    ("CenterX", "i32"),
    ("CenterY", "i32"),
    ("Radius", "i32"),
]

BUFF_REGION_FIELDS = [
    ("regionIdx", "i32"),
    ("mapidx", "u32"),
    ("centerx", "i32"),
    ("centery", "i32"),
    ("radius", "i32"),
    ("act", "i32"),
    ("buffidx", "i32"),
    ("time", "i32"),
    ("layerno", "i32"),
    ("applytype", "i32"),
    ("requirement_1", "i32"),
    ("requirement_2", "i32"),
    ("objuniqid", "i32"),
]

SECTIONS = {
    "Region": REGION_FIELDS,
    "LimitEvo": LIMIT_EVO_FIELDS,
    "BuffRegion": BUFF_REGION_FIELDS,
}


def _read_groups(reader: Reader, name: str, fields: list[tuple[str, Any]]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for _ in range(_count(reader, f"{name} group")):
        count = _count(reader, f"{name} record")
        groups.append({"Info": [read_fields(reader, fields) for _ in range(count)]})
    return groups


def _write_groups(
    writer: Writer, name: str, fields: list[tuple[str, Any]], groups: list[Any]
) -> None:
    writer.i32(len(groups))
    for group in groups:
        records = group.get("Info") if isinstance(group, dict) else None
        if not isinstance(records, list):
            raise FormatError(f"{name}: group must be an object with an 'Info' list")
        writer.i32(len(records))
        for record in records:
            write_fields(writer, fields, record)


def _count(reader: Reader, what: str) -> int:
    count = reader.i32()
    if count < 0 or count > (len(reader.data) - reader.pos):
        raise FormatError(
            f"{reader.name}: implausible {what} count {count} at offset {reader.pos - 4}"
        )
    return count


class MapRegionCodec(Codec):
    name = "MapRegion"
    filenames = ("mapregion",)
    sections = ("Region", "LimitEvo", "BuffRegion")
    record_tags = {"Region": "MapRegion", "LimitEvo": "MapLimitEvo", "BuffRegion": "MapBuffRegion"}

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        sections = {
            name: _read_groups(reader, name, fields) for name, fields in SECTIONS.items()
        }
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": sections}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        for name, fields in SECTIONS.items():
            _write_groups(writer, name, fields, self._items(sections, name))
        return writer.getvalue()
