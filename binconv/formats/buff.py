"""``Buff.bin`` -- the buff/debuff table.

Ported from ``reference/csharp/Buff.cs``.  Fixed 476 byte records::

    s_dwID (u16)
    s_szName     64 char UTF-16 buffer (128 bytes), cut at the first NUL
    s_szComment 128 char UTF-16 buffer (256 bytes), cut at the first NUL
    s_nBuffIcon, s_nBuffType, s_nBuffLifeType, s_nBuffTimeType, s_nMinLv (u16)
    s_nBuffClass (i16), unknow (i16)
    s_dwSkillCode (u32), s_dwDigimonSkillCode (i32)
    s_bDelete (u8)
    s_szEffectFile   ReadZString(ASCII, 64)
    s_nConditionLv (u16), u (u8)

``s_nBuffClass`` is the known writer bug: the field is declared ``int``, so the
old writer emits four bytes where the reader takes sixteen bits.
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, read_records, write_records
from ..fields import read_fields, write_fields

BUFF_FIELDS = [
    ("s_dwID", "u16"),
    ("s_szName", ("w", 64)),
    ("s_szComment", ("w", 128)),
    ("s_nBuffIcon", "u16"),
    ("s_nBuffType", "u16"),
    ("s_nBuffLifeType", "u16"),
    ("s_nBuffTimeType", "u16"),
    ("s_nMinLv", "u16"),
    ("s_nBuffClass", "i16"),
    ("unknow", "i16"),
    ("s_dwSkillCode", "u32"),
    ("s_dwDigimonSkillCode", "i32"),
    ("s_bDelete", "u8"),
    ("s_szEffectFile", ("z", "ascii", 64)),
    ("s_nConditionLv", "u16"),
    ("u", "u8"),
]


def _read_buff(reader: Reader) -> dict[str, Any]:
    return read_fields(reader, BUFF_FIELDS)


def _write_buff(writer: Writer, record: dict[str, Any]) -> None:
    write_fields(writer, BUFF_FIELDS, record)


class BuffCodec(Codec):
    name = "Buff"
    filenames = ("buff",)
    sections = ("Buff",)
    record_tags = {"Buff": "BuffData"}

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        records = read_records(reader, _read_buff)
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": {"Buff": records}}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        write_records(writer, self._items(sections, "Buff"), _write_buff)
        return writer.getvalue()
