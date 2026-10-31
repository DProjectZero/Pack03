"""``Cuid.bin`` -- the banned-name and chat-filter lists.

Layout from the client, ``CUID.h`` (``CsCuid::sINFO``) and ``CUID_Chat.h``
(``CsCuid_Chat::sINFO``) written by ``CUIDMng.cpp::SaveBin`` (lines 274-294)::

    int32 nCount
    nCount x CsCuid::sINFO                68 bytes
        TCHAR s_Name[CUIDNAME_LEN=32]              64 bytes
        int   s_MsgType                            eCUID_TYPE: 1 = whole word, 2 = id only

    int32 nChatCount
    nChatCount x CsCuid_Chat::sINFO       64 bytes
        TCHAR s_Name[CUID_CHAT_LEN=32]             64 bytes

The shipped file holds 1 023 id entries and 1 202 chat words (146 500 bytes),
which decodes exactly to EOF.
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, read_records, write_records
from ..fields import read_fields, write_fields

CUID_NAME_LEN = 32
CUID_CHAT_LEN = 32

CUID_FIELDS = [("Name", ("w", CUID_NAME_LEN)), ("MsgType", "i32")]
CHAT_FIELDS = [("Name", ("w", CUID_CHAT_LEN))]


def _read_cuid(reader: Reader) -> dict[str, Any]:
    return read_fields(reader, CUID_FIELDS)


def _write_cuid(writer: Writer, record: dict[str, Any]) -> None:
    write_fields(writer, CUID_FIELDS, record)


def _read_chat(reader: Reader) -> dict[str, Any]:
    return read_fields(reader, CHAT_FIELDS)


def _write_chat(writer: Writer, record: dict[str, Any]) -> None:
    write_fields(writer, CHAT_FIELDS, record)


class CuidCodec(Codec):
    name = "Cuid"
    filenames = ("cuid",)
    sections = ("Cuid", "CuidChat")
    record_tags = {"Cuid": "Cuid", "CuidChat": "Chat"}

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        sections = {"Cuid": read_records(reader, _read_cuid)}
        sections["CuidChat"] = read_records(reader, _read_chat)
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": sections}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        write_records(writer, self._items(sections, "Cuid"), _write_cuid)
        write_records(writer, self._items(sections, "CuidChat"), _write_chat)
        return writer.getvalue()
