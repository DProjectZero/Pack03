"""``Achieve.bin`` -- achievement definitions and their display groups.

Ported from ``reference/csharp/Achieve.cs``.  The file has **no leading count**
for its first table::

    AchieveUnknow  18 * (s_szName [64 byte UTF-16 ReadZString], s_listChild int32)
    Achieve        count, then per record
                   s_nQuestID, s_nIcon (int32), s_nPoint (u16),
                   s_bDisplay, s_bDisplay2 (byte),
                   s_szName [128 bytes], s_szComment [512 bytes],
                   s_szTitle [128 bytes]   (UTF-16 ReadZString each)
                   s_nGroup, s_nSubGroup, s_nType, s_nBuffCode (int32)

``AchieveUnknow`` is 18 records because the C# reader hardcodes ``dcount = 18``
("parte sem funçao alguma"), so ``compile`` insists on exactly 18 -- with any
other number the second table would start at the wrong offset.
"""

from __future__ import annotations

from typing import Any, Sequence

from ..binary import FormatError, Reader, UTF16, Writer
from ..codec import Codec, read_records, write_records
from ..fields import read_fields, write_fields

#: ``ReadsINFOFromBinary`` always consumes 18 of these, there is no count.
UNKNOWN_COUNT = 18
UNKNOWN_NAME_BYTES = 32 * 2

ACHIEVE_HEAD_FIELDS = [
    ("s_nQuestID", "i32"),
    ("s_nIcon", "i32"),
    ("s_nPoint", "u16"),
    ("s_bDisplay", "u8"),
    ("s_bDisplay2", "u8"),
]

#: (json name, buffer size in bytes) of the UTF-16 ``ReadZString`` fields.
ACHIEVE_STRINGS: Sequence[tuple[str, int]] = (
    ("s_szName", 64 * 2),
    ("s_szComment", 256 * 2),
    ("s_szTitle", 64 * 2),
)

ACHIEVE_TAIL_FIELDS = [
    ("s_nGroup", "i32"),
    ("s_nSubGroup", "i32"),
    ("s_nType", "i32"),
    ("s_nBuffCode", "i32"),
]


def _read_unknown(reader: Reader) -> dict[str, Any]:
    record = {"s_szName": reader.zstring(UTF16, UNKNOWN_NAME_BYTES)}
    record["s_listChild"] = reader.i32()
    return record


def _write_unknown(writer: Writer, record: dict[str, Any]) -> None:
    writer.zstring(record["s_szName"], UTF16, UNKNOWN_NAME_BYTES)
    writer.i32(record["s_listChild"])


def _read_achieve(reader: Reader) -> dict[str, Any]:
    record = read_fields(reader, ACHIEVE_HEAD_FIELDS)
    for name, size in ACHIEVE_STRINGS:
        record[name] = reader.zstring(UTF16, size)
    record.update(read_fields(reader, ACHIEVE_TAIL_FIELDS))
    return record


def _write_achieve(writer: Writer, record: dict[str, Any]) -> None:
    write_fields(writer, ACHIEVE_HEAD_FIELDS, record)
    for name, size in ACHIEVE_STRINGS:
        writer.zstring(record[name], UTF16, size)
    write_fields(writer, ACHIEVE_TAIL_FIELDS, record)


class AchieveCodec(Codec):
    name = "Achieve"
    filenames = ("achieve",)
    sections = ("AchieveUnknow", "Achieve")
    record_tags = {"AchieveUnknow": "sINFO", "Achieve": "AchieveSINFO"}

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        sections = {
            "AchieveUnknow": [_read_unknown(reader) for _ in range(UNKNOWN_COUNT)]
        }
        sections["Achieve"] = read_records(reader, _read_achieve)
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": sections}

    def encode(self, sections: dict[str, Any]) -> bytes:
        unknown = self._items(sections, "AchieveUnknow")
        if len(unknown) != UNKNOWN_COUNT:
            raise FormatError(
                f"AchieveUnknow: the file stores exactly {UNKNOWN_COUNT} records "
                f"(no count field), got {len(unknown)}"
            )
        writer = Writer()
        for record in unknown:
            _write_unknown(writer, record)
        write_records(writer, self._items(sections, "Achieve"), _write_achieve)
        return writer.getvalue()
