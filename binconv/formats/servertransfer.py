"""``ServerTransfer.bin`` -- the server relocation table.

Ported from the client
(``dmz-client/LibProj/CsFileTable/ServerRelocateTable.cpp``,
``CsServerRelocateTBMng::_LoadBin`` lines 117-144) and the structs in
``ServerRelocateTable.h`` (``sTransferInfo`` / ``sTransferLimit``)::

    int32 count, then per server:
        int      nServerIDX
        bool     m_bEnable              1 byte
        wstring  m_serverName           int32 charCount + charCount * 2 bytes
        int32    nLimitCount
        per limit:
            int    m_nLimitType
            UINT64 m_nLimitValue        8 bytes

Everything is read field by field, so there is no struct padding in the file.
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, field, read_records, write_records
from ..fields import read_text, write_text


def _read_limit(reader: Reader) -> dict[str, Any]:
    return {"m_nLimitType": reader.i32(), "m_nLimitValue": reader.u64()}


def _write_limit(writer: Writer, record: dict[str, Any]) -> None:
    writer.i32(field(record, "m_nLimitType", "ServerTransfer.limit"))
    writer.u64(field(record, "m_nLimitValue", "ServerTransfer.limit"))


def _read_server(reader: Reader) -> dict[str, Any]:
    record: dict[str, Any] = {
        "nServerIDX": reader.i32(),
        "m_bEnable": reader.u8(),
    }
    record["m_serverName"] = read_text(reader)
    count = reader.i32()
    if count < 0 or count > len(reader.data):
        raise FormatError(f"{reader.name}: implausible limit count {count}")
    record["LimitList"] = [_read_limit(reader) for _ in range(count)]
    return record


def _write_server(writer: Writer, record: dict[str, Any]) -> None:
    where = "ServerTransfer"
    writer.i32(field(record, "nServerIDX", where))
    writer.u8(field(record, "m_bEnable", where))
    write_text(writer, field(record, "m_serverName", where))
    limits = record.get("LimitList")
    if not isinstance(limits, list):
        raise FormatError(f"{where}: 'LimitList' must be a list")
    writer.i32(len(limits))
    for limit in limits:
        _write_limit(writer, limit)


class ServerTransferCodec(Codec):
    name = "ServerTransfer"
    filenames = ("servertransfer",)
    sections = ("ServerTransfer",)
    record_tags = {"ServerTransfer": "Server"}

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        records = read_records(reader, _read_server)
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": {"ServerTransfer": records}}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        write_records(writer, self._items(sections, "ServerTransfer"), _write_server)
        return writer.getvalue()
