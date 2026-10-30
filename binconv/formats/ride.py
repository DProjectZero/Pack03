"""``Ride.bin`` -- which digimon can be ridden and what it costs.

Layout from the client (``dmz-client/LibProj/CsFileTable/Ride.h``,
``CsRide::sINFO``)::

    DWORD  s_dwDigimonID
    DWORD  s_dwChangeRide
    float  s_fMoveSpeed
    TCHAR  s_szComment[512]      1024 bytes, a fixed buffer used as a C string
    int    s_nRideType
    float  s_fAniRate_Run
    struct { int s_nItemType_S; int s_nNeedCount; } s_OpenInfo[2]

``sizeof`` is 1060 bytes, the record stride of the shipped file.  The last four
``int`` fields are the two ``s_OpenInfo`` entries (item type + needed count per
open condition); the old C# code called them ``s_nSection``/``s_nNeedCount`` and
``s_nSection_2``/``s_nNeedCount_2``.

``s_szComment`` is a fixed 1024 byte buffer, NUL padded: a value longer than 512
characters is truncated to the buffer (the client's own ``SaveBin`` copies the
``TCHAR`` array verbatim, so a full buffer has no terminator at all -- the old C#
writer had the same weakness, ``Array.Resize`` truncated it just as well).
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, UTF16, Writer
from ..codec import Codec, read_records, write_records
from ..fields import read_fields, write_fields

#: 512 UTF-16 characters -- ``ITEM_COMMENT_LEN`` in the client header.
COMMENT_BYTES = 512 * 2

RIDE_FIELDS = [
    ("s_dwDigimonID", "i32"),
    ("s_dwChangeRide", "i32"),
    ("s_fMoveSpeed", "f32"),
    ("s_szComment", ("c", UTF16, COMMENT_BYTES)),
    ("s_nRideType", "i32"),
    ("s_fAniRate_Run", "f32"),
    ("s_nSection", "i32"),
    ("s_nNeedCount", "i32"),
    ("s_nSection_2", "i32"),
    ("s_nNeedCount_2", "i32"),
]


def _read_ride(reader: Reader) -> dict[str, Any]:
    return read_fields(reader, RIDE_FIELDS)


def _write_ride(writer: Writer, record: dict[str, Any]) -> None:
    write_fields(writer, RIDE_FIELDS, record)


class RideCodec(Codec):
    name = "Ride"
    filenames = ("ride",)
    sections = ("Ride",)
    record_tags = {"Ride": "Ride"}

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        rides = read_records(reader, _read_ride)
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": {"Ride": rides}}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        write_records(writer, self._items(sections, "Ride"), _write_ride)
        return writer.getvalue()
