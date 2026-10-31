"""``Reward.bin`` -- the reward groups handed out per map.

Layout from the client, ``Reward.h`` (``CsReward::sINFO``) read by
``RewardMng.cpp::_LoadBin`` (lines 236-255)::

    int32 nGroups
    per group:
        int32 nIdx
        int32 nMapCount
        nMapCount x CsReward::sINFO          2188 bytes
            USHORT s_nID
            <2 bytes of struct padding>
            TCHAR  s_szCommnet[1024]                 2048 bytes
            char   s_nStartDate[64]
            char   s_nExpDate[64]
            DWORD  s_nItemCode1
            USHORT s_nItemCount1
            <2 bytes of struct tail padding>

The shipped file holds 6 groups with 1 015 rows (2 220 872 bytes), which decodes
exactly to EOF.
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, field, read_records, write_records
from ..fields import read_fields, write_fields

REWARD_FIELDS = [
    ("ID", "u16"),
    ("_pad0", "u16"),
    ("Commnet", ("w", 1024)),
    ("StartDate", ("c", "ascii", 64)),
    ("ExpDate", ("c", "ascii", 64)),
    ("ItemCode1", "u32"),
    ("ItemCount1", "u16"),
    ("_pad1", "u16"),
]


def _read_group(reader: Reader) -> dict[str, Any]:
    group = {"Idx": reader.i32()}
    count = reader.i32()
    if count < 0 or count > (len(reader.data) - reader.pos):
        raise FormatError(
            f"{reader.name}: implausible reward count {count} at offset {reader.pos - 4}"
        )
    group["Reward"] = [read_fields(reader, REWARD_FIELDS) for _ in range(count)]
    return group


def _write_group(writer: Writer, group: dict[str, Any]) -> None:
    where = "Reward"
    writer.i32(field(group, "Idx", where))
    rows = group.get("Reward")
    if not isinstance(rows, list):
        raise FormatError(f"{where}: 'Reward' must be a list")
    writer.i32(len(rows))
    for row in rows:
        write_fields(writer, REWARD_FIELDS, row)


class RewardCodec(Codec):
    name = "Reward"
    filenames = ("reward",)
    sections = ("Reward",)
    record_tags = {"Reward": "Group"}

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        groups = read_records(reader, _read_group)
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": {"Reward": groups}}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        write_records(writer, self._items(sections, "Reward"), _write_group)
        return writer.getvalue()
