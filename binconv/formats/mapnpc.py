"""``MapNpc.bin`` -- npc spawn points on every map.

Ported from the original converter (``MapNpc.cs``).  Fixed 20 byte records::

    NpcID, MapID, InitPosX, InitPosY, s_fRotation (float)

The old XML export prints ``MapID`` **before** ``NpcID`` while the reader takes
``NpcID`` first; JSON keeps the read order (the XML comparison matches fields by
element name, so both agree).
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, read_records, write_records
from ..fields import read_fields, write_fields

MAP_NPC_FIELDS = [
    ("NpcID", "i32"),
    ("MapID", "i32"),
    ("InitPosX", "i32"),
    ("InitPosY", "i32"),
    ("Rotation", "f32"),
]


def _read_npc(reader: Reader) -> dict[str, Any]:
    return read_fields(reader, MAP_NPC_FIELDS)


def _write_npc(writer: Writer, record: dict[str, Any]) -> None:
    write_fields(writer, MAP_NPC_FIELDS, record)


class MapNpcCodec(Codec):
    name = "MapNpc"
    filenames = ("mapnpc",)
    sections = ("MapNpc",)
    record_tags = {"MapNpc": "MapNPC"}

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        records = read_records(reader, _read_npc)
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": {"MapNpc": records}}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        write_records(writer, self._items(sections, "MapNpc"), _write_npc)
        return writer.getvalue()
