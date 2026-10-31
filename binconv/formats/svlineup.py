"""``SvLineUp.bin`` -- the PvP "survival" line-up (the five Demon Lords).

There is **no reader for this file in the client, server or C# converter** — it is
an orphan written by an older tool build.  The layout below was derived from the
bytes themselves and reproduces the shipped 364-byte file exactly::

    int32  nCount                        5
    nCount x 72 bytes:                   (4 + 5 * 72 == 364)
        int    nSlot                    0-based slot index, 0..4
        int    nOrder                   line-up priority (5, 4, 3, 1, 2)
        TCHAR  szName[32]               the boss name, e.g. "Barbamon"

The names are the Demon Lords whose banner the survival line-up shows:
Barbamon, Beelzemon, Lilithmon, Leviamon, Lucemon.
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, read_records, write_records
from ..fields import read_fields, write_fields

FT_LINEUP_NAME_LEN = 32

LINEUP_FIELDS = [
    ("nSlot", "i32"),
    ("nOrder", "i32"),
    ("szName", ("w", FT_LINEUP_NAME_LEN)),
]


def _read_row(reader: Reader) -> dict[str, Any]:
    return read_fields(reader, LINEUP_FIELDS)


def _write_row(writer: Writer, record: dict[str, Any]) -> None:
    write_fields(writer, LINEUP_FIELDS, record)


class SvLineUpCodec(Codec):
    name = "SvLineUp"
    filenames = ("svlineup",)
    sections = ("SvLineUp",)
    record_tags = {"SvLineUp": "LineUp"}

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        sections = {"SvLineUp": read_records(reader, _read_row)}
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": sections}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        write_records(writer, self._items(sections, "SvLineUp"), _write_row)
        return writer.getvalue()
