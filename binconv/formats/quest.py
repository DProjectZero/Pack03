"""``Quest.bin`` -- quest database.

Ported from the original converter (``Quests.cs``) and cross-checked against the client
(``CsFileTable/QuestMng.cpp``, ``CsQuestMng::SaveBin``).
Records are variable length: eight ``TCHAR`` buffers (fixed size, NUL padded,
written as ``fwrite( m_szTitleTab, sizeof(TCHAR), QUEST_TITLE_LEN, fp )``)
followed by four nested tables and a list of event ids.  The client uses those
buffers as C strings, so they are read as fixed buffers that end at the first
NUL (``Reader.cstring``).

Note: the client writes ``Active`` and ``Immediate`` as two ``bool`` bytes and,
in this build (``QUEST_RESET_180712``), ``ResetQuest`` as a third.  The old C#
reader packed the first two into an ``int16`` called ``Active`` and called the
third ``Unknown``; the layout is identical, only the names are off.
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, UTF16, Writer
from ..codec import Codec, read_records, write_records
from ..fields import read_fields, write_fields

QUEST_FIELDS_HEAD = [
    ("UniqID", "i32"),
    ("Model", "i32"),
    ("Model2", "i32"),
    ("Level", "i16"),
    ("Pos", "i32"),
    ("Pos2", "i32"),
    ("ManagedID", "i32"),
    ("Active", "i16"),
    ("Unknown", "u8"),
    ("Type", "i32"),
    ("StartTargetType", "i32"),
    ("StartTargetID", "i32"),
    ("Target", "i32"),
    ("TargetValue", "i32"),
]

# (json name, field size in bytes) for the ReadZString blobs.
QUEST_STRINGS = [
    ("TitleTab", 160),
    ("TitleText", 160),
    ("Body", 4096),
    ("Simple", 256),
    ("Helper", 1024),
    ("Process", 640),
    ("Complete", 1400),
    ("Expert", 640),
]

QUEST_ITEM_FIELDS = [
    ("Itemgiven", "i32"),
    ("ItemgivenType", "i32"),
    ("ItemgivenAmount", "i32"),
]
CONDITION_FIELDS = [
    ("ConditionType", "i32"),
    ("ConditionID", "i32"),
    ("ConditionCount", "i32"),
]
GOAL_FIELDS = [
    ("GoalType", "i32"),
    ("GoalID", "i32"),
    ("goalAmount", "i32"),
    ("CurTypeCount", "i32"),
    ("SubValue", "i32"),
    ("SubValue1", "i32"),
]
REWARD_MONEY_FIELDS = [("RewardMoney", "i32"), ("RewardUnk", "i32")]
REWARD_ITEM_FIELDS = [("RewardItem", "i32"), ("RewardAmount", "i32")]


def _read_table(reader, fields) -> list[dict[str, Any]]:
    count = reader.i32()
    if count < 0 or count > len(reader.data):
        raise FormatError(f"{reader.name}: implausible table count {count}")
    return [read_fields(reader, fields) for _ in range(count)]


def _write_table(writer, fields, records) -> None:
    items = list(records)
    writer.i32(len(items))
    for item in items:
        write_fields(writer, fields, item)


def _read_quest(reader) -> dict[str, Any]:
    quest = read_fields(reader, QUEST_FIELDS_HEAD)
    for name, size in QUEST_STRINGS:
        quest[name] = reader.cstring(UTF16, size)

    quest["questItems"] = _read_table(reader, QUEST_ITEM_FIELDS)
    quest["conditions"] = _read_table(reader, CONDITION_FIELDS)
    quest["QuestGoals"] = _read_table(reader, GOAL_FIELDS)

    count = reader.i32()
    if count < 0 or count > len(reader.data):
        raise FormatError(f"{reader.name}: implausible reward count {count}")
    rewards = []
    for _ in range(count):
        reward = {"Reward": reader.i32(), "RewardType": reader.i32()}
        if reward["RewardType"] <= 0:
            reward["QuestRewardMoney"] = read_fields(reader, REWARD_MONEY_FIELDS)
        else:
            reward["QuestRewardItems"] = read_fields(reader, REWARD_ITEM_FIELDS)
        rewards.append(reward)
    quest["rewardQuantities"] = rewards

    count = reader.i32()
    if count < 0 or count > len(reader.data):
        raise FormatError(f"{reader.name}: implausible event count {count}")
    quest["Event"] = [reader.i32() for _ in range(count)]
    return quest


def _write_quest(writer, quest) -> None:
    write_fields(writer, QUEST_FIELDS_HEAD, quest)
    for name, size in QUEST_STRINGS:
        writer.cstring(quest[name], UTF16, size)

    _write_table(writer, QUEST_ITEM_FIELDS, quest["questItems"])
    _write_table(writer, CONDITION_FIELDS, quest["conditions"])
    _write_table(writer, GOAL_FIELDS, quest["QuestGoals"])

    rewards = quest["rewardQuantities"]
    writer.i32(len(rewards))
    for reward in rewards:
        writer.i32(reward["Reward"])
        writer.i32(reward["RewardType"])
        if reward["RewardType"] <= 0:
            write_fields(writer, REWARD_MONEY_FIELDS, reward["QuestRewardMoney"])
        else:
            write_fields(writer, REWARD_ITEM_FIELDS, reward["QuestRewardItems"])

    events = quest["Event"]
    writer.i32(len(events))
    for event in events:
        writer.i32(event)


class QuestCodec(Codec):
    name = "Quest"
    filenames = ("quest",)
    sections = ("Quest",)
    record_tags = {"Quest": "QuestInfo"}

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        quests = read_records(reader, _read_quest)
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": {"Quest": quests}}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        write_records(writer, self._items(sections, "Quest"), _write_quest)
        return writer.getvalue()
