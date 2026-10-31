"""``Achieve.bin`` -- achievement definitions and their display categories.

Layout taken from the **client**, which is the authoritative reader
(``dmz-client/LibProj/CsFileTable/AchieveMng.h`` / ``AchieveMng.cpp``)::

    sTYPE :  TCHAR s_szType[32], int32 childCount, then childCount * sTYPE

    header:  int32 achievementCount, then achievementCount * sINFO

    sINFO :  DWORD  s_nQuestID
             DWORD  s_nIcon
             USHORT s_nPoint
             bool   s_bDisplay
             <one byte of alignment padding>
             TCHAR  s_szName[64]
             TCHAR  s_szComment[256]
             TCHAR  s_szTitle[64]
             int    s_nGroup, s_nSubGroup, s_nType, s_nBuffCode

``sizeof(sINFO)`` is 796 bytes, which is exactly the record stride of the
shipped file.

The category table at the head of the file is a **tree**, not a flat list:
``CsAchieveMng::_LoadFilePack`` calls ``m_RootType.Load( nHandle )``, which reads
one node (name + child count) and then recurses.  The shipped file is
``'' -> General(8), Quest(2), Adventure(4)``: one root plus 17 leaves, i.e. 18
records / 1224 bytes.  The old C# converter read it as *18 fixed records* with
the count hardcoded (``dcount = 18``), which happens to consume the same bytes
for this shape but cannot cope with any other.  JSON keeps the records in file
order (depth first) exactly like the exporter's XML, and the stored
``s_listChild`` values are validated against the nesting on ``compile``.

Strings are plain ``TCHAR`` buffers that the client uses as C strings
(``g_pStringAnalysis->Cut_Parcing( ..., pInfo->s_szTitle, ... )``), so a value
ends at the first NUL.  They are read with :meth:`Reader.wstring`, **not** with
``ReadZString``: the old reader skipped NULs instead of stopping at them, which
made it return stale buffer contents ("ronze Tamer" for achievement 1505, whose
title is empty -- a leftover of the longer title that a previous revision of the
file stored there).  ``s_bDisplay2`` is the struct's padding byte after
``s_bDisplay``; it is kept for byte fidelity but the client never reads it.
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, read_records, write_records
from ..fields import read_fields, write_fields

#: ``TCHAR s_szType[32]`` -- the category/menu name.
TYPE_NAME_CHARS = 32

#: One node of the category tree: name + number of children that follow.
TYPE_FIELDS = [("Name", ("w", TYPE_NAME_CHARS)), ("istChild", "i32")]

ACHIEVE_HEAD_FIELDS = [
    ("QuestID", "i32"),
    ("Icon", "i32"),
    ("Point", "u16"),
    ("Display", "u8"),
    # Padding in the client's struct, exported by the old tool as a field.
    ("Display2", "u8"),
]

ACHIEVE_FIELDS = (
    ACHIEVE_HEAD_FIELDS
    + [
        ("Name", ("w", 64)),
        ("Comment", ("w", 256)),
        ("Title", ("w", 64)),
    ]
    + [
        ("Group", "i32"),
        ("SubGroup", "i32"),
        ("Type", "i32"),
        ("BuffCode", "i32"),
    ]
)


def _read_types(reader: Reader) -> list[dict[str, Any]]:
    """Read the recursive category tree, flattened in file (depth first) order."""

    records: list[dict[str, Any]] = []

    def load() -> None:
        record = read_fields(reader, TYPE_FIELDS)
        records.append(record)
        count = record["istChild"]
        if count < 0 or count > len(reader.data):
            raise FormatError(f"{reader.name}: implausible category child count {count}")
        for _ in range(count):
            load()

    load()
    return records


def _write_types(writer: Writer, records: list[dict[str, Any]]) -> None:
    """Write the tree back, checking the stored child counts against the list."""

    items = list(records)
    if not items:
        raise FormatError("AchieveUnknow: the file always starts with a root category")

    index = 0

    def write_node() -> None:
        nonlocal index
        if index >= len(items):
            raise FormatError(
                "AchieveUnknow: a category claims more children than the list holds"
            )
        record = items[index]
        index += 1
        write_fields(writer, TYPE_FIELDS, record)
        count = record["istChild"]
        if not isinstance(count, int) or count < 0:
            raise FormatError(
                f"AchieveUnknow: record {index - 1} has an invalid s_listChild {count!r}"
            )
        for _ in range(count):
            write_node()

    write_node()
    if index != len(items):
        raise FormatError(
            f"AchieveUnknow: {len(items) - index} record(s) are not reachable from the "
            "root category, the s_listChild counts do not describe the list"
        )


def _read_achieve(reader: Reader) -> dict[str, Any]:
    return read_fields(reader, ACHIEVE_FIELDS)


def _write_achieve(writer: Writer, record: dict[str, Any]) -> None:
    write_fields(writer, ACHIEVE_FIELDS, record)


class AchieveCodec(Codec):
    name = "Achieve"
    filenames = ("achieve",)
    sections = ("AchieveUnknow", "Achieve")
    record_tags = {"AchieveUnknow": "sINFO", "Achieve": "AchieveSINFO"}

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        sections = {"AchieveUnknow": _read_types(reader)}
        sections["Achieve"] = read_records(reader, _read_achieve)
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": sections}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        _write_types(writer, self._items(sections, "AchieveUnknow"))
        write_records(writer, self._items(sections, "Achieve"), _write_achieve)
        return writer.getvalue()
