"""``Tutorial.bin`` -- the tutorial speech lines.

Layout from the client, ``Talk_Tutorial.h`` (``CsTalk_Tutorial::sINFO``,
``FT_TALK_TUTORIAL_LEN`` 256) written by ``TalkMng_Tutorial.cpp::SaveBin``
(lines 96-101) and read by ``_LoadBin`` (lines 122-130)::

    int32 nCount
    nCount x CsTalk_Tutorial::sINFO
        TCHAR s_szText[256]        512 bytes

The map key (a ``DWORD``) is *not* stored -- the loader recreates it from the
entry order.  The shipped file holds 18 lines (9 220 bytes), which decodes
exactly to EOF.
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, read_records, write_records
from ..fields import read_fields, write_fields

FT_TALK_TUTORIAL_LEN = 256

TUTORIAL_FIELDS = [("Text", ("w", FT_TALK_TUTORIAL_LEN))]


def _read_tutorial(reader: Reader) -> dict[str, Any]:
    return read_fields(reader, TUTORIAL_FIELDS)


def _write_tutorial(writer: Writer, record: dict[str, Any]) -> None:
    write_fields(writer, TUTORIAL_FIELDS, record)


class TutorialCodec(Codec):
    name = "Tutorial"
    filenames = ("tutorial",)
    sections = ("Tutorial",)
    record_tags = {"Tutorial": "Tutorial"}

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        records = read_records(reader, _read_tutorial)
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": {"Tutorial": records}}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        write_records(writer, self._items(sections, "Tutorial"), _write_tutorial)
        return writer.getvalue()
