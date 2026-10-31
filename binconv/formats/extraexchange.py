"""``ExtraExchange.bin`` -- the "extra" (digimon) exchange shops.

Ported from ``reference/csharp/ExtraExchange.cs``
(``ExtraExchanges.ExtraExchangesFromBinary``) and verified against the **client**
loader ``CsExtraEvolutionMng`` (``dmz-client/LibProj/CsFileTable/
ExtraEvolutionTable.cpp``, ``#define EXTRA_EXCHAGE_BIN "ExtraExchange.bin"``,
``_LoadBin``/``_LoadFilePack``/``SaveBin``).  Three nesting levels::

    int32 count, then per NPC:
        DWORD  NpcId                       dwNPCIdx
        int32  idCount, then per id:
            USHORT Id                      usExchangeType
            int32  exchangeCount, then per exchange:
                DWORD  DigimonID           dwObjectIDX
                USHORT usMaterialType      (the converter called it ``Unknow``)
                int    RequiredLevel       nNeedMaterialValue
                DWORD  Price               dwNeedMoney
                USHORT usWayType           (the converter called it ``Unknow1``)
                int32  ItemCount           -> ItemCount * MaterialData
                int32  MaterialCount       -> MaterialCount * SubMaterialData
                MaterialData: DWORD ItemId (dwMaterialIDX), int ItemCount (nCount)

Only the two fields the converter could not explain were renamed to the client's
names (``usMaterialType``/``usWayType``); the rest keeps the legible converter
names, with the client's identifier in the docstring above.

The client's ``SaveBin`` writes both counts, so a file recompiled here loads
exactly like one written by the client.  The old *converter's* writer dropped
``MaterialCount``, which desynchronised every record after the first -- the
reader (and this port) keeps the field.
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, field, read_records, write_records


def _count(reader: Reader, what: str) -> int:
    count = reader.i32()
    if count < 0 or count > len(reader.data):
        raise FormatError(
            f"{reader.name}: implausible {what} count {count} at offset {reader.pos - 4}"
        )
    return count


def _read_material(reader: Reader) -> dict[str, Any]:
    return {"ItemID": reader.u32(), "ItemCount": reader.i32()}


def _write_material(writer: Writer, record: dict[str, Any]) -> None:
    writer.u32(field(record, "ItemID", "MaterialData"))
    writer.i32(field(record, "ItemCount", "MaterialData"))


def _list(record: dict[str, Any], name: str, where: str) -> list[Any]:
    value = record.get(name)
    if not isinstance(value, list):
        raise FormatError(f"{where}: {name!r} must be a list")
    return value


def _read_exchange(reader: Reader) -> dict[str, Any]:
    record: dict[str, Any] = {
        "DigimonID": reader.u32(),
        "MaterialType": reader.u16(),
        "RequiredLevel": reader.i32(),
        "Price": reader.u32(),
        "WayType": reader.u16(),
        "ItemCount": reader.i32(),
    }
    record["MaterialData"] = [_read_material(reader) for _ in range(record["ItemCount"])]
    record["MaterialCount"] = reader.i32()
    record["SubMaterialData"] = [
        _read_material(reader) for _ in range(record["MaterialCount"])
    ]
    return record


def _write_exchange(writer: Writer, record: dict[str, Any]) -> None:
    where = "ExtraExchange"
    writer.u32(field(record, "DigimonID", where))
    writer.u16(field(record, "MaterialType", where))
    writer.i32(field(record, "RequiredLevel", where))
    writer.u32(field(record, "Price", where))
    writer.u16(field(record, "WayType", where))
    writer.i32(field(record, "ItemCount", where))
    for material in _list(record, "MaterialData", where):
        _write_material(writer, material)
    writer.i32(field(record, "MaterialCount", where))
    for material in _list(record, "SubMaterialData", where):
        _write_material(writer, material)


def _read_id(reader: Reader) -> dict[str, Any]:
    record = {"ID": reader.u16()}
    count = _count(reader, "ExtraExchange")
    record["ExtraExchange"] = [_read_exchange(reader) for _ in range(count)]
    return record


def _write_id(writer: Writer, record: dict[str, Any]) -> None:
    writer.u16(field(record, "ID", "ExtraExchangesID"))
    exchanges = _list(record, "ExtraExchange", "ExtraExchangesID")
    writer.i32(len(exchanges))
    for exchange in exchanges:
        _write_exchange(writer, exchange)


def _read_npc(reader: Reader) -> dict[str, Any]:
    record = {"NpcID": reader.u32()}
    count = _count(reader, "ExtraExchangesID")
    record["ExtraExchangesID"] = [_read_id(reader) for _ in range(count)]
    return record


def _write_npc(writer: Writer, record: dict[str, Any]) -> None:
    writer.u32(field(record, "NpcID", "ExtraExchangeNPC"))
    ids = _list(record, "ExtraExchangesID", "ExtraExchangeNPC")
    writer.i32(len(ids))
    for exchange_id in ids:
        _write_id(writer, exchange_id)


class ExtraExchangeCodec(Codec):
    name = "ExtraExchange"
    filenames = ("extraexchange",)
    sections = ("ExtraExchangeNPC",)
    record_tags = {"ExtraExchangeNPC": "ExtraExchangeNPC"}

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        records = read_records(reader, _read_npc)
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": {"ExtraExchangeNPC": records}}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        write_records(writer, self._items(sections, "ExtraExchangeNPC"), _write_npc)
        return writer.getvalue()
