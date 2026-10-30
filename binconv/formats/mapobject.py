"""``MapObject.bin`` -- the gimmick objects (switches, quest gates) per map.

Ported from ``reference/csharp/MapObject.cs``.  Three nested tables::

    count
    per map:  MapId, Size, then Size * MapSourceObject
              ObjectId, ObjectCount, then ObjectCount * OrderObject
              OrderId, FactorSize, then FactorSize * Object
              s_nOpenType, s_nFactorCnt, s_nFactor

The list keys are the XML element names (``MapSourceObject``, ``OrderObject``,
``Object``) because the exporter repeats them directly under their parent; the
three count fields (``Size``, ``ObjectCount``, ``FactorSize``) are the lengths of
those lists and are therefore derived on write.

The old writer swaps ``s_nFactor`` and ``s_nFactorCnt`` (the reader takes the
count first); JSON keeps the read order.
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, field, read_records, record_list, write_records


def _read_object(reader: Reader) -> dict[str, Any]:
    record = {"s_nOpenType": reader.i32(), "s_nFactorCnt": reader.i32()}
    record["s_nFactor"] = reader.i32()
    return record


def _write_object(writer: Writer, record: dict[str, Any]) -> None:
    writer.i32(field(record, "s_nOpenType", "Object"))
    writer.i32(field(record, "s_nFactorCnt", "Object"))
    writer.i32(field(record, "s_nFactor", "Object"))


def _read_order_object(reader: Reader) -> dict[str, Any]:
    record = {"OrderId": reader.i32()}
    record["Object"] = read_records(reader, _read_object)
    return record


def _write_order_object(writer: Writer, record: dict[str, Any]) -> None:
    writer.i32(field(record, "OrderId", "OrderObject"))
    write_records(writer, record_list(record, "Object", "OrderObject"), _write_object)


def _read_source_object(reader: Reader) -> dict[str, Any]:
    record = {"ObjectId": reader.i32()}
    record["OrderObject"] = read_records(reader, _read_order_object)
    return record


def _write_source_object(writer: Writer, record: dict[str, Any]) -> None:
    writer.i32(field(record, "ObjectId", "MapSourceObject"))
    write_records(
        writer, record_list(record, "OrderObject", "MapSourceObject"), _write_order_object
    )


def _read_map_object(reader: Reader) -> dict[str, Any]:
    record = {"MapId": reader.i32()}
    record["MapSourceObject"] = read_records(reader, _read_source_object)
    return record


def _write_map_object(writer: Writer, record: dict[str, Any]) -> None:
    writer.i32(field(record, "MapId", "MapObject"))
    write_records(
        writer, record_list(record, "MapSourceObject", "MapObject"), _write_source_object
    )


class MapObjectCodec(Codec):
    name = "MapObject"
    filenames = ("mapobject",)
    sections = ("MapObject",)
    record_tags = {"MapObject": "MapObject"}

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        records = read_records(reader, _read_map_object)
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": {"MapObject": records}}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        write_records(writer, self._items(sections, "MapObject"), _write_map_object)
        return writer.getvalue()
