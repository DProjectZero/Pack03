"""``New_Element.bin`` -- the element UI table (icon paths and screen positions).

Layout from the client, ``ElementUI.h`` (``CsAttributeTypeUI::sINFO`` and
``CsNatureTypeUI::sINFO``, ``ELEMENT_UI_PATH`` = 128) written by
``DigimonMng.cpp::SaveBin`` lines 1731-1762 under
``#define NEW_ELEMENT_TABLE_BIN``.  Two counted tables in one file::

    CsAttributeTypeUI::sINFO      148 bytes
        DWORD s_nAttID
        char  s_cPath[128]        "DigimonStatus\\Element\\*.tga"
        int   s_nX, s_nY, s_nBarX, s_nBarY

    CsNatureTypeUI::sINFO         152 bytes
        DWORD s_nNatID
        char  s_cPath[128]
        int   s_nX, s_nY, s_nGaugeX, s_nGaugeY
        float s_nAngle

The shipped file is exactly 2 420 bytes (4 + 5 * 148 + 4 + 11 * 152): five
attribute rows (``nsBaseElement::eElementType`` = No/Data/Vaccine/Virus/Unknown)
and eleven nature rows (the same ``NT_ICE``..``NT_NONE`` set as ``Nature.bin``).

This file is *not* a nature table despite the name -- it only holds icon paths --
and the old tool never exported it, so there is no XML to compare against.
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, read_records, write_records
from ..fields import read_fields, write_fields

ELEMENT_UI_PATH = 128

ATTRIBUTE_FIELDS = [
    ("s_nAttID", "u32"),
    ("s_cPath", ("c", "ascii", ELEMENT_UI_PATH)),
    ("s_nX", "i32"),
    ("s_nY", "i32"),
    ("s_nBarX", "i32"),
    ("s_nBarY", "i32"),
]

NATURE_FIELDS = [
    ("s_nNatID", "u32"),
    ("s_cPath", ("c", "ascii", ELEMENT_UI_PATH)),
    ("s_nX", "i32"),
    ("s_nY", "i32"),
    ("s_nGaugeX", "i32"),
    ("s_nGaugeY", "i32"),
    ("s_nAngle", "f32"),
]


def _read_attribute(reader: Reader) -> dict[str, Any]:
    return read_fields(reader, ATTRIBUTE_FIELDS)


def _write_attribute(writer: Writer, record: dict[str, Any]) -> None:
    write_fields(writer, ATTRIBUTE_FIELDS, record)


def _read_nature(reader: Reader) -> dict[str, Any]:
    return read_fields(reader, NATURE_FIELDS)


def _write_nature(writer: Writer, record: dict[str, Any]) -> None:
    write_fields(writer, NATURE_FIELDS, record)


class NewElementCodec(Codec):
    name = "New_Element"
    filenames = ("new_element",)
    sections = ("AttributeTypeUI", "NatureTypeUI")
    record_tags = {"AttributeTypeUI": "Attribute", "NatureTypeUI": "Nature"}

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        sections = {"AttributeTypeUI": read_records(reader, _read_attribute)}
        sections["NatureTypeUI"] = read_records(reader, _read_nature)
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": sections}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        write_records(writer, self._items(sections, "AttributeTypeUI"), _write_attribute)
        write_records(writer, self._items(sections, "NatureTypeUI"), _write_nature)
        return writer.getvalue()
