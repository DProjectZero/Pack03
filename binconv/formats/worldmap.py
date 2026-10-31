"""``WorldMap.bin`` -- the world map and area map tables (one file, two sections).

Ported from ``reference/csharp/WorldMap.cs`` and checked against the client
(``dmz-client/LibProj/CsFileTable/WorldMap.h``, ``CsWorldMap::sINFO``)::

    WorldMapInfo:  count, then per record:
        USHORT s_nID
        TCHAR  s_szName[48]         96 bytes
        TCHAR  s_szComment[256]     512 bytes
        USHORT s_nWorldType         (the client declares a BYTE + padding)
        USHORT s_nUI_X, s_nUI_Y

    AreaMapInfo:   count, then per record:
        USHORT d_nMapID
        TCHAR  d_szName[48]         96 bytes
        TCHAR  d_szComment[256]     512 bytes
        BYTE   d_nAreaType, d_nFieldType
        int    d_nFTDetail
        USHORT d_nUI_X, d_nUI_Y
        float  d_fGaussianBlur[3]

Both sections are exported as separate documents (``WorldMap.xml``,
``AreaMap.xml``), so they are separate JSON sections.  The strings are fixed
``TCHAR`` buffers with NUL padding, read as C strings; ``d_fGaussianBlur`` is the
only nested value (three floats, exported as ``<item>`` children).
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, read_records, write_records
from ..fields import read_fields, write_fields

WORLD_INFO_FIELDS = [
    ("ID", "u16"),
    ("Name", ("w", 48)),
    ("Comment", ("w", 256)),
    ("WorldType", "u16"),
    ("UI_X", "u16"),
    ("UI_Y", "u16"),
]

AREA_FIELDS = [
    ("d_nMapID", "u16"),
    ("d_szName", ("w", 48)),
    ("d_szComment", ("w", 256)),
    ("d_nAreaType", "u8"),
    ("d_nFieldType", "u8"),
    ("d_nFTDetail", "i32"),
    ("d_nUI_X", "u16"),
    ("d_nUI_Y", "u16"),
]

#: ``float d_fGaussianBlur[3]``
BLUR_COUNT = 3


def _read_world(reader: Reader) -> dict[str, Any]:
    return read_fields(reader, WORLD_INFO_FIELDS)


def _write_world(writer: Writer, record: dict[str, Any]) -> None:
    write_fields(writer, WORLD_INFO_FIELDS, record)


def _read_area(reader: Reader) -> dict[str, Any]:
    record = read_fields(reader, AREA_FIELDS)
    record["d_fGaussianBlur"] = [reader.f32() for _ in range(BLUR_COUNT)]
    return record


def _write_area(writer: Writer, record: dict[str, Any]) -> None:
    write_fields(writer, AREA_FIELDS, record)
    blur = record.get("d_fGaussianBlur")
    if not isinstance(blur, list) or len(blur) != BLUR_COUNT:
        raise FormatError(
            f"AreaMapInfo {record.get('d_nMapID')}: expected {BLUR_COUNT} "
            "d_fGaussianBlur values"
        )
    for value in blur:
        writer.f32(value)


class WorldMapCodec(Codec):
    name = "WorldMap"
    filenames = ("worldmap",)
    sections = ("WorldMapInfo", "AreaMapInfo")
    record_tags = {"WorldMapInfo": "WorldMapInfo", "AreaMapInfo": "AreaMapInfo"}

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        sections = {"WorldMapInfo": read_records(reader, _read_world)}
        sections["AreaMapInfo"] = read_records(reader, _read_area)
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": sections}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        write_records(writer, self._items(sections, "WorldMapInfo"), _write_world)
        write_records(writer, self._items(sections, "AreaMapInfo"), _write_area)
        return writer.getvalue()
