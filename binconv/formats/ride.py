"""``Ride.bin`` -- which digimon can be ridden and what it costs.

Ported from ``reference/csharp/Ride.cs``.  Every record is a fixed 1060 byte
block::

    s_dwDigimonID, s_dwChangeRide, s_fMoveSpeed (float),
    s_szComment  -- ReadZString(Unicode, 512 * 2), i.e. a 1024 byte buffer,
    s_nRideType, s_fAniRate_Run (float),
    s_nSection, s_nNeedCount, s_nSection_2, s_nNeedCount_2

``s_szComment`` is written back NUL padded / truncated to 1024 bytes, exactly
like the old writer did with ``Array.Resize``.  Note that the terminator has to
fit in the buffer too: at most 510 characters can be stored, a longer text loses
its ``NUL`` run and the reader would run into the next fields (the old writer had
the same limitation).
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, UTF16, Writer
from ..codec import Codec, read_records, write_records
from ..fields import read_fields, write_fields

#: 512 UTF-16 characters, the size the C# reader passes to ``ReadZString``.
COMMENT_BYTES = 512 * 2

RIDE_FIELDS = [
    ("s_dwDigimonID", "i32"),
    ("s_dwChangeRide", "i32"),
    ("s_fMoveSpeed", "f32"),
    ("s_szComment", ("z", UTF16, COMMENT_BYTES)),
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
