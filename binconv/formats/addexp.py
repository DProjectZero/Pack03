"""``AddExp.bin`` -- the bonus-EXP (tamer "title") entries.

Layout from the client, ``AddExp.h`` (``CsAddExpMng::sAddExp``) read by
``AddExp.cpp::_LoadBin`` (lines 122-130)::

    int32 nCount
    nCount x sAddExp
        DWORD s_nID
        DWORD s_nSkillID
        int   s_nIconID
        TCHAR s_szTitle[ITEM_NAME_LEN]        64 chars  = 128 bytes
        TCHAR s_szComment[ITEM_COMMENT_LEN]  512 chars = 1024 bytes

``sizeof(sAddExp)`` is 1164 bytes, so the shipped 19 792-byte file holds 17 rows.
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, read_records, write_records
from ..fields import read_fields, write_fields

ITEM_NAME_LEN = 64
ITEM_COMMENT_LEN = 512

ADD_EXP_FIELDS = [
    ("s_nID", "u32"),
    ("s_nSkillID", "u32"),
    ("s_nIconID", "i32"),
    ("s_szTitle", ("w", ITEM_NAME_LEN)),
    ("s_szComment", ("w", ITEM_COMMENT_LEN)),
]


def _read_add_exp(reader: Reader) -> dict[str, Any]:
    return read_fields(reader, ADD_EXP_FIELDS)


def _write_add_exp(writer: Writer, record: dict[str, Any]) -> None:
    write_fields(writer, ADD_EXP_FIELDS, record)


class AddExpCodec(Codec):
    name = "AddExp"
    filenames = ("addexp",)
    sections = ("AddExp",)
    record_tags = {"AddExp": "AddExp"}

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        records = read_records(reader, _read_add_exp)
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": {"AddExp": records}}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        write_records(writer, self._items(sections, "AddExp"), _write_add_exp)
        return writer.getvalue()
