"""``DigimonParcel.bin`` -- the digimon ids that can be sent by parcel.

Ported from the client (``CsFileTable/DigimonParcelManager.cpp``,
``CsDigimonParcelMng::_LoadBin`` lines 98-108)::

    int32 count, then count * DWORD dwDigimonIDX

Just a counted list of ids; the JSON keeps one record per id so the section has
the same shape as every other format.
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, field, read_records, write_records


def _read_id(reader: Reader) -> dict[str, Any]:
    return {"DigimonIDX": reader.u32()}


def _write_id(writer: Writer, record: dict[str, Any]) -> None:
    writer.u32(field(record, "DigimonIDX", "DigimonParcel"))


class DigimonParcelCodec(Codec):
    name = "DigimonParcel"
    filenames = ("digimonparcel",)
    sections = ("DigimonParcel",)
    record_tags = {"DigimonParcel": "Digimon"}

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        records = read_records(reader, _read_id)
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": {"DigimonParcel": records}}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        write_records(writer, self._items(sections, "DigimonParcel"), _write_id)
        return writer.getvalue()
