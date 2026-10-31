"""``Digimon_Book.bin`` -- the encyclopedia: option entries, excluded digimon and decks.

Layout from the client, ``Digimon.h`` (``CsEncy_OptData``, ``CsEncy_Exception_Digimon``,
``CsEncy_Deck``, ``CsEncy_Deck_Composition``; ``ENCY_NAME_LEN`` 64,
``ENCY_EXPLAIN_LEN`` 512, ``ENCY_MAX_OPTION`` 3) written by
``DigimonMng.cpp::SaveBin`` lines 1764-1835 under ``#define ENCYCLOPEDIA_BIN``.
Four counted sections::

    CsEncy_OptData::sINFO                 1160 bytes
        DWORD s_dwOptID
        TCHAR s_szOptName[64]                      128 bytes
        USHORT s_nIcon
        <2 bytes of struct padding: TCHAR block follows>
        TCHAR s_szOptExplain[512]                 1024 bytes

    CsEncy_Exception_Digimon::sINFO        132 bytes
        DWORD s_dwDigimonID
        TCHAR s_szName[64]                         128 bytes

    CsEncy_Deck::sINFO                    1204 bytes
        USHORT s_nGroupIdx
        TCHAR  s_szGroupName[64]                   128 bytes
        TCHAR  s_szExplain[512]                   1024 bytes
        USHORT s_nCondition[3], s_nAT_Type[3], s_nOption[3], s_nVal[3]
        UINT   s_nProb[3], s_nTime[3]
        <2 bytes of struct tail padding>

    CsEncy_Deck_Composition                variable
        USHORT s_nGroupIdx
        USHORT nListSize                            (derived from the array)
        nListSize x sDATA                   268 bytes
            DWORD  s_dwBaseDigimonID
            TCHAR  s_szBaseDigimonName[64]         128 bytes
            USHORT s_nEvolslot
            <2 bytes of struct padding>
            DWORD  s_dwDestDigimonID
            TCHAR  s_szDestDigimonName[64]         128 bytes

The shipped file holds 6 option rows, 13 excluded digimon, 16 decks and 16
composition groups with 88 rows (51 604 bytes, decodes exactly to EOF).

``SaveBin`` never copies ``s_nEvolslot`` into the written record (it only copies
the two ids and names) and the destination object is heap allocated, so those two
bytes hold whatever the allocator left behind -- ``_pad0`` keeps them for a byte
exact round-trip.  ``s_szGroupName`` of a composition group is *not* written at
all, which is why the record starts with the index and the list size.
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, field, read_records, write_records
from ..fields import read_fields, write_fields

ENCY_NAME_LEN = 64
ENCY_EXPLAIN_LEN = 512
ENCY_MAX_OPTION = 3

OPT_FIELDS = [
    ("s_dwOptID", "u32"),
    ("s_szOptName", ("w", ENCY_NAME_LEN)),
    ("s_nIcon", "u16"),
    ("_pad0", "u16"),
    ("s_szOptExplain", ("w", ENCY_EXPLAIN_LEN)),
]

EXCEPTION_FIELDS = [
    ("s_dwDigimonID", "u32"),
    ("s_szName", ("w", ENCY_NAME_LEN)),
]

DECK_FIELDS = [
    ("s_nGroupIdx", "u16"),
    ("s_szGroupName", ("w", ENCY_NAME_LEN)),
    ("s_szExplain", ("w", ENCY_EXPLAIN_LEN)),
]

DECK_OPTION_ARRAYS = (
    ("s_nCondition", "u16"),
    ("s_nAT_Type", "u16"),
    ("s_nOption", "u16"),
    ("s_nVal", "u16"),
    ("s_nProb", "u32"),
    ("s_nTime", "u32"),
)

COMPOSITION_DATA_FIELDS = [
    ("s_dwBaseDigimonID", "u32"),
    ("s_szBaseDigimonName", ("w", ENCY_NAME_LEN)),
    ("s_nEvolslot", "u16"),
    ("_pad0", "u16"),
    ("s_dwDestDigimonID", "u32"),
    ("s_szDestDigimonName", ("w", ENCY_NAME_LEN)),
]


def _read_opt(reader: Reader) -> dict[str, Any]:
    return read_fields(reader, OPT_FIELDS)


def _write_opt(writer: Writer, record: dict[str, Any]) -> None:
    write_fields(writer, OPT_FIELDS, record)


def _read_exception(reader: Reader) -> dict[str, Any]:
    return read_fields(reader, EXCEPTION_FIELDS)


def _write_exception(writer: Writer, record: dict[str, Any]) -> None:
    write_fields(writer, EXCEPTION_FIELDS, record)


def _read_deck(reader: Reader) -> dict[str, Any]:
    deck = read_fields(reader, DECK_FIELDS)
    for name, spec in DECK_OPTION_ARRAYS:
        deck[name] = [_read_scalar(reader, spec) for _ in range(ENCY_MAX_OPTION)]
    deck["_pad0"] = reader.u16()
    return deck


def _write_deck(writer: Writer, deck: dict[str, Any]) -> None:
    write_fields(writer, DECK_FIELDS, deck)
    for name, spec in DECK_OPTION_ARRAYS:
        values = deck.get(name)
        if not isinstance(values, list) or len(values) != ENCY_MAX_OPTION:
            raise FormatError(
                f"EncyDeck: {name!r} must be a list of {ENCY_MAX_OPTION} numbers"
            )
        for value in values:
            _write_scalar(writer, spec, value)
    writer.u16(field(deck, "_pad0", "EncyDeck"))


def _read_scalar(reader: Reader, spec: str) -> int:
    return reader.u32() if spec == "u32" else reader.u16()


def _write_scalar(writer: Writer, spec: str, value: int) -> None:
    if spec == "u32":
        writer.u32(value)
    else:
        writer.u16(value)


def _read_composition(reader: Reader) -> dict[str, Any]:
    group = {"s_nGroupIdx": reader.u16()}
    count = reader.u16()
    group["ListData"] = [read_fields(reader, COMPOSITION_DATA_FIELDS) for _ in range(count)]
    return group


def _write_composition(writer: Writer, group: dict[str, Any]) -> None:
    where = "EncyComposition"
    writer.u16(field(group, "s_nGroupIdx", where))
    entries = group.get("ListData")
    if not isinstance(entries, list):
        raise FormatError(f"{where}: 'ListData' must be a list")
    writer.u16(len(entries))
    for entry in entries:
        write_fields(writer, COMPOSITION_DATA_FIELDS, entry)


class DigimonBookCodec(Codec):
    name = "Digimon_Book"
    filenames = ("digimon_book",)
    sections = ("EncyOptData", "EncyException", "EncyDeck", "EncyComposition")
    record_tags = {
        "EncyOptData": "OptData",
        "EncyException": "Exception",
        "EncyDeck": "Deck",
        "EncyComposition": "Composition",
    }

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        sections = {"EncyOptData": read_records(reader, _read_opt)}
        sections["EncyException"] = read_records(reader, _read_exception)
        sections["EncyDeck"] = read_records(reader, _read_deck)
        sections["EncyComposition"] = read_records(reader, _read_composition)
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": sections}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        write_records(writer, self._items(sections, "EncyOptData"), _write_opt)
        write_records(writer, self._items(sections, "EncyException"), _write_exception)
        write_records(writer, self._items(sections, "EncyDeck"), _write_deck)
        write_records(writer, self._items(sections, "EncyComposition"), _write_composition)
        return writer.getvalue()

