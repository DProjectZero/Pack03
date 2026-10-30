"""``MapPortal.bin`` -- every map's portals.

Ported from ``reference/csharp/Portal.cs``.  The file groups portals per map::

    count
    per group:  int32 pMapGroup, then pMapGroup * PortalInfo (15 int32 each)

``pMapGroup`` is the length of the group's ``PortalInfos`` list, so it is
derived on write instead of being stored twice.
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, read_records, record_list, write_records
from ..fields import read_fields, write_fields

PORTAL_INFO_FIELDS = [
    ("s_dwPortalID", "i32"),
    ("s_dwPortalType", "i32"),
    ("s_dwSrcMapID", "i32"),
    ("s_nSrcTargetX", "i32"),
    ("s_nSrcTargetY", "i32"),
    ("s_nSrcRadius", "i32"),
    ("s_dwDestMapID", "i32"),
    ("s_nDestTargetX", "i32"),
    ("s_nDestTargetY", "i32"),
    ("s_nDestRadius", "i32"),
    ("s_ePortalType", "i32"),
    ("s_dwUniqObjectID", "i32"),
    ("s_nPortalKindIndex", "i32"),
    ("s_nViewTargetX", "i32"),
    ("s_nViewTargetY", "i32"),
]


def _read_portal(reader: Reader) -> dict[str, Any]:
    count = reader.i32()
    if count < 0 or count > (len(reader.data) - reader.pos) // 60:
        raise FormatError(
            f"{reader.name}: implausible portal count {count} at offset {reader.pos - 4}"
        )
    return {
        "PortalInfos": [read_fields(reader, PORTAL_INFO_FIELDS) for _ in range(count)]
    }


def _write_portal(writer: Writer, record: dict[str, Any]) -> None:
    infos = record_list(record, "PortalInfos", "Portal")
    writer.i32(len(infos))
    for info in infos:
        write_fields(writer, PORTAL_INFO_FIELDS, info)


class MapPortalCodec(Codec):
    name = "MapPortal"
    filenames = ("mapportal",)
    sections = ("MapPortal",)
    record_tags = {"MapPortal": "Portal"}

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        portals = read_records(reader, _read_portal)
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": {"MapPortal": portals}}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        write_records(writer, self._items(sections, "MapPortal"), _write_portal)
        return writer.getvalue()
