"""``UIText.bin`` -- the localised UI strings.

Ported from ``reference/csharp/UIText.cs``::

    count, then per record: int64 ID_Maybe, int32 characters, UTF-16 text

The reader does **not** cut the text at a NUL (unlike most other formats), so the
JSON text is the raw buffer content and re-encoding keeps the same byte count.
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, read_records, write_records
from ..fields import read_text, write_text


def _read_text_record(reader: Reader) -> dict[str, Any]:
    return {"ID": reader.i64(), "Text": read_text(reader)}


def _write_text_record(writer: Writer, record: dict[str, Any]) -> None:
    writer.i64(record["ID"])
    write_text(writer, record["Text"])


class UITextCodec(Codec):
    name = "UIText"
    filenames = ("uitext",)
    sections = ("UIText",)
    record_tags = {"UIText": "UIText"}

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        records = read_records(reader, _read_text_record)
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": {"UIText": records}}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        write_records(writer, self._items(sections, "UIText"), _write_text_record)
        return writer.getvalue()
