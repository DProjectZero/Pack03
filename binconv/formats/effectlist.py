"""``EffectList.bin`` -- item code to equip-effect file name.

Ported from the client (``CsFileTable/EffectMng.cpp``,
``CsEffectMng::_LoadBin`` lines 104-116; the file name is a literal, the manager
has no ``*_BIN`` define)::

    int32 count, then per record:
        DWORD      dwItemCode
        std::string fileName      int32 byteCount + ASCII bytes

Nothing is written with ``fwrite``, so there is no alignment padding.
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, field, read_records, write_records


def _read_text(reader: Reader) -> str:
    size = reader.i32()
    if size < 0 or size > (len(reader.data) - reader.pos):
        raise FormatError(
            f"{reader.name}: implausible name size {size} at offset {reader.pos - 4}"
        )
    return reader.raw(size).decode("ascii", "replace")


def _write_text(writer: Writer, value: Any, where: str) -> None:
    if not isinstance(value, str):
        raise FormatError(f"{where} must be a string")
    data = value.encode("ascii", "replace")
    writer.i32(len(data))
    writer.raw(data)


def _read_effect(reader: Reader) -> dict[str, Any]:
    record = {"ItemCode": reader.u32()}
    record["fileName"] = _read_text(reader)
    return record


def _write_effect(writer: Writer, record: dict[str, Any]) -> None:
    writer.u32(field(record, "ItemCode", "EffectList"))
    _write_text(writer, field(record, "fileName", "EffectList"), "EffectList.fileName")


class EffectListCodec(Codec):
    name = "EffectList"
    filenames = ("effectlist",)
    sections = ("EffectList",)
    record_tags = {"EffectList": "Effect"}

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        records = read_records(reader, _read_effect)
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": {"EffectList": records}}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        write_records(writer, self._items(sections, "EffectList"), _write_effect)
        return writer.getvalue()
