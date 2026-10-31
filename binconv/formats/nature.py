"""``Nature.bin`` -- the element matrix and the attribute (Data/Vaccine/Virus) table.

Layout from the client, ``dmz-client/LibProj/CsFileTable/Nature.h`` (``CsNature::sINFO``)
written by ``NatureMng.cpp::SaveBin`` (lines 118-141)::

    int32 nCount
    nCount x CsNature::sINFO          ; USHORT s_nID, short s_nElement[MaxCount = 11]
    _SaveBinBaseElement()             ; element-vs-element attribute table

``CsNature::sINFO`` is 24 bytes (2 + 11 * 2), which is why the matrix rows are
``short`` and not ``int``: only the attribute table below uses 32 bit values.
``s_nElement[j]`` is the percentage delta applied to the attacker (the row's
``s_nID``) when it hits target nature ``nsCsDigimonTable::NT_ICE + j`` -- the
client's ``GetValue`` indexes it as ``s_nElement[ nTarget - NT_ICE ]``.

The attribute table (``_SaveBinBaseElement``, lines 383-413; reader at 275-327)::

    int32 nCmpTypeCount
    per compare type:
        int32 nCmpType                ; nsBaseElement::eAtt (0) / eDef (1)
        int32 nBaseCount
        per base type:
            int32 nBaseType           ; nsBaseElement::eElementType (0..4)
            int32 nVecCount
            per target:
                int32 nTargetType
                int32 nPoint          ; 110 = superior, 100 = equal, 90 = inferior

The shipped file holds 11 matrix rows (ids 16-26 = ``NT_ICE`` .. ``NT_NONE``) and
two compare tables of 5 x 5 points; the decode ends exactly at EOF.

``New_Element.bin`` is *not* this format: it holds ``DigimonStatus\\Element\\*.tga``
texture paths and has no loader anywhere in the client.
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, field, read_records, write_records

NATURE_ELEMENT_COUNT = 11


def _read_nature(reader: Reader) -> dict[str, Any]:
    return {
        "ID": reader.u16(),
        "Element": [reader.i16() for _ in range(NATURE_ELEMENT_COUNT)],
    }


def _write_nature(writer: Writer, record: dict[str, Any]) -> None:
    where = "Nature"
    writer.u16(field(record, "ID", where))
    values = record.get("Element")
    if not isinstance(values, list) or len(values) != NATURE_ELEMENT_COUNT:
        raise FormatError(
            f"{where}: 's_nElement' must be a list of {NATURE_ELEMENT_COUNT} numbers"
        )
    for value in values:
        writer.i16(value)


def _read_base(reader: Reader) -> dict[str, Any]:
    record: dict[str, Any] = {"CmpType": reader.i32()}
    record["Element"] = [
        {
            "BaseType": reader.i32(),
            "Point": _read_points(reader),
        }
        for _ in range(_count(reader, "base type"))
    ]
    return record


def _read_points(reader: Reader) -> list[dict[str, Any]]:
    return [
        {"TargetType": reader.i32(), "Point": reader.i32()}
        for _ in range(_count(reader, "target"))
    ]


def _write_base(writer: Writer, record: dict[str, Any]) -> None:
    where = "BaseElement"
    writer.i32(field(record, "CmpType", where))
    elements = record.get("Element")
    if not isinstance(elements, list):
        raise FormatError(f"{where}: 'Element' must be a list")
    writer.i32(len(elements))
    for element in elements:
        writer.i32(field(element, "BaseType", where))
        _write_points(writer, element, where)


def _write_points(writer: Writer, record: dict[str, Any], where: str) -> None:
    points = record.get("Point")
    if not isinstance(points, list):
        raise FormatError(f"{where}: 'Point' must be a list")
    writer.i32(len(points))
    for point in points:
        writer.i32(field(point, "TargetType", where))
        writer.i32(field(point, "Point", where))


def _count(reader: Reader, what: str) -> int:
    count = reader.i32()
    if count < 0 or count > (len(reader.data) - reader.pos):
        raise FormatError(
            f"{reader.name}: implausible {what} count {count} at offset {reader.pos - 4}"
        )
    return count


class NatureCodec(Codec):
    name = "Nature"
    filenames = ("nature",)
    sections = ("Nature", "BaseElement")
    record_tags = {"Nature": "NatureData", "BaseElement": "Compare"}

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        sections = {"Nature": read_records(reader, _read_nature)}
        sections["BaseElement"] = read_records(reader, _read_base)
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": sections}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        write_records(writer, self._items(sections, "Nature"), _write_nature)
        write_records(writer, self._items(sections, "BaseElement"), _write_base)
        return writer.getvalue()
