"""``Gotcha.bin`` -- the gacha ("gotcha") machines, item groups and mystery rewards.

Layout from the client, ``CsGotcha.h`` (``MAX_GROUP_ITEM`` 10) read by
``CsGotchaMng.cpp::_LoadBin`` (lines 313-380).  Five counted sections, all fixed
size records::

    1) CsGotcha_Machine::sINFO              36 bytes
        DWORD  s_dwNpc_Id
        DWORD  s_dwUseItem_Code
        USHORT s_nUseItem_Cnt
        bool   s_bLimit
        <1 byte of struct padding>
        UINT   s_nStart_Date, s_nEnd_Date, s_nStart_Time, s_nEnd_Time
        USHORT s_nMin_Lv, s_nMax_Lv
        int    s_nShowCountUI

    2) CsGotcha_Item::sINFO                 64 bytes
        USHORT s_nGroup_Id
        <2 bytes of struct padding>
        DWORD  s_dwItem_Code[10]                   40 bytes
        USHORT s_nItem_Cnt[10]                     20 bytes

    3) CsGotcha_RareItem::sINFO            144 bytes
        UINT   s_nNpcID
        TCHAR  s_szRareItemName[64]               128 bytes
        UINT   s_nRareItem, s_nRareItemCnt, s_nRareItemGive

    4) CsGotcha_Mystery_Item::sINFO         12 bytes
        USHORT s_nGroup
        <2 bytes of struct padding>
        UINT   s_nItem
        USHORT s_nEffect
        <2 bytes of struct tail padding>

    5) CsGotcha_Mystery_Coin::sINFO         12 bytes  (``EGG_PREFERMENT`` build adds
        USHORT s_nCoinOrder                       s_nMoney/s_nStartGroupNo/s_nEndGroupNo
        <2 bytes of struct padding>               for a 20-byte record; the shipped
        UINT   s_nCoinIdx                         file has no rows in this table, so
        USHORT s_nCoinCnt                         the smaller layout is the one that
        <2 bytes of struct tail padding>          matches the bytes we have)

The shipped file holds 42 machines, 31 item groups, 122 rare items and no mystery
rows (21 084 bytes = 4 + 42 * 36 + 4 + 31 * 64 + 4 + 122 * 144 + 4 + 4), which
decodes exactly to EOF.
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, read_records, write_records
from ..fields import read_fields, write_fields

MAX_GROUP_ITEM = 10

MACHINE_FIELDS = [
    ("s_dwNpc_Id", "u32"),
    ("s_dwUseItem_Code", "u32"),
    ("s_nUseItem_Cnt", "u16"),
    ("s_bLimit", "u8"),
    ("_pad0", "u8"),
    ("s_nStart_Date", "u32"),
    ("s_nEnd_Date", "u32"),
    ("s_nStart_Time", "u32"),
    ("s_nEnd_Time", "u32"),
    ("s_nMin_Lv", "u16"),
    ("s_nMax_Lv", "u16"),
    ("s_nShowCountUI", "i32"),
]

ITEM_HEAD_FIELDS = [("s_nGroup_Id", "u16"), ("_pad0", "u16")]

RARE_FIELDS = [
    ("s_nNpcID", "u32"),
    ("s_szRareItemName", ("w", 64)),
    ("s_nRareItem", "u32"),
    ("s_nRareItemCnt", "u32"),
    ("s_nRareItemGive", "u32"),
]

MYSTERY_ITEM_FIELDS = [
    ("s_nGroup", "u16"),
    ("_pad0", "u16"),
    ("s_nItem", "u32"),
    ("s_nEffect", "u16"),
    ("_pad1", "u16"),
]

MYSTERY_COIN_FIELDS = [
    ("s_nCoinOrder", "u16"),
    ("_pad0", "u16"),
    ("s_nCoinIdx", "u32"),
    ("s_nCoinCnt", "u16"),
    ("_pad1", "u16"),
]


def _read_item(reader: Reader) -> dict[str, Any]:
    record = read_fields(reader, ITEM_HEAD_FIELDS)
    record["s_dwItem_Code"] = [reader.u32() for _ in range(MAX_GROUP_ITEM)]
    record["s_nItem_Cnt"] = [reader.u16() for _ in range(MAX_GROUP_ITEM)]
    return record


def _write_item(writer: Writer, record: dict[str, Any]) -> None:
    where = "GotchaItem"
    write_fields(writer, ITEM_HEAD_FIELDS, record)
    for name, writer_fn in (("s_dwItem_Code", writer.u32), ("s_nItem_Cnt", writer.u16)):
        values = record.get(name)
        if not isinstance(values, list) or len(values) != MAX_GROUP_ITEM:
            raise FormatError(f"{where}: {name!r} must be a list of {MAX_GROUP_ITEM}")
        for value in values:
            writer_fn(value)


def _simple(fields: list[tuple[str, Any]]):
    def read(reader: Reader) -> dict[str, Any]:
        return read_fields(reader, fields)

    def write(writer: Writer, record: dict[str, Any]) -> None:
        write_fields(writer, fields, record)

    return read, write


_read_machine, _write_machine = _simple(MACHINE_FIELDS)
_read_rare, _write_rare = _simple(RARE_FIELDS)
_read_mystery_item, _write_mystery_item = _simple(MYSTERY_ITEM_FIELDS)
_read_mystery_coin, _write_mystery_coin = _simple(MYSTERY_COIN_FIELDS)


class GotchaCodec(Codec):
    name = "Gotcha"
    filenames = ("gotcha",)
    sections = ("GotchaMachine", "GotchaItem", "GotchaRareItem", "GotchaMysteryItem",
                "GotchaMysteryCoin")
    record_tags = {
        "GotchaMachine": "Machine",
        "GotchaItem": "Item",
        "GotchaRareItem": "RareItem",
        "GotchaMysteryItem": "MysteryItem",
        "GotchaMysteryCoin": "MysteryCoin",
    }

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        sections = {"GotchaMachine": read_records(reader, _read_machine)}
        sections["GotchaItem"] = read_records(reader, _read_item)
        sections["GotchaRareItem"] = read_records(reader, _read_rare)
        sections["GotchaMysteryItem"] = read_records(reader, _read_mystery_item)
        sections["GotchaMysteryCoin"] = read_records(reader, _read_mystery_coin)
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": sections}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        write_records(writer, self._items(sections, "GotchaMachine"), _write_machine)
        write_records(writer, self._items(sections, "GotchaItem"), _write_item)
        write_records(writer, self._items(sections, "GotchaRareItem"), _write_rare)
        write_records(writer, self._items(sections, "GotchaMysteryItem"), _write_mystery_item)
        write_records(writer, self._items(sections, "GotchaMysteryCoin"), _write_mystery_coin)
        return writer.getvalue()

