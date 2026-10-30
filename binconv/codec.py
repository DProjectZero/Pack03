"""Shared plumbing for the per-format codecs.

Every ``.bin`` file type is implemented by a :class:`Codec` subclass that turns
the raw bytes into a JSON friendly structure ("sections") and back.  ``decode``
returns::

    {
      "format": "Ride",
      "sections": {
        "Ride": [ {"s_dwDigimonID": 51001, ...}, ... ]
      }
    }

The command line tool writes one JSON file per section, so ``Ride.bin`` becomes
``json/Ride/Ride.json`` while ``ItemList.bin`` becomes a folder with sixteen
files (``json/ItemList/ItemList.json``, ``json/ItemList/ItemTap.json``, ...).
Section names match the XML documents the original tool produced, so the old
``PROGRAM/XML`` tree stays comparable.  Record counts are *not* stored: they are
derived from the length of the arrays.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable, Sequence

from .binary import FormatError, Reader, Writer


class Codec:
    """Base class for a ``.bin`` <-> JSON converter."""

    #: Name used in ``--only``, in the JSON ``format`` field and for diagnostics.
    name: str = ""
    #: Section (XML document) names this codec produces, in output order.
    sections: Sequence[str] = ()
    #: ``.bin``/``.dat`` file names this codec understands (lower case stems).
    filenames: Sequence[str] = ()
    #: File name used by ``compile``; defaults to ``<name>.bin``.
    output_name: str = ""
    #: Repeated XML element holding each section's records, for the tools that
    #: compare against ``PROGRAM/XML`` (``{"ItemList": "Item"}`` style).
    record_tags: dict[str, str] = {}

    @property
    def bin_name(self) -> str:
        return self.output_name or f"{self.name}.bin"

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        raise NotImplementedError

    def encode(self, sections: dict[str, Any]) -> bytes:
        raise NotImplementedError

    # -- helpers --------------------------------------------------------
    @staticmethod
    def _items(sections: dict[str, Any], name: str) -> list[dict[str, Any]]:
        try:
            value = sections[name]
        except KeyError:
            raise FormatError(f"missing section {name!r} (expected one of: "
                              f"{', '.join(sorted(sections))})") from None
        if not isinstance(value, list):
            raise FormatError(f"section {name!r} must be a list of records")
        return value


def read_records(reader: Reader, decode_record: Callable[[Reader], dict[str, Any]]) -> list[dict[str, Any]]:
    """Read ``int32 count`` followed by *count* records."""

    count = reader.i32()
    if count < 0:
        raise FormatError(f"{reader.name}: negative record count ({count}) at offset {reader.pos - 4}")
    if count > (len(reader.data) - reader.pos):
        raise FormatError(
            f"{reader.name}: implausible record count {count} at offset {reader.pos - 4}"
        )
    return [decode_record(reader) for _ in range(count)]


def write_records(
    writer: Writer,
    records: Iterable[dict[str, Any]],
    encode_record: Callable[[Writer, dict[str, Any]], None],
) -> None:
    """Write ``int32 count`` followed by the records."""

    items = list(records)
    writer.i32(len(items))
    for item in items:
        encode_record(writer, item)


def read_fixed_records(
    reader: Reader, count: int, decode_record: Callable[[Reader], dict[str, Any]]
) -> list[dict[str, Any]]:
    """Read *count* records without a leading count field."""

    return [decode_record(reader) for _ in range(count)]


def field(record: dict[str, Any], name: str, where: str = "record") -> Any:
    """Fetch a required JSON field with a helpful error message."""

    try:
        return record[name]
    except KeyError:
        raise FormatError(f"{where}: missing required field {name!r}") from None


def record_list(record: dict[str, Any], name: str, where: str = "record") -> list[Any]:
    """Fetch a required JSON list field with a helpful error message."""

    value = field(record, name, where)
    if not isinstance(value, list):
        raise FormatError(f"{where}: {name!r} must be a list")
    return value


CHUNK = 65536


def compare_roundtrip(original: bytes, reencoded: bytes) -> tuple[str, int]:
    """Classify a decode -> encode round-trip.

    Returns ``(status, differing_bytes)`` where status is:

    ``"exact"``     byte for byte identical.
    ``"padding"``   only bytes we wrote as ``0x00`` differ, i.e. the original
                    file held leftovers in unused string padding which the
                    reader discards by design.  Recompiles are still valid.
    ``"mismatch"``  real differences (or a different length).
    """

    if original == reencoded:
        return ("exact", 0)
    if len(original) != len(reencoded):
        return ("mismatch", abs(len(original) - len(reencoded)))

    padding = 0
    for base in range(0, len(original), CHUNK):
        left = original[base : base + CHUNK]
        right = reencoded[base : base + CHUNK]
        if left == right:
            continue
        for index in range(len(left)):
            if left[index] == right[index]:
                continue
            if right[index] != 0:
                return ("mismatch", padding + 1)
            padding += 1
    return ("padding", padding)

