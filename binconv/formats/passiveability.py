"""``Passive_Ability.bin`` -- passive ability rows per passive type.

Layout from the client, ``Digimon.h`` (``CsPassive_Ability_Digimon::sINFO``)
written by ``DigimonMng.cpp::SaveBin`` lines 1837-1858 under
``#define PASSIVE_ABILITY_BIN``::

    per passive type i in nsCsDigimonTable::ePASSIVE_TYPE [PA_START, PA_MAX):
        int32 nCount
        nCount x CsPassive_Ability_Digimon::sINFO     16 bytes
            DWORD s_dwDigimonID
            short s_shEvoNum
            <2 bytes of struct padding>
            int   s_nType
            int   s_nValue1

``PA_START`` is 1 and ``PA_MAX`` is 2 (``nsCsDigimonTable.h``), so exactly one
count is written -- the shipped file is 4 bytes holding a single ``0``.  ``compile``
writes one count as well, which keeps the file byte identical even when rows are
added later.
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, read_records, write_records
from ..fields import read_fields, write_fields

PASSIVE_FIELDS = [
    ("DigimonID", "u32"),
    ("s_shEvoNum", "i16"),
    ("_pad0", "u16"),
    ("Type", "i32"),
    ("s_nValue1", "i32"),
]


def _read_passive(reader: Reader) -> dict[str, Any]:
    return read_fields(reader, PASSIVE_FIELDS)


def _write_passive(writer: Writer, record: dict[str, Any]) -> None:
    write_fields(writer, PASSIVE_FIELDS, record)


class PassiveAbilityCodec(Codec):
    name = "Passive_Ability"
    filenames = ("passive_ability",)
    sections = ("Passive_Ability",)
    record_tags = {"Passive_Ability": "Passive"}

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        records = read_records(reader, _read_passive)
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": {"Passive_Ability": records}}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        write_records(writer, self._items(sections, "Passive_Ability"), _write_passive)
        return writer.getvalue()
