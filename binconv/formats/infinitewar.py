"""``InfiniteWar.bin`` -- the endless-war (Infinite War) tables.

Layout from the client, ``InfiniteWarManager.h`` / ``TableStruct_InfiniteWar.h``
written by ``InfiniteWarManager.cpp::_SaveBin`` (lines 280-411) and read by
``_LoadBin`` (lines 413-680).  Five counted sections, each a ``map<key, ...>``
whose key *is* stored::

    1) InfiniteWarNpc            map<DWORD npcIdx, map<int stage, sStageInfos>>
        int32 nGroups
        per group:
            DWORD nNpcIdx
            int32 nStages
            per stage:
                int   s_nSummon_Type
                DWORD s_dwRewardItemIdx
                int   s_nWinPoint, s_nLosePoint, s_nMonsterInfoIndex
        (the stage key ``int nStage`` is written before those five fields)

    2) SummonMonster             map<int key, list<sSummonMonsterInfo>>
            int32 nKey
            int32 nMonsters
            per monster: DWORD s_dwMonsterIDX, int s_nCount

    3) DailyReward               map<int key, list<sDaliyRewardInfo>>
            int32 nKey
            int32 nRewards
            per reward:
                DWORD s_dwNeedItemCode, int s_nNeedPoint
                int32 nItems
                per item: DWORD s_dwItemCode, int s_nCount

    4) RankReward                map<int key, list<sRankRewardInfo>>
            int32 nKey
            int32 nRewards
            per reward:
                int s_nRankType, s_nRankMin, s_nRankMax
                int32 nItems
                per item: DWORD s_dwItemCode, int s_nCount

    5) AwardNpc                  map<int key, map<DWORD tableID, sInfiniteAwardNpcInfo>>
            int32 nKey
            int32 nAwards
            per award:
                DWORD s_dwTableID, DWORD s_dwModelID
                std::wstring s_wTamerName, s_wTitleName, s_wGuildName, s_wTalkMsg
                    (``CmBinRead`` wide strings: int32 char count + UTF-16LE)

The shipped file holds 2 / 59 / 7 / 3 / 6 groups (8 694 bytes: 60 stage rows, 189
summon rows, 35 daily rewards, 45 rank rewards and 6 award NPCs), which decodes
exactly to EOF.
"""

from __future__ import annotations

from typing import Any, Callable

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, field, read_records, write_records
from ..fields import read_fields, write_fields

STAGE_FIELDS = [
    ("s_nSummon_Type", "i32"),
    ("s_dwRewardItemIdx", "u32"),
    ("s_nWinPoint", "i32"),
    ("s_nLosePoint", "i32"),
    ("s_nMonsterInfoIndex", "i32"),
]

SUMMON_FIELDS = [("s_dwMonsterIDX", "u32"), ("s_nCount", "i32")]

REWARD_ITEM_FIELDS = [("s_dwItemCode", "u32"), ("s_nCount", "i32")]

DAILY_FIELDS = [("s_dwNeedItemCode", "u32"), ("s_nNeedPoint", "i32")]

RANK_FIELDS = [
    ("s_nRankType", "i32"),
    ("s_nRankMin", "i32"),
    ("s_nRankMax", "i32"),
]

AWARD_FIELDS = [("s_dwTableID", "u32"), ("s_dwModelID", "u32")]

AWARD_STRINGS = ("s_wTamerName", "s_wTitleName", "s_wGuildName", "s_wTalkMsg")


def _read_count(reader: Reader, label: str) -> int:
    count = reader.i32()
    if count < 0 or count > (len(reader.data) - reader.pos):
        raise FormatError(
            f"{reader.name}: implausible {label} count {count} at offset {reader.pos - 4}"
        )
    return count


def _read_npc(reader: Reader) -> dict[str, Any]:
    npc = {"s_dwNpcIdx": reader.u32()}
    count = _read_count(reader, "stage")
    stages = []
    for _ in range(count):
        stage = {"s_nStage": reader.i32()}
        stage.update(read_fields(reader, STAGE_FIELDS))
        stages.append(stage)
    npc["Stage"] = stages
    return npc


def _write_npc(writer: Writer, npc: dict[str, Any]) -> None:
    where = "InfiniteWarNpc"
    writer.u32(field(npc, "s_dwNpcIdx", where))
    stages = npc.get("Stage")
    if not isinstance(stages, list):
        raise FormatError(f"{where}: 'Stage' must be a list")
    writer.i32(len(stages))
    for stage in stages:
        writer.i32(field(stage, "s_nStage", where))
        write_fields(writer, STAGE_FIELDS, stage)


def _read_summon(reader: Reader) -> dict[str, Any]:
    group = {"s_nKey": reader.i32()}
    count = _read_count(reader, "summon monster")
    group["Monster"] = [read_fields(reader, SUMMON_FIELDS) for _ in range(count)]
    return group


def _write_summon(writer: Writer, group: dict[str, Any]) -> None:
    where = "SummonMonster"
    writer.i32(field(group, "s_nKey", where))
    rows = group.get("Monster")
    if not isinstance(rows, list):
        raise FormatError(f"{where}: 'Monster' must be a list")
    writer.i32(len(rows))
    for row in rows:
        write_fields(writer, SUMMON_FIELDS, row)


def _read_reward(reader: Reader, fields: list[tuple[str, Any]]) -> dict[str, Any]:
    reward = read_fields(reader, fields)
    count = _read_count(reader, "reward item")
    reward["Item"] = [read_fields(reader, REWARD_ITEM_FIELDS) for _ in range(count)]
    return reward


def _write_reward(writer: Writer, reward: dict[str, Any], fields: list[tuple[str, Any]]) -> None:
    write_fields(writer, fields, reward)
    rows = reward.get("Item")
    if not isinstance(rows, list):
        raise FormatError("InfiniteWar: 'Item' must be a list")
    writer.i32(len(rows))
    for row in rows:
        write_fields(writer, REWARD_ITEM_FIELDS, row)


def _read_award(reader: Reader) -> dict[str, Any]:
    award = read_fields(reader, AWARD_FIELDS)
    for name in AWARD_STRINGS:
        award[name] = reader.wstring(reader.i32())
    return award


def _write_award(writer: Writer, award: dict[str, Any]) -> None:
    write_fields(writer, AWARD_FIELDS, award)
    for name in AWARD_STRINGS:
        value = field(award, name, "AwardNpc")
        if not isinstance(value, str):
            raise FormatError(f"AwardNpc: {name!r} must be a string")
        writer.i32(len(value))
        writer.wstring(value, len(value))


def _read_key_group(
    reader: Reader, row_reader: Callable[[Reader], dict[str, Any]]
) -> dict[str, Any]:
    group = {"s_nKey": reader.i32()}
    count = _read_count(reader, "sub")
    group["Row"] = [row_reader(reader) for _ in range(count)]
    return group


def _write_key_group(
    writer: Writer,
    group: dict[str, Any],
    row_writer: Callable[[Writer, dict[str, Any]], None],
    section: str,
) -> None:
    writer.i32(field(group, "s_nKey", section))
    rows = group.get("Row")
    if not isinstance(rows, list):
        raise FormatError(f"{section}: 'Row' must be a list")
    writer.i32(len(rows))
    for row in rows:
        row_writer(writer, row)


def _read_award_group(reader: Reader) -> dict[str, Any]:
    group = {"s_nKey": reader.i32()}
    count = _read_count(reader, "award npc")
    group["Row"] = [_read_award(reader) for _ in range(count)]
    return group


def _write_award_group(writer: Writer, group: dict[str, Any]) -> None:
    _write_key_group(writer, group, _write_award, "AwardNpc")


class InfiniteWarCodec(Codec):
    name = "InfiniteWar"
    filenames = ("infinitewar",)
    sections = ("InfiniteWarNpc", "SummonMonster", "DailyReward", "RankReward", "AwardNpc")
    record_tags = {
        "InfiniteWarNpc": "Npc",
        "SummonMonster": "Summon",
        "DailyReward": "Daily",
        "RankReward": "Rank",
        "AwardNpc": "Award",
    }

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        sections = {"InfiniteWarNpc": read_records(reader, _read_npc)}
        sections["SummonMonster"] = read_records(reader, _read_summon)
        sections["DailyReward"] = read_records(
            reader, lambda r: _read_key_group(r, lambda rr: _read_reward(rr, DAILY_FIELDS))
        )
        sections["RankReward"] = read_records(
            reader, lambda r: _read_key_group(r, lambda rr: _read_reward(rr, RANK_FIELDS))
        )
        sections["AwardNpc"] = read_records(reader, _read_award_group)
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": sections}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        write_records(writer, self._items(sections, "InfiniteWarNpc"), _write_npc)
        write_records(writer, self._items(sections, "SummonMonster"), _write_summon)
        write_records(
            writer,
            self._items(sections, "DailyReward"),
            lambda w, g: _write_key_group(
                w, g, lambda ww, row: _write_reward(ww, row, DAILY_FIELDS), "DailyReward"
            ),
        )
        write_records(
            writer,
            self._items(sections, "RankReward"),
            lambda w, g: _write_key_group(
                w, g, lambda ww, row: _write_reward(ww, row, RANK_FIELDS), "RankReward"
            ),
        )
        write_records(writer, self._items(sections, "AwardNpc"), _write_award_group)
        return writer.getvalue()


