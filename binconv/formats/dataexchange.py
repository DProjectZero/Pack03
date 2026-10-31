"""``Data_Exchange.bin`` -- the item-to-item exchange groups.

Layout from the client, ``Digimon.h`` (``CsData_Exchange::sINFO``) written by
``DigimonMng.cpp::SaveBin`` lines 1860-1890 under
``#define DATA_EXCHAGE_SHEET_BIN`` (the client's spelling)::

    int32 nGroups
    per group:
        int32 nListSize
        nListSize x CsData_Exchange::sINFO      276 bytes
            int   Item_Index
            int   Item_Type
            int   Item_Code
            char  Item_Name[MAX_PATH]           260 bytes
            USHORT Use_Rank
            USHORT Req_Num

The map key is not stored -- the group boundaries are.  The shipped file holds 3
groups with 6 rows in total and decodes exactly to EOF.

The client never names the groups in the file (``CsData_Exchange`` is a
``map<DWORD, list<sINFO>>`` and only the list is written), so the JSON keeps the
groups as ``Items`` arrays and leaves the ids out.
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, read_records, write_records
from ..fields import read_fields, write_fields

ITEM_NAME_LEN = 260  # MAX_PATH

EXCHANGE_FIELDS = [
    ("Item_Index", "i32"),
    ("Item_Type", "i32"),
    ("Item_Code", "i32"),
    ("Item_Name", ("c", "cp949", ITEM_NAME_LEN)),
    ("Use_Rank", "u16"),
    ("Req_Num", "u16"),
]


def _read_group(reader: Reader) -> dict[str, Any]:
    count = reader.i32()
    if count < 0 or count > (len(reader.data) - reader.pos):
        raise FormatError(
            f"{reader.name}: implausible exchange row count {count} at offset {reader.pos - 4}"
        )
    return {"Items": [read_fields(reader, EXCHANGE_FIELDS) for _ in range(count)]}


def _write_group(writer: Writer, group: dict[str, Any]) -> None:
    items = group.get("Items")
    if not isinstance(items, list):
        raise FormatError("Data_Exchange: 'Items' must be a list")
    writer.i32(len(items))
    for item in items:
        write_fields(writer, EXCHANGE_FIELDS, item)


class DataExchangeCodec(Codec):
    name = "Data_Exchange"
    filenames = ("data_exchange",)
    sections = ("Data_Exchange",)
    record_tags = {"Data_Exchange": "Exchange"}

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        groups = read_records(reader, _read_group)
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": {"Data_Exchange": groups}}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        write_records(writer, self._items(sections, "Data_Exchange"), _write_group)
        return writer.getvalue()
