"""``Spirit_NPC.bin`` -- the spirit-evolution NPC table.

There is **no reader for this file in the client, server or C# converter**; the
layout below was derived from the bytes.  It reproduces the shipped 3 700-byte
file exactly: a count followed by 42 fixed 88-byte records
(``4 + 42 * 88 == 3700``), with sequentially allocated ids (75 020 .. 75 061)::

    int32  nCount                                42
    nCount x 88 bytes:
        u16    nType                             1..2
        u16    nSubType                          1..2
        u32    dwID                             75 020, 75 021, ...
        u32    nCount2                          2
        u32    dwItemCode[3]                     98 701 / 98 801 / 98 901 in the first row
        u32    dwReserved0[7]                    zero in every row
        u32    dwEvolveCode[2]                   98 700 / 98 699 in the first row
        u32    dwReserved1[3]                    zero in every row
        u32    dwFlag1                           0x00010001 in every row
        u32    dwFlag2                           0
        u32    dwFlag3                           0x00380000 in every row (56 << 16)
        u32    dwFlag4                           0

The field names are inferred: ````dwItemCode``/``dwEvolveCode`` hold item codes in
the 98 xxx range (the spirit item block), everything else is an opaque flag.
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, read_records, write_records
from ..fields import read_fields, write_fields

def _arr(name: str, kind: str, count: int) -> list[tuple[str, str]]:
    """Expand a fixed C array into individually named fields."""
    return [(f"{name}{i}", kind) for i in range(count)]


SPIRIT_NPC_FIELDS = [
    ("nType", "u16"),
    ("nSubType", "u16"),
    ("dwID", "u32"),
    ("nCount2", "u32"),
    *_arr("dwItemCode", "u32", 3),
    *_arr("dwReserved0", "u32", 7),
    *_arr("dwEvolveCode", "u32", 2),
    *_arr("dwReserved1", "u32", 3),
    ("dwFlag1", "u32"),
    ("dwFlag2", "u32"),
    ("dwFlag3", "u32"),
    ("dwFlag4", "u32"),
]


def _read_row(reader: Reader) -> dict[str, Any]:
    return read_fields(reader, SPIRIT_NPC_FIELDS)


def _write_row(writer: Writer, record: dict[str, Any]) -> None:
    write_fields(writer, SPIRIT_NPC_FIELDS, record)


class SpiritNpcCodec(Codec):
    name = "Spirit_NPC"
    filenames = ("spirit_npc", "spiritnpc")
    sections = ("SpiritNpc",)
    record_tags = {"SpiritNpc": "Npc"}

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        sections = {"SpiritNpc": read_records(reader, _read_row)}
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": sections}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        write_records(writer, self._items(sections, "SpiritNpc"), _write_row)
        return writer.getvalue()
