"""``Buff.bin`` -- the buff/debuff table.

Layout from the client, ``dmz-client/LibProj/CsFileTable/Buff.h`` (``CsBuff::sINFO``,
``fread`` one struct per record by ``BuffMng.cpp::_LoadFilePack``)::

    USHORT s_dwID
    TCHAR  s_szName[64]        128 bytes   (BUFF_NAME_LEN, 32 on non-US builds)
    TCHAR  s_szComment[128]    256 bytes
    USHORT s_nBuffIcon, s_nBuffType, s_nBuffLifeType, s_nBuffTimeType
    USHORT s_nMinLv
    USHORT s_nBuffClass
    <2 bytes of struct padding: DWORD must be 4 byte aligned>
    DWORD  s_dwSkillCode
    DWORD  s_dwDigimonSkillCode
    bool   s_bDelete
    char   s_szEffectFile[64]
    <1 byte of struct padding: USHORT must be 2 byte aligned>
    USHORT s_nConditionLv

``sizeof(CsBuff::sINFO)`` is 476 bytes, the record stride of the shipped file.
The padding bytes are kept (``_pad0``/``_pad1``) so a recompile stays byte
identical; in the shipped data ``_pad0`` is zero and ``_pad1`` holds a constant
``0x9A`` left over from the exporter's stack.

The old C# reader ignored the alignment: it read ``s_nConditionLv`` from the
padding byte plus the low half of the real value (154/922/410 instead of
0/3/1) and turned the last byte into a bogus ``u`` field.  It also declared
``s_nBuffClass`` as a signed ``int`` (the client uses ``USHORT``) and wrote four
bytes for it, which shifted every following record.
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, read_records, write_records
from ..fields import read_fields, write_fields

BUFF_FIELDS = [
    ("ID", "u16"),
    ("Name", ("w", 64)),
    ("Comment", ("w", 128)),
    ("BuffIcon", "u16"),
    ("BuffType", "u16"),
    ("BuffLifeType", "u16"),
    ("BuffTimeType", "u16"),
    ("MinLv", "u16"),
    ("BuffClass", "u16"),
    ("_pad0", "u16"),
    ("SkillCode", "u32"),
    ("DigimonSkillCode", "u32"),
    ("Delete", "u8"),
    ("EffectFile", ("z", "ascii", 64)),
    ("_pad1", "u8"),
    ("ConditionLv", "u16"),
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
