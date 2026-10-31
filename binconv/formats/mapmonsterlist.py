"""``MapMonsterList.bin`` -- which monsters spawn where, per map file table.

Layout from the client, ``MapMonsterMng.cpp::_LoadBin`` (lines 191-215) and
``CsMapMonster::sINFO`` in ``MapMonster.h``::

    int32 nCount                             ; 1043 file tables
    per file table:
        DWORD dwFileID
        int32 nSize                          ; map buckets in this table
        per bucket:
            DWORD dwMapNum
            int32 nMapNum                    ; spawn rows in this bucket
            per row: CsMapMonster::sINFO     ; 48 bytes
                DWORD s_dwMapID
                DWORD s_dwMonsterTableID
                int   s_nCenterX, s_nCenterY, s_nRadius, s_nCount, s_nResponTime
                int   s_nKillgen_MonFTID, s_nKillgen_Count, s_nKillgen_ViewCnt
                int   s_nMoveType
                bool  s_bInsRespon
                <3 bytes of struct tail padding>

Field names follow ``the XML dump/MapMonsterList.xml`` (``<Map><FileID>` /
`<MapInformation><Map>` / `<Monsters>`), which is how the old tool laid the same
nesting out, so the XML comparison still lines up.  ``nSize``/``nMapNum`` are not
stored in the JSON -- both are derivable from the arrays -- but the trailing
``u10``/``u2`` padding bytes are, so a recompile stays byte identical.

The shipped file holds 1043 file tables with 93 distinct maps and 3517 spawn rows.
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, field
from ..fields import read_fields, write_fields

MONSTER_FIELDS = [
    ("MapID", "u32"),
    ("MonsterID", "u32"),
    ("CenterX", "i32"),
    ("CenterY", "i32"),
    ("Radius", "i32"),
    ("Count", "i32"),
    ("RespawnTime", "i32"),
    ("KillGenMonFTID", "i32"),
    ("KillgenCount", "i32"),
    ("KillgenViewCnt", "i32"),
    ("MoveType", "i32"),
    ("InstRespawn", "u8"),
    ("u10", "u8"),
    ("u2", "u16"),
]


def _read_table(reader: Reader) -> dict[str, Any]:
    table: dict[str, Any] = {"FileID": reader.u32()}
    table["MapInformation"] = [
        {"Map": reader.u32(), "Monsters": _read_monsters(reader)}
        for _ in range(_count(reader, "map bucket"))
    ]
    return table


def _read_monsters(reader: Reader) -> list[dict[str, Any]]:
    return [read_fields(reader, MONSTER_FIELDS) for _ in range(_count(reader, "spawn row"))]


def _write_table(writer: Writer, table: dict[str, Any]) -> None:
    where = "MapMonsterList"
    writer.u32(field(table, "FileID", where))
    buckets = table.get("MapInformation")
    if not isinstance(buckets, list):
        raise FormatError(f"{where}: 'MapInformation' must be a list")
    writer.i32(len(buckets))
    for bucket in buckets:
        writer.u32(field(bucket, "Map", where))
        rows = bucket.get("Monsters")
        if not isinstance(rows, list):
            raise FormatError(f"{where}: 'Monsters' must be a list")
        writer.i32(len(rows))
        for row in rows:
            write_fields(writer, MONSTER_FIELDS, row)


def _count(reader: Reader, what: str) -> int:
    count = reader.i32()
    if count < 0 or count > (len(reader.data) - reader.pos):
        raise FormatError(
            f"{reader.name}: implausible {what} count {count} at offset {reader.pos - 4}"
        )
    return count


class MapMonsterListCodec(Codec):
    name = "MapMonsterList"
    filenames = ("mapmonsterlist",)
    sections = ("MapMonsterList",)
    record_tags = {"MapMonsterList": "Map"}

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        count = _count(reader, "file table")
        tables = [_read_table(reader) for _ in range(count)]
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": {"MapMonsterList": tables}}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        tables = self._items(sections, "MapMonsterList")
        writer.i32(len(tables))
        for table in tables:
            _write_table(writer, table)
        return writer.getvalue()
