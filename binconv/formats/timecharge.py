"""``TimeCharge.bin`` -- the time-charge (prepaid) item tables.

Ported from the client (``dmz-client/LibProj/CsFileTable/TimeChargeMng.cpp``,
``CsTimeChargeMng::_LoadBin`` lines 154-240; the file name is a literal).  One file
holds three consecutive counted tables::

    ChargeItem:  int32 count, per: DWORD dwItemCode, int nBitCode, int nCashCode
    BitCode:     int32 count, per: int nBitCode, int nKeepTime, int nChargeTime,
                                   DWORD dwKeepPrice
    CashCode:    int32 count, per: int nCashCode, int32 nCashCodeCount,
                                   per: int nTimeIndex, int nNeedCount

The client skips records whose key is 0 (``if( 0 == dwItemCode ) continue;``) after
reading only the key -- those rows would desynchronise the stream, so the JSON
keeps every record as stored and ``compile`` reproduces the file byte for byte.
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, field, read_records, write_records

CHARGE_ITEM_FIELDS = [("dwItemCode", "u32"), ("nBitCode", "i32"), ("nCashCode", "i32")]
BIT_CODE_FIELDS = [
    ("nBitCode", "i32"),
    ("nKeepTime", "i32"),
    ("nChargeTime", "i32"),
    ("dwKeepPrice", "u32"),
]


def _read_charge_item(reader: Reader) -> dict[str, Any]:
    return {
        "dwItemCode": reader.u32(),
        "nBitCode": reader.i32(),
        "nCashCode": reader.i32(),
    }


def _write_charge_item(writer: Writer, record: dict[str, Any]) -> None:
    where = "ChargeItem"
    writer.u32(field(record, "dwItemCode", where))
    writer.i32(field(record, "nBitCode", where))
    writer.i32(field(record, "nCashCode", where))


def _read_bit_code(reader: Reader) -> dict[str, Any]:
    return {
        "nBitCode": reader.i32(),
        "nKeepTime": reader.i32(),
        "nChargeTime": reader.i32(),
        "dwKeepPrice": reader.u32(),
    }


def _write_bit_code(writer: Writer, record: dict[str, Any]) -> None:
    where = "BitCode"
    writer.i32(field(record, "nBitCode", where))
    writer.i32(field(record, "nKeepTime", where))
    writer.i32(field(record, "nChargeTime", where))
    writer.u32(field(record, "dwKeepPrice", where))


def _read_cash_code(reader: Reader) -> dict[str, Any]:
    record = {"nCashCode": reader.i32()}
    count = reader.i32()
    if count < 0 or count > len(reader.data):
        raise FormatError(f"{reader.name}: implausible time-index count {count}")
    record["nCashCodeCount"] = count
    record["NeedInfo"] = [
        {"nTimeIndex": reader.i32(), "nNeedCount": reader.i32()} for _ in range(count)
    ]
    return record


def _write_cash_code(writer: Writer, record: dict[str, Any]) -> None:
    where = "CashCode"
    writer.i32(field(record, "nCashCode", where))
    entries = record.get("NeedInfo")
    if not isinstance(entries, list):
        raise FormatError(f"{where}: 'NeedInfo' must be a list")
    writer.i32(len(entries))
    for entry in entries:
        writer.i32(field(entry, "nTimeIndex", where))
        writer.i32(field(entry, "nNeedCount", where))


class TimeChargeCodec(Codec):
    name = "TimeCharge"
    filenames = ("timecharge",)
    sections = ("ChargeItem", "BitCode", "CashCode")
    record_tags = {"ChargeItem": "Item", "BitCode": "Bit", "CashCode": "Cash"}

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        sections = {"ChargeItem": read_records(reader, _read_charge_item)}
        sections["BitCode"] = read_records(reader, _read_bit_code)
        sections["CashCode"] = read_records(reader, _read_cash_code)
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": sections}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        write_records(writer, self._items(sections, "ChargeItem"), _write_charge_item)
        write_records(writer, self._items(sections, "BitCode"), _write_bit_code)
        write_records(writer, self._items(sections, "CashCode"), _write_cash_code)
        return writer.getvalue()
