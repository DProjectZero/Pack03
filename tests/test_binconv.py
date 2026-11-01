"""Unit tests for the converter primitives and a couple of codecs.

Run with:
    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import re
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REPO_ROOT = Path(__file__).resolve().parents[1]

from binconv.binary import FormatError, Reader, UTF16, Writer  # noqa: E402
from binconv.blobs import BLOBS, copy_into  # noqa: E402
from binconv.cli import main, read_sections, section_path, write_sections  # noqa: E402
from binconv.codec import compare_roundtrip  # noqa: E402
from binconv.pack import (  # noqa: E402
    CHUNK_SIZE,
    ENTRY_SIZE,
    HASH_SEED,
    PATH_SEED,
    collect,
    extract,
    name_hash,
    patch_pack,
    read_index,
    read_pack,
    write_pack,
)
from binconv.formats import all_codecs, for_stem  # noqa: E402
from binconv.formats.achieve import ACHIEVE_FIELDS, AchieveCodec  # noqa: E402
from binconv.formats.buff import BuffCodec  # noqa: E402
from binconv.formats.cashshop import CashShopCodec  # noqa: E402
from binconv.formats.charcreatetable import CharCreateTableCodec  # noqa: E402
from binconv.formats.dmbase import DMBaseCodec  # noqa: E402
from binconv.formats.event import EventCodec  # noqa: E402
from binconv.formats.extraexchange import ExtraExchangeCodec  # noqa: E402
from binconv.formats.itemlist import ItemListCodec  # noqa: E402
from binconv.formats.maplist import MapListCodec  # noqa: E402
from binconv.formats.mapmonsterlist import MapMonsterListCodec  # noqa: E402
from binconv.formats.mapnpc import MapNpcCodec  # noqa: E402
from binconv.formats.mapobject import MapObjectCodec  # noqa: E402
from binconv.formats.mapregion import MapRegionCodec  # noqa: E402
from binconv.formats.monster import MonsterCodec  # noqa: E402
from binconv.formats.nature import NatureCodec  # noqa: E402
from binconv.formats.newelement import NewElementCodec  # noqa: E402
from binconv.formats.npc import NpcCodec  # noqa: E402
from binconv.formats.spiritnpc import SpiritNpcCodec  # noqa: E402
from binconv.formats.svlineup import SvLineUpCodec  # noqa: E402
from binconv.formats.talk import TalkCodec  # noqa: E402
from binconv.formats.digimon_list import DigimonListCodec  # noqa: E402
from binconv.formats.digimonevo import DigimonEvoCodec  # noqa: E402
from binconv.formats.skill import SkillCodec  # noqa: E402
from binconv.formats.portal import PORTAL_INFO_FIELDS, MapPortalCodec  # noqa: E402
from binconv.formats.quest import QuestCodec  # noqa: E402
from binconv.formats.ride import RideCodec  # noqa: E402
from binconv.formats.uitext import UITextCodec  # noqa: E402
from binconv.formats.worldmap import WorldMapCodec  # noqa: E402
from binconv.fields import read_fields, read_text  # noqa: E402


class ScalarTests(unittest.TestCase):
    def test_roundtrip_scalars(self) -> None:
        writer = Writer()
        writer.u8(0xFF)
        writer.i8(-1)
        writer.u16(0xBEEF)
        writer.i16(-2)
        writer.u32(0xDEADBEEF)
        writer.i32(-3)
        writer.f32(1.5)
        writer.f64(-2.25)

        reader = Reader(writer.getvalue())
        self.assertEqual(reader.u8(), 0xFF)
        self.assertEqual(reader.i8(), -1)
        self.assertEqual(reader.u16(), 0xBEEF)
        self.assertEqual(reader.i16(), -2)
        self.assertEqual(reader.u32(), 0xDEADBEEF)
        self.assertEqual(reader.i32(), -3)
        self.assertEqual(reader.f32(), 1.5)
        self.assertEqual(reader.f64(), -2.25)
        self.assertEqual(reader.pos, len(writer.getvalue()))

    def test_unsigned_wraps_signed_payload(self) -> None:
        writer = Writer()
        writer.i16(short_value := 65535)
        self.assertEqual(Reader(writer.getvalue()).i16(), -1)
        writer = Writer()
        writer.u16(-1 & 0xFFFF)
        self.assertEqual(Reader(writer.getvalue()).u16(), 65535)
        self.assertEqual(short_value, 65535)

    def test_read_past_end_raises(self) -> None:
        with self.assertRaises(FormatError):
            Reader(b"\x00").i32()


class StringTests(unittest.TestCase):
    def test_wstring_pads_and_truncates(self) -> None:
        writer = Writer()
        writer.wstring("GM Buff", 8)
        self.assertEqual(len(writer), 16)
        self.assertEqual(Reader(writer.getvalue()).wstring(8), "GM Buff")

        writer = Writer()
        writer.wstring("0123456789", 4)
        self.assertEqual(Reader(writer.getvalue()).wstring(4), "0123")

    def test_wstring_stops_at_nul(self) -> None:
        buffer = "AB\0CD".encode(UTF16) + b"\0\0"
        self.assertEqual(Reader(buffer).wstring(6), "AB")

    def test_zstring_utf16_skips_to_field_size(self) -> None:
        payload = "Hi".encode(UTF16) + b"\0\0\0\0" + b"junkjunkjunk"
        reader = Reader(payload)
        self.assertEqual(reader.zstring(UTF16, 16), "Hi")
        self.assertEqual(reader.pos, 16)

    def test_zstring_ascii(self) -> None:
        payload = b"Effect\0" + b"\0" * 9
        reader = Reader(payload)
        self.assertEqual(reader.zstring("ascii", 16), "Effect")
        self.assertEqual(reader.pos, 16)


class RoundtripClassificationTests(unittest.TestCase):
    def test_exact(self) -> None:
        self.assertEqual(compare_roundtrip(b"abcd", b"abcd"), ("exact", 0))

    def test_padding(self) -> None:
        self.assertEqual(compare_roundtrip(b"ab\0\0", b"ab\0\0"), ("exact", 0))
        self.assertEqual(compare_roundtrip(b"ab\x19\x00", b"ab\0\0"), ("padding", 1))

    def test_mismatch(self) -> None:
        self.assertEqual(compare_roundtrip(b"abcd", b"abce")[0], "mismatch")
        self.assertEqual(compare_roundtrip(b"abc", b"abcd")[0], "mismatch")


def exchange_record(**overrides) -> dict:
    record = {
        "ExchangeItem_No": 0,
        "NpcID": 93808,
        "ItemIndex": 0,
        "_pad0": 30264,
        "ItemID": 9917,
        "Exchange_Code_A": 9916,
        "Exchange_Code_B": 0,
        "Exchange_Code_C": 0,
        "Exchange_Code_D": 0,
        "PropertyA_Price": 3,
        "PropertyB_Price": 0,
        "PropertyC_Price": 0,
        "PropertyD_Price": 0,
        "Count": 1,
        "_pad1": 108,
    }
    record.update(overrides)
    return record


def accessory_entry(key: int) -> dict:
    return {
        "index_Accessory1": 10000001 + key,
        "index_Accessory": 10000001 + key,
        "Gain_Option": 1,
        "Changeable_Option_Number": 0,
        "index": [
            {"OptIdx": slot, "unknow": 0, "Min": 1, "Max": 2}
            for slot in range(16)
        ],
    }


class ItemListLayoutTests(unittest.TestCase):
    def test_item_record_is_1596_bytes(self) -> None:
        from binconv.fields import field_size
        from binconv.formats.itemlist import ITEM_FIELDS

        # 14907 records * 1596 + 4 byte count = 23791576, which is exactly where
        # the ItemTap section starts in the retail install/ItemList.bin.
        self.assertEqual(field_size(ITEM_FIELDS), 1596)

    def test_section_names(self) -> None:
        codec = ItemListCodec()
        self.assertEqual(len(codec.sections), 16)
        self.assertEqual(codec.sections[0], "ItemList")
        self.assertIn("ItemAcessorys", codec.sections)

    def test_exchange_key_precedes_the_struct(self) -> None:
        # The client writes ``[ExchangeItem_No int][CsItemExchange::sINFO]`` per
        # record.  The old reader took the key as the *previous* record's last
        # field, so the last key was lost (it swallowed the accessory count).
        from binconv.fields import field_size
        from binconv.formats.itemlist import EXCHANGE_FIELDS

        self.assertEqual(field_size(EXCHANGE_FIELDS), 40)
        records = [
            exchange_record(ExchangeItem_No=0, NpcID=93808, ItemIndex=0),
            exchange_record(ExchangeItem_No=1, NpcID=93808, ItemIndex=1),
        ]
        writer = Writer()
        ItemListCodec._write_exchanges(writer, records)
        data = writer.getvalue()
        # count + two (4 byte key + 40 byte struct) records
        self.assertEqual(len(data), 4 + 2 * 44)
        self.assertEqual(data[4:8], (0).to_bytes(4, "little"))
        self.assertEqual(data[4 + 44 : 4 + 48], (1).to_bytes(4, "little"))
        self.assertEqual(ItemListCodec._read_exchanges(Reader(data)), records)

    def test_accessory_table_starts_with_its_count(self) -> None:
        from binconv.formats.itemlist import (
            ACCESSORY_COUNT,
            _read_accessories,
            _write_accessories,
        )

        table = [accessory_entry(index) for index in range(ACCESSORY_COUNT)]
        writer = Writer()
        _write_accessories(writer, table)
        data = writer.getvalue()
        # count + 184 * (12 byte header + 16 * 12 byte options)
        self.assertEqual(data[:4], (ACCESSORY_COUNT).to_bytes(4, "little"))
        self.assertEqual(len(data), 4 + 184 * 204)
        self.assertEqual(_read_accessories(Reader(data)), table)

    def test_accessory_table_size_comes_from_the_count(self) -> None:
        # The count is stored in the file, so a shorter table is legal (the
        # shipped one holds ACCESSORY_COUNT entries).
        from binconv.formats.itemlist import _read_accessories, _write_accessories

        table = [accessory_entry(0), accessory_entry(1)]
        writer = Writer()
        _write_accessories(writer, table)
        data = writer.getvalue()
        self.assertEqual(data[:4], (2).to_bytes(4, "little"))
        self.assertEqual(len(data), 4 + 2 * 204)
        self.assertEqual(_read_accessories(Reader(data)), table)

    def test_accessory_entry_needs_every_option(self) -> None:
        from binconv.formats.itemlist import _write_accessories

        entry = accessory_entry(0)
        entry["index"] = entry["index"][:15]
        with self.assertRaises(FormatError):
            _write_accessories(Writer(), [entry])


def quest_sections() -> dict:
    """Sample Quest table shared by the codec and CLI tests."""

    return {
        "Quest": [
            {
                "UniqID": 2,
                "Model": 0,
                "Model2": 0,
                "Level": 9,
                "Pos": 0,
                "Pos2": 0,
                "ManagedID": 122,
                "Active": 0,
                "Unknown": 0,
                "Type": 0,
                "StartTargetType": 0,
                "StartTargetID": 90002,
                "Target": 0,
                "TargetValue": 0,
                "TitleTab": "Digital World_Whole",
                "TitleText": "Find traces of Piyomon!!",
                "Body": "Line one\r\nLine two",
                "Simple": "Bring back feathers",
                "Helper": "",
                "Process": "",
                "Complete": "",
                "Expert": "",
                "questItems": [
                    {"Itemgiven": 20001, "ItemgivenType": 1, "ItemgivenAmount": 1}
                ],
                "conditions": [
                    {"ConditionType": 1, "ConditionID": 0, "ConditionCount": 0}
                ],
                "QuestGoals": [
                    {
                        "GoalType": 1,
                        "GoalID": 20001,
                        "goalAmount": 10,
                        "CurTypeCount": 1,
                        "SubValue": -1,
                        "SubValue1": 0,
                    }
                ],
                "rewardQuantities": [
                    {
                        "Reward": 1,
                        "RewardType": 0,
                        "QuestRewardMoney": {"RewardMoney": 1200, "RewardUnk": 0},
                    },
                    {
                        "Reward": 2,
                        "RewardType": 1,
                        "QuestRewardItems": {"RewardItem": 20001, "RewardAmount": 3},
                    },
                ],
                "Event": [1, 2, 3],
            }
        ]
    }


class TalkCodecTests(unittest.TestCase):
    def test_roundtrip(self) -> None:
        codec = TalkCodec()
        sections = {
            "TalkDigimon": [
                {"Key": 7, "Param": 1, "Type": 2, "_pad0": 0,
                 "Text": "hi", "List": "list"}
            ],
            "TalkEvent": [{"Key": 3, "TalkNum": 9, "Text": "event"}],
            "TalkMessage": [
                {"ID": 5, "MsgType": 2, "ButtonType": 4, "TitleName": "t",
                 "Message": "m", "LinkID": 0}
            ],
            "TalkTip": [{"Key": 1, "Tip": "tip"}],
            "TalkLoadingTip": [{"Key": 2, "LoadingTip": "lt", "Level": 30}],
            "TalkTooltip": [],
        }
        data = codec.encode(sections)
        # 4 + 412 | 4 + 408 | 4 + 560 | 4 + 404 | 4 + 408, and no tooltip section.
        self.assertEqual(len(data), 5 * 4 + 412 + 408 + 560 + 404 + 408)
        self.assertEqual(codec.decode(data)["sections"], sections)

    def test_optional_tooltip_section(self) -> None:
        codec = TalkCodec()
        sections = {
            "TalkDigimon": [],
            "TalkEvent": [],
            "TalkMessage": [],
            "TalkTip": [],
            "TalkLoadingTip": [],
            "TalkTooltip": [{"ID": 1, "s_Title": "a", "Message": "b"}],
        }
        data = codec.encode(sections)
        # five empty sections + the tooltip count and its 3 076-byte record
        self.assertEqual(len(data), 6 * 4 + 3076)
        self.assertEqual(codec.decode(data)["sections"], sections)


class SpiritNpcCodecTests(unittest.TestCase):
    def test_record_size(self) -> None:
        row = {
            "Type": 2, "SubType": 1, "ID": 75020, "ItemCount": 2,
            "ItemCode0": 98701, "ItemCode1": 98801, "ItemCode2": 98901,
            "Reserved0": 0, "Reserved1": 0, "Reserved2": 0,
            "Reserved3": 0, "Reserved4": 0, "Reserved5": 0,
            "Reserved6": 0, "EvolveCode0": 98700, "EvolveCode1": 98699,
            "ReservedLow0": 0, "ReservedLow1": 0, "ReservedLow2": 0,
            "Flag1": 0x00010001, "Flag2": 0, "Flag3": 0x00380000, "Flag4": 0,
        }
        codec = SpiritNpcCodec()
        data = codec.encode({"SpiritNpc": [row]})
        self.assertEqual(len(data), 4 + 88)
        self.assertEqual(codec.decode(data)["sections"]["SpiritNpc"], [row])


class SvLineUpCodecTests(unittest.TestCase):
    def test_roundtrip(self) -> None:
        rows = [
            {"Slot": i, "Order": order, "Name": name}
            for i, (order, name) in enumerate(
                [(5, "Barbamon"), (4, "Beelzemon"), (3, "Lilithmon"),
                 (1, "Leviamon"), (2, "Lucemon")]
            )
        ]
        codec = SvLineUpCodec()
        data = codec.encode({"SvLineUp": rows})
        self.assertEqual(len(data), 4 + 5 * 72)
        self.assertEqual(codec.decode(data)["sections"]["SvLineUp"], rows)


class QuestCodecTests(unittest.TestCase):
    def test_roundtrip(self) -> None:
        codec = QuestCodec()
        sections = quest_sections()
        data = codec.encode(sections)
        decoded = codec.decode(data)
        self.assertEqual(decoded["sections"], sections)

    def test_strings_are_fixed_size(self) -> None:
        codec = QuestCodec()
        data = codec.encode(quest_sections())
        # TitleTab is a 160 byte field, Body 4096, ...
        self.assertGreater(len(data), 4 + 160 + 160 + 4096)

    def test_missing_section(self) -> None:
        with self.assertRaises(FormatError):
            QuestCodec().encode({})


def event_sections() -> dict:
    """Minimal valid ``Event.bin``: one record per section, fixed slot counts."""

    def slots(count: int, first: dict) -> list[dict]:
        return [first] + [{"ItemID": 0, "ItemCount": 0}] * (count - 1)

    return {
        "AttendenceTime": [
            {"tm_sec": 1, "tm_min": 0, "tm_hour": 0, "tm_mday": 15, "tm_mon": 2,
             "tm_year": 117, "tm_wday": 0, "tm_yday": 0, "tm_isdst": 0},
            {"tm_sec": 59, "tm_min": 59, "tm_hour": 23, "tm_mday": 26, "tm_mon": 3,
             "tm_year": 117, "tm_wday": 8, "tm_yday": 411319584, "tm_isdst": 0},
        ],
        "Event": [
            {
                "TableNo": 30018,
                "TimeInMinutes": 0,
                "EventItems": slots(6, {"ItemID": 128578, "ItemCount": 1}),
                "Name": "Come Back Tamer! Event Reward",
            }
        ],
        "MensalEvent": [
            {
                "ID": 1, "Use": 1, "Index": 1, "Type": 1,
                "SuccessType": 1, "SuccessValue": 35, "ItemKind": 3,
                "MensalItems": slots(6, {"ItemID": 10301, "ItemCount": 1}),
                "Name": "2016-04-26/00:01:00",
                "EndTime": "2018-09-28/12:59:00",
            }
        ],
        "MonthlyEvent": [
            {
                "TableNo": 60000,
                "Message": "Event Reward",
                "MonthlyItems": slots(28, {"ItemID": 9766, "ItemCount": 20}),
            }
        ],
        "TimeEvent": [
            {
                "ID": 1,
                "StartDate": "2020-01-14 10:00:00",
                "EndDate": "2020-01-28 23:59:59",
                "Day": 0,
                "StartTime": "02:00:00",
                "EndTime": "05:00:00",
                "ItemID": 129135,
                "ItemCount": 1,
                "unknow": 0,
            }
        ],
        "Event100Days": [
            {
                "ID": 1,
                "Event": "100 Days of Digimon",
                "EventTitle": "Thanksgiving! Digimon Race(100D)!",
                "EventDescript": "Log-in everyday and get DigiEgg!",
                "StartTime": "2019-11-12 14:00:00",
                "EndTime": "2020-02-19 23:59:59",
                "Reset": "00:00:10",
                "EventItems": [
                    {"Name": "1D", "ItemID": 127041, "ItemCount": 1, "Unknow": 0},
                ],
            }
        ],
    }


class EventCodecTests(unittest.TestCase):
    def test_roundtrip(self) -> None:
        codec = EventCodec()
        sections = event_sections()
        decoded = codec.decode(codec.encode(sections))
        self.assertEqual(decoded["sections"], sections)

    def test_section_names_follow_the_xml_documents(self) -> None:
        self.assertEqual(
            EventCodec().sections,
            ("AttendenceTime", "Event", "MensalEvent", "MonthlyEvent", "TimeEvent",
             "Event100Days"),
        )

    def test_event_name_is_utf16_at_offset_120(self) -> None:
        # 2*9 int32 time spans, event count, s_TableNo, TimeInMinutes, 6 ids, 6 counts
        name_offset = 72 + 4 + 4 + 4 + 6 * 4 + 6 * 2
        data = EventCodec().encode(event_sections())
        self.assertEqual(name_offset, 120)
        self.assertEqual(data[name_offset : name_offset + 2], "C".encode(UTF16))
        # ... which is why the ASCII reader in Event.cs only ever saw "C".
        self.assertEqual(
            Reader(data[name_offset:]).cstring("ascii", 1024), "C"
        )
        self.assertEqual(
            EventCodec().decode(data)["sections"]["Event"][0]["Name"],
            "Come Back Tamer! Event Reward",
        )

    def test_item_tables_need_every_slot(self) -> None:
        sections = event_sections()
        sections["Event"][0]["EventItems"].pop()
        with self.assertRaises(FormatError):
            EventCodec().encode(sections)

        sections = event_sections()
        sections["MonthlyEvent"][0]["MonthlyItems"].pop()
        with self.assertRaises(FormatError):
            EventCodec().encode(sections)

    def test_attendence_needs_two_time_spans(self) -> None:
        sections = event_sections()
        sections["AttendenceTime"].pop()
        with self.assertRaises(FormatError):
            EventCodec().encode(sections)

    def test_zero_id_time_event_is_only_four_bytes(self) -> None:
        sections = event_sections()
        sections["TimeEvent"] = [{"ID": 0}]
        data = EventCodec().encode(sections)
        self.assertEqual(EventCodec().decode(data)["sections"]["TimeEvent"], [{"ID": 0}])

    def test_time_event_keeps_the_discarded_int16(self) -> None:
        sections = event_sections()
        sections["TimeEvent"][0]["unknow"] = 7
        decoded = EventCodec().decode(EventCodec().encode(sections))["sections"]
        self.assertEqual(decoded["TimeEvent"][0]["unknow"], 7)

    def test_string_lengths_are_derived_from_the_text(self) -> None:
        data = EventCodec().encode(event_sections())
        size = len("2020-01-14 10:00:00".encode(UTF16)) // 2
        self.assertIn(size.to_bytes(4, "little") + "2020-01-14 10:00:00".encode(UTF16), data)


def f32(value: float) -> float:
    """The double Python reads back after storing *value* as a float32."""

    return struct.unpack("<f", struct.pack("<f", value))[0]


def dmbase_sections() -> dict:
    """Minimal valid ``DMBase.bin``: one record per section."""

    stats = {
        "ID": 1001, "Level": 1, "_pad0": 65535, "Exp": 13500, "Hp": 90, "Ds": 30,
        "Ms": 100, "De": 10, "Ev": 5, "Ct": 5, "Attack": 20, "HitRate": 0,
        "_pad1": 786450,
    }
    return {
        "TamerBaseInfo": [dict(stats)],
        "DigimonBaseInfo": [dict(stats, ID=31001, Hp=46)],
        "CsBaseMapInfo": [
            {
                "MapID": 1, "ShoutSec": 15000, "EnableCheckMacro": 0,
                "_pad0": 0, "_pad1": 12,
            }
        ],
        "JumpBooster": [{"ItemID": 4811, "MapIDs": [3, 105, 110]}],
        "Party": [{"distc": 30000.0}],
        "Guild": [
            {
                "Level": 1, "Fame": 0, "ItemNo1": 26001, "ItemCount1": 1,
                "ItemNo2": 0, "ItemCount2": 0, "MasterLevel": 0,
                "NeedPerson": 0, "MaxGuildPerson": 50, "IncMember": 10,
                "MaxGuild2Master": 3,
            }
        ],
        "Limit": [
            {
                "MaxTacticsHouse": 200, "MaxWareHouse": 245, "UnionStore": 10,
                "MaxShareStash": 14, "Consume_XG": 500, "Charge_XG": 500,
            }
        ],
        "Store": [
            {
                "Person_Charge": f32(0.02), "Employment_Charge": f32(0.0),
                "StoreDist": f32(150.0),
                "StoreItems": [
                    {
                        "ItemID": 0, "DigimonID": 0, "Scale": f32(0.0),
                        "SlotCount": 3, "FileName": "Base",
                    }
                ],
            }
        ],
        "PaneltyInfo": [{"PaneltyLevel": 1, "Exp": 100, "Drop": 100}],
        "EvolutionBaseApply": [
            {"EvolutionType": 1, "EvolutionName": "Digi-Tama", "EvolutionApplyValue": 100}
        ],
        "DigimonEvoMaxSkill": [
            {"EvoType": 1, "SkillExpStartLv": 1, "SkillMaxLvs": [1]}
        ],
        "ExpansionData": [
            {"OpenItemSubType": 20201, "ExpansionRank": 1, "EvoType": [3, 4, 5, 6]}
        ],
    }


class DMBaseCodecTests(unittest.TestCase):
    def test_roundtrip(self) -> None:
        codec = DMBaseCodec()
        sections = dmbase_sections()
        self.assertEqual(codec.decode(codec.encode(sections))["sections"], sections)

    def test_section_names_follow_the_xml_documents(self) -> None:
        self.assertEqual(
            DMBaseCodec().sections,
            ("TamerBaseInfo", "DigimonBaseInfo", "CsBaseMapInfo", "JumpBooster", "Party",
             "Guild", "Limit", "Store", "PaneltyInfo", "EvolutionBaseApply",
             "DigimonEvoMaxSkill", "ExpansionData"),
        )

    def test_encoded_size_of_the_sample(self) -> None:
        # 4+40 tamer, 4+40 digimon, 4+12 map, 4+(8+12) booster, 4 party,
        # 4+44 guild, 16 limit, 12+4+(16+128) store, 4+12 panelty,
        # 4+(4+4+18+4) evolution ("Digi-Tama" is 9 characters),
        # 4+(12+4) skill levels, 4+(8+4+16) expansion.
        self.assertEqual(len(DMBaseCodec().encode(dmbase_sections())), 458)

    def test_single_record_sections_are_enforced(self) -> None:
        for name in ("Party", "Limit", "Store"):
            for replacement in ([], [{}, {}]):
                sections = dmbase_sections()
                sections[name] = replacement
                with self.assertRaises(FormatError, msg=name):
                    DMBaseCodec().encode(sections)

    def test_jumpbooster_map_ids_keep_their_order(self) -> None:
        sections = dmbase_sections()
        sections["JumpBooster"] = [
            {"ItemID": 5005, "MapIDs": [3, 105, 110, 1100]},
            {"ItemID": 5006, "MapIDs": []},
        ]
        decoded = DMBaseCodec().decode(DMBaseCodec().encode(sections))["sections"]
        self.assertEqual(decoded["JumpBooster"], sections["JumpBooster"])

    def test_store_file_name_is_a_128_byte_utf16_field(self) -> None:
        data = DMBaseCodec().encode(dmbase_sections())
        self.assertIn("Base".encode(UTF16) + b"\0" * 8, data)

        # 63 characters + terminator fill the buffer; anything longer is cut off.
        sections = dmbase_sections()
        sections["Store"][0]["StoreItems"][0]["FileName"] = "x" * 63
        decoded = DMBaseCodec().decode(DMBaseCodec().encode(sections))["sections"]
        self.assertEqual(decoded["Store"][0]["StoreItems"][0]["FileName"], "x" * 63)

        sections["Store"][0]["StoreItems"][0]["FileName"] = "x" * 70
        data = DMBaseCodec().encode(sections)
        self.assertIn(("x" * 64).encode(UTF16), data)

    def test_derived_counts_are_not_stored(self) -> None:
        sections = dmbase_sections()
        self.assertNotIn("mapcount", sections["JumpBooster"][0])
        self.assertNotIn("nSubCount", sections["DigimonEvoMaxSkill"][0])
        decoded = DMBaseCodec().decode(DMBaseCodec().encode(sections))["sections"]
        self.assertEqual(list(decoded["JumpBooster"][0]), ["ItemID", "MapIDs"])

    def test_panelty_fields_follow_the_client_struct(self) -> None:
        # CsBaseMng::sPLAY_PANELTY is (level, exp, drop) and the whole struct is
        # written with fwrite; the old reader had exp and drop swapped.
        record = DMBaseCodec().decode(DMBaseCodec().encode(dmbase_sections()))["sections"][
            "PaneltyInfo"
        ][0]
        self.assertEqual(list(record), ["PaneltyLevel", "Exp", "Drop"])

    def test_base_stats_end_with_the_struct_padding(self) -> None:
        # CsBase::sINFO: __int64 exp forces 2 bytes of padding after s_nLevel and
        # the struct is 8 byte aligned, so 4 more bytes follow s_nHitRate.
        record = dmbase_sections()["TamerBaseInfo"][0]
        self.assertEqual(list(record)[-4:], ["Ct", "Attack", "HitRate", "_pad1"])
        data = DMBaseCodec().encode(dmbase_sections())
        # count + 40 byte struct: level at 4, padding at 6, attack/hitrate at 32
        self.assertEqual(data[4 + 32 : 4 + 36], (20).to_bytes(2, "little") + b"\0\0")
        self.assertEqual(data[4 + 36 : 4 + 40], (786450).to_bytes(4, "little"))


def cashinfo(name: str = "Item") -> dict:
    """One ``CASHINFO`` record as the reader produces it."""

    return {
        "Name": name,
        "Description": "Desc",
        "Enabled": 1,
        "unique_id": 7,
        "Date1": "2000-01-01 00:00:00",
        "Date2": "2010-12-31 23:59:59",
        "PurchaseCashType": 1,
        "StandardSellingPrice": 100,
        "RealSellingPrice": 90,
        "SalePersent": 10,
        "IconID": 5,
        "MaskType": 1,
        "DispType": 2,
        "DispCount": 3,
        "CashItems": [{"ItemID": 1001, "Amount": 1}],
    }


def cashshop_sections(shops: int = 1) -> dict:
    """Minimal valid ``CashShop.bin``: *shops* document groups, one banner."""

    def document(index: int) -> dict:
        return {
            "Main": {
                "unknow": 0,
                "unknow1": 0,
                "unknow2": 0,
                "MainTitle": "Main",
                "unknow3": 0,
                "unknow4": 0,
                "MainNewTitle": "NEW",
                "MainNewItems": [{"ProductID": 1}, {"ProductID": 2}],
                "unknow5": 1,
                "MainHotTitle": "HOT",
                "MainHotItems": [],
                "unknow6": 2,
                "MainEventTitle": "EVENT",
                "MainEventItems": [{"ProductID": 3}],
                "unknow7": 4,
                "MainUnknowItems": [],
                "unknow8": 5,
            },
            "TamerInfo": {
                "CategoryName": "Tamer",
                "unknow": 0,
                "unknow1": 0,
                "AllName": "All",
                "unknow2": 1,
                "unknow3": 2,
                "ExpasionName": "Expansion",
                "ExpansionItems": [
                    {"CashShopID": 11 + index, "CashInfo": [cashinfo()]}
                ],
                "unknow4": 3,
                "ExpName": "Exp",
                "ExpItems": [],
                "unknow5": 4,
                "MovimentName": "Moviment",
                "MovimentItems": [],
                "unknow6": 5,
                "ChatName": "Chat",
                "ChatItems": [],
                "unknow7": 6,
                "EtcName": "Etc",
                "EtcItems": [],
            },
            "DigimonInfo": {
                "unknow": 0,
                "CategoryName": "Digimon",
                "unknow1": 0,
                "unknow2": 0,
                "AllName": "All",
                "unknow3": 0,
                "unknow4": 0,
                "DigiEggName": "DigiEgg",
                "DigiEgg": [],
                "unknow5": 0,
                "EvolutionName": "Evolution",
                "EvolutionItems": [],
                "unknow6": 0,
                "HatchName": "Hatch",
                "HatchItems": [],
                "unknow7": 0,
                "ReinforcedName": "Reinforce",
                "ReinforcedItems": [],
                "unknow8": 0,
                "RidingName": "Riding",
                "RidingItems": [],
                "unknow9": 0,
                "EtcName": "Etc",
                "EtcItems": [],
            },
            "AvatarInfo": {
                "unknow": 0,
                "CategoryName": "Avatar",
                "unknow1": 0,
                "unknow2": 0,
                "AllName": "All",
                "unknow3": 0,
                "unknow4": 0,
                "ReinforcedName": "Reinforce",
                "ReinforcedItems": [],
                "unknow5": 0,
                "HeadName": "Head",
                "HeadItems": [],
                "unknow6": 0,
                "TopName": "Top",
                "TopItems": [],
                "unknow7": 0,
                "BottomName": "Bottom",
                "BottomItems": [],
                "unknow8": 0,
                "GlovesName": "Gloves",
                "GlovesItems": [],
                "unknow9": 0,
                "ShoesName": "Shoes",
                "ShoesItems": [],
                "unknow10": 0,
                "FashionName": "Fashion",
                "FashionItems": [],
                "unknow11": 0,
                "CostumeName": "Costume",
                "CostumeItems": [],
            },
            "PackageInfo": {
                "unknow": 0,
                "CategoryName": "Packages",
                "unknow1": 0,
                "unknow2": 0,
                "AllName": "Package",
                "PackageItems": [],
            },
        }

    sections: dict[str, list] = {name: [] for name in CashShopCodec().shop_sections}
    for index in range(shops):
        for name, record in document(index).items():
            sections[name].append(record)
    sections["WebData"] = [
        {
            "TableType": 0,
            "CashWebInfo": [{"Size": 5, "sWebImageFile": "b.tga", "Size2": 4,
                             "sWebLinkUrl": "link"}],
        }
    ]
    return sections

class CashShopCodecTests(unittest.TestCase):
    def test_roundtrip(self) -> None:
        codec = CashShopCodec()
        sections = cashshop_sections(shops=2)
        self.assertEqual(codec.decode(codec.encode(sections))["sections"], sections)

    def test_section_names_follow_the_shop_documents(self) -> None:
        self.assertEqual(
            CashShopCodec().sections,
            ("Main", "TamerInfo", "DigimonInfo", "AvatarInfo", "PackageInfo", "WebData"),
        )

    def test_shop_count_is_derived_from_the_document_lists(self) -> None:
        for shops in (1, 3):
            data = CashShopCodec().encode(cashshop_sections(shops=shops))
            self.assertEqual(int.from_bytes(data[:4], "little"), shops)
            self.assertEqual(len(CashShopCodec().decode(data)["sections"]["Main"]), shops)

    def test_every_shop_needs_one_record_per_document(self) -> None:
        sections = cashshop_sections(shops=2)
        sections["AvatarInfo"].pop()
        with self.assertRaises(FormatError):
            CashShopCodec().encode(sections)

    def test_layout_follows_the_csharp_reader(self) -> None:
        data = CashShopCodec().encode(cashshop_sections())
        reader = Reader(data)
        self.assertEqual(reader.i32(), 1)  # shop count

        # Main: three ints, title, two ints, title, product id lists.
        self.assertEqual([reader.i32() for _ in range(3)], [0, 0, 0])
        self.assertEqual(read_text(reader), "Main")
        self.assertEqual([reader.i32() for _ in range(2)], [0, 0])
        self.assertEqual(read_text(reader), "NEW")
        self.assertEqual(reader.i32(), 2)
        self.assertEqual([reader.i64() for _ in range(2)], [1, 2])
        self.assertEqual(reader.i32(), 1)
        self.assertEqual(read_text(reader), "HOT")
        self.assertEqual(reader.i32(), 0)
        self.assertEqual(reader.i32(), 2)
        self.assertEqual(read_text(reader), "EVENT")
        self.assertEqual(reader.i32(), 1)
        self.assertEqual(reader.i64(), 3)
        self.assertEqual(reader.i64(), 4)  # unknow7 is a long
        self.assertEqual(reader.i32(), 0)  # MainUnknowItems
        self.assertEqual(reader.i32(), 5)

        # TamerInfo starts with its caption, there is no leading int.
        self.assertEqual(read_text(reader), "Tamer")
        self.assertEqual([reader.i32() for _ in range(2)], [0, 0])
        self.assertEqual(read_text(reader), "All")
        self.assertEqual([reader.i32() for _ in range(2)], [1, 2])
        self.assertEqual(read_text(reader), "Expansion")
        self.assertEqual(reader.i32(), 1)  # ExpansionItems count
        self.assertEqual(reader.i32(), 11)  # CashShopId
        self.assertEqual(reader.i32(), 1)  # CashInfo count

        # CASHINFO: Name, Description, Enabled (byte!), unique_id, two 64 byte
        # ASCII dates, eight ints, item list.
        self.assertEqual(read_text(reader), "Item")
        self.assertEqual(read_text(reader), "Desc")
        self.assertEqual(reader.u8(), 1)
        self.assertEqual(reader.i32(), 7)
        self.assertEqual(reader.zstring("ascii", 64), "2000-01-01 00:00:00")
        self.assertEqual(reader.zstring("ascii", 64), "2010-12-31 23:59:59")
        self.assertEqual(
            [reader.i32() for _ in range(8)], [1, 100, 90, 10, 5, 1, 2, 3]
        )
        self.assertEqual(reader.i32(), 1)  # CashItems count
        self.assertEqual(reader.i32(), 1001)
        self.assertEqual(reader.i32(), 1)

    def test_cashinfo_keys_follow_the_file(self) -> None:
        codec = CashShopCodec()
        decoded = codec.decode(codec.encode(cashshop_sections()))["sections"]
        record = decoded["TamerInfo"][0]["ExpansionItems"][0]["CashInfo"][0]
        self.assertEqual(
            list(record),
            [
                "Name",
                "Description",
                "Enabled",
                "unique_id",
                "Date1",
                "Date2",
                "PurchaseCashType",
                "StandardSellingPrice",
                "RealSellingPrice",
                "SalePersent",
                "IconID",
                "MaskType",
                "DispType",
                "DispCount",
                "CashItems",
            ],
        )
        # cashshop_id is copied from the parent group by the C# reader, the
        # other declared members are never read.
        for unused in ("cashshop_id", "CashName", "bActive", "Desc"):
            self.assertNotIn(unused, record)
        self.assertNotIn("UnknowItemsTitle", decoded["Main"][0])

    def test_item_lists_are_nested_by_group(self) -> None:
        sections = cashshop_sections()
        sections["TamerInfo"][0]["ExpansionItems"][0]["CashInfo"][0]["CashItems"] = [
            {"ItemID": 5, "Amount": 6},
            {"ItemID": 7, "Amount": 8},
        ]
        decoded = CashShopCodec().decode(CashShopCodec().encode(sections))["sections"]
        self.assertEqual(
            decoded["TamerInfo"][0]["ExpansionItems"][0]["CashInfo"][0]["CashItems"],
            [{"ItemID": 5, "Amount": 6}, {"ItemID": 7, "Amount": 8}],
        )

    def test_web_data_sizes_are_kept(self) -> None:
        sections = cashshop_sections()
        web = sections["WebData"][0]
        self.assertNotIn("m_mapWebData", web)
        banner = CashShopCodec().decode(CashShopCodec().encode(sections))["sections"][
            "WebData"
        ][0]["CashWebInfo"][0]
        self.assertEqual((banner["Size"], banner["Size2"]), (5, 4))

        # A shorter text is NUL padded to the declared size.
        web["CashWebInfo"][0].update(Size=8, sWebImageFile="c.tga")
        data = CashShopCodec().encode(sections)
        self.assertIn(b"c.tga\0\0\0", data)
        banner = CashShopCodec().decode(data)["sections"]["WebData"][0]["CashWebInfo"][0]
        self.assertEqual((banner["Size"], banner["sWebImageFile"]), (8, "c.tga"))

        # A longer one grows the field instead of being truncated.
        web["CashWebInfo"][0].update(Size=2, sWebImageFile="long.tga")
        banner = CashShopCodec().decode(CashShopCodec().encode(sections))["sections"][
            "WebData"
        ][0]["CashWebInfo"][0]
        self.assertEqual((banner["Size"], banner["sWebImageFile"]), (8, "long.tga"))

    def test_dates_are_read_with_the_zstring_helper(self) -> None:
        # Garbage behind the terminator is dropped, a recompile writes zeros.
        data = CashShopCodec().encode(cashshop_sections())
        index = data.index(b"2000-01-01 00:00:00\0")
        patched = data[: index + 20] + b"junk" + data[index + 24 :]
        decoded = CashShopCodec().decode(patched)["sections"]
        record = decoded["TamerInfo"][0]["ExpansionItems"][0]["CashInfo"][0]
        self.assertEqual(record["Date1"], "2000-01-01 00:00:00")
        self.assertEqual(
            compare_roundtrip(patched, CashShopCodec().encode(decoded)), ("padding", 4)
        )

    def test_trailing_bytes_are_rejected(self) -> None:
        data = CashShopCodec().encode(cashshop_sections()) + b"\0"
        with self.assertRaises(FormatError):
            CashShopCodec().decode(data)

    def test_missing_section(self) -> None:
        sections = cashshop_sections()
        del sections["WebData"]
        with self.assertRaises(FormatError):
            CashShopCodec().encode(sections)
def buff_record(**overrides) -> dict:
    record = {
        "ID": 1,
        "Name": "Attack Up",
        "Comment": "Increases attack",
        "BuffIcon": 10,
        "BuffType": 2,
        "BuffLifeType": 1,
        "BuffTimeType": 1,
        "MinLv": 5,
        "BuffClass": 3,
        "_pad0": 0,
        "SkillCode": 9001,
        "DigimonSkillCode": 4294967295,
        "Delete": 0,
        "EffectFile": "buff01.tga",
        "_pad1": 0,
        "ConditionLv": 1,
    }
    record.update(overrides)
    return record


class BuffCodecTests(unittest.TestCase):
    def test_record_is_476_bytes(self) -> None:
        sections = {"Buff": [buff_record(), buff_record(ID=2)]}
        data = BuffCodec().encode(sections)
        self.assertEqual(len(data), 4 + 2 * 476)
        self.assertEqual(BuffCodec().decode(data)["sections"], sections)

    def test_strings_are_fixed_buffers(self) -> None:
        data = BuffCodec().encode({"Buff": [buff_record()]})
        # 64 and 128 UTF-16 characters, NUL padded
        self.assertIn("Attack Up".encode(UTF16) + b"\0" * (128 - 18), data)
        self.assertIn("Increases attack".encode(UTF16) + b"\0" * (256 - 34), data)
        self.assertIn(b"buff01.tga\0" + b"\0" * (64 - 11), data)

    def test_buff_class_is_sixteen_bits(self) -> None:
        # The client declares USHORT; the old writer emitted four bytes for the
        # int-typed field and shifted every following record.
        sections = {"Buff": [buff_record(BuffClass=65535)]}
        data = BuffCodec().encode(sections)
        # count, s_dwID, 64 char name, 128 char comment, five u16 fields
        offset = 4 + 2 + 64 * 2 + 128 * 2 + 5 * 2
        self.assertEqual(data[offset : offset + 2], (65535).to_bytes(2, "little"))
        self.assertEqual(BuffCodec().decode(data)["sections"], sections)

    def test_condition_level_follows_the_padding_byte(self) -> None:
        # struct alignment: char[64] ends on an odd offset, USHORT is padded.
        sections = {"Buff": [buff_record(_pad1=0x9A, ConditionLv=3)]}
        data = BuffCodec().encode(sections)
        self.assertEqual(data[4 + 473 : 4 + 476], b"\x9a\x03\x00")
        decoded = BuffCodec().decode(data)["sections"]["Buff"][0]
        self.assertEqual(decoded["ConditionLv"], 3)
        self.assertEqual(decoded["_pad1"], 0x9A)

    def test_missing_and_trailing_bytes(self) -> None:
        with self.assertRaises(FormatError):
            BuffCodec().encode({})
        with self.assertRaises(FormatError):
            BuffCodec().decode(BuffCodec().encode({"Buff": []}) + b"\0")








def ride_record(**overrides) -> dict:
    record = {
        "DigimonID": 31001,
        "ChangeRide": 31002,
        "MoveSpeed": f32(1.5),
        "Comment": "Fast",
        "RideType": 1,
        "AniRate_Run": f32(1.0),
        "Section": 3,
        "NeedCount": 5,
        "Section2": 0,
        "NeedCount2": 0,
    }
    record.update(overrides)
    return record


def achieve_sections() -> dict:
    """A small but valid category tree (root + two categories + two sub-items)."""
    return {
        "AchieveUnknow": [
            {"Name": "", "istChild": 2},
            {"Name": "General", "istChild": 2},
            {"Name": "Tamer Lv", "istChild": 0},
            {"Name": "Digimon Lv", "istChild": 0},
            {"Name": "Quest", "istChild": 0},
        ],
        "Achieve": [
            {
                "QuestID": 1500,
                "Icon": 4,
                "Point": 99,
                "Display": 1,
                "Display2": 0,
                "Name": "Ranker",
                "Comment": "Reach the ranking",
                "Title": "Honor Guardian",
                "Group": 1,
                "SubGroup": 7,
                "Type": 1,
                "BuffCode": 0,
            }
        ],
    }


#: 5 category records * (32 TCHAR name + int32 child count)
TYPE_BYTES = 5 * 68


class AchieveCodecTests(unittest.TestCase):
    def test_roundtrip(self) -> None:
        sections = achieve_sections()
        data = AchieveCodec().encode(sections)
        self.assertEqual(AchieveCodec().decode(data)["sections"], sections)

    def test_sizes(self) -> None:
        sections = achieve_sections()
        data = AchieveCodec().encode(sections)
        # category tree (no count in front) + int32 count + 796 byte record
        self.assertEqual(len(data), TYPE_BYTES + 4 + 796)
        self.assertEqual(data[TYPE_BYTES : TYPE_BYTES + 4], (1).to_bytes(4, "little"))
        self.assertEqual(
            data[TYPE_BYTES + 4 : TYPE_BYTES + 8], (1500).to_bytes(4, "little")
        )

    def test_child_counts_must_describe_the_list(self) -> None:
        # a category claiming a child that is not in the list
        sections = achieve_sections()
        sections["AchieveUnknow"][0]["istChild"] = 5
        with self.assertRaises(FormatError):
            AchieveCodec().encode(sections)

        # a record that no parent reaches
        sections = achieve_sections()
        sections["AchieveUnknow"][0]["istChild"] = 1
        sections["AchieveUnknow"][1]["istChild"] = 0
        with self.assertRaises(FormatError):
            AchieveCodec().encode(sections)

        # an empty tree
        sections = achieve_sections()
        sections["AchieveUnknow"] = []
        with self.assertRaises(FormatError):
            AchieveCodec().encode(sections)

    def test_point_is_sixteen_bits(self) -> None:
        sections = achieve_sections()
        sections["Achieve"][0]["Point"] = 40000
        data = AchieveCodec().encode(sections)
        # head: quest id, icon, point (u16), display, display2
        self.assertEqual(
            data[TYPE_BYTES + 4 + 8 : TYPE_BYTES + 4 + 10], (40000).to_bytes(2, "little")
        )
        self.assertEqual(
            AchieveCodec().decode(data)["sections"]["Achieve"][0]["Point"], 40000
        )

    def test_strings_stop_at_the_first_nul(self) -> None:
        # The client reads s_szTitle as a C string, so an empty title followed by
        # the leftovers of an older revision must decode as "" (the old C#
        # reader skipped the NUL and returned "ronze Tamer").
        stale = b"\0\0" + "ronze Tamer".encode(UTF16) + b"\0\0"
        data = (
            (1505).to_bytes(4, "little")
            + (0).to_bytes(4, "little")
            + (3).to_bytes(2, "little")
            + b"\x01\x00"
            + "Lv 20".encode(UTF16).ljust(128, b"\0")
            + "Tamer reached level 20".encode(UTF16).ljust(512, b"\0")
            + stale.ljust(128, b"\0")
            + b"\0" * 16
        )
        record = read_fields(Reader(data, "Achieve.bin"), ACHIEVE_FIELDS)
        self.assertEqual(record["Name"], "Lv 20")
        self.assertEqual(record["Comment"], "Tamer reached level 20")
        self.assertEqual(record["Title"], "")

class SimpleCodecTests(unittest.TestCase):
    """The single section formats that are a plain ``count`` + fixed records."""

    def test_uitext_keeps_the_raw_text_length(self) -> None:
        sections = {
            "UIText": [
                {"ID": 1234567890123, "Text": "Hello"},
                {"ID": 0, "Text": "Hi\0there"},
            ]
        }
        data = UITextCodec().encode(sections)
        # count + (int64 + int32 + UTF-16) per record, NULs included
        self.assertEqual(len(data), 4 + (8 + 4 + 10) + (8 + 4 + 16))
        self.assertEqual(UITextCodec().decode(data)["sections"], sections)

    def test_ride_record_is_a_1060_byte_block(self) -> None:
        sections = {"Ride": [ride_record(), ride_record(Comment="")]}
        data = RideCodec().encode(sections)
        self.assertEqual(len(data), 4 + 2 * 1060)
        decoded = RideCodec().decode(data)["sections"]["Ride"]
        self.assertEqual(decoded[0]["Comment"], "Fast")
        self.assertEqual(decoded[0]["MoveSpeed"], f32(1.5))
        # 512 UTF-16 characters, NUL padded like the old Array.Resize writer.
        self.assertIn("Fast".encode(UTF16) + b"\0" * (1024 - 8), data)

    def test_ride_comment_is_a_fixed_buffer(self) -> None:
        # 512 UTF-16 characters fill the buffer; a longer text is truncated to it.
        sections = {"Ride": [ride_record(Comment="x" * 510)]}
        data = RideCodec().encode(sections)
        self.assertEqual(len(data), 4 + 1060)
        decoded = RideCodec().decode(data)["sections"]["Ride"]
        self.assertEqual(decoded[0]["Comment"], "x" * 510)

        sections = {"Ride": [ride_record(Comment="x" * 600)]}
        decoded = RideCodec().decode(RideCodec().encode(sections))["sections"]["Ride"]
        self.assertEqual(decoded[0]["Comment"], "x" * 512)

    def test_mapnpc_record_order_and_size(self) -> None:
        sections = {
            "MapNpc": [
                {
                    "NpcID": 7,
                    "MapID": 3,
                    "InitPosX": 100,
                    "InitPosY": 200,
                    "Rotation": f32(90.0),
                }
            ]
        }
        data = MapNpcCodec().encode(sections)
        self.assertEqual(len(data), 4 + 20)
        # The reader takes NpcID first even though the XML prints MapID first.
        self.assertEqual(data[4:8], (7).to_bytes(4, "little"))
        self.assertEqual(data[8:12], (3).to_bytes(4, "little"))
        self.assertEqual(MapNpcCodec().decode(data)["sections"], sections)

    def test_mapportal_group_count_is_the_portal_list_length(self) -> None:
        info = {name: 0 for name, _ in PORTAL_INFO_FIELDS}
        info["PortalID"] = 11
        sections = {"MapPortal": [{"PortalInfos": [info, dict(info, PortalID=12)]}]}
        data = MapPortalCodec().encode(sections)
        self.assertEqual(len(data), 4 + 4 + 2 * 60)
        self.assertEqual(data[4:8], (2).to_bytes(4, "little"))
        self.assertNotIn("pMapGroup", sections["MapPortal"][0])
        decoded = MapPortalCodec().decode(data)["sections"]
        self.assertEqual(decoded["MapPortal"][0]["PortalInfos"][1]["PortalID"], 12)

    def test_mapobject_nested_counts_and_factor_order(self) -> None:
        sections = {
            "MapObject": [
                {
                    "MapID": 13,
                    "MapSourceObject": [
                        {
                            "ObjectID": 10511,
                            "OrderObject": [
                                {
                                    "OrderID": 1,
                                    "Object": [
                                        {
                                            "OpenType": 1,
                                            "FactorCnt": 500,
                                            "Factor": 31420,
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ]
        }
        data = MapObjectCodec().encode(sections)
        # count, MapId/Size, ObjectId/ObjectCount, OrderId/FactorSize, 3 * int32
        self.assertEqual(len(data), 4 + 8 + 8 + 8 + 12)
        words = [int.from_bytes(data[i : i + 4], "little") for i in range(4, 4 + 36, 4)]
        # ... and s_nFactorCnt is the *first* of the two trailing values.
        self.assertEqual(words, [13, 1, 10511, 1, 1, 1, 1, 500, 31420])
        self.assertEqual(MapObjectCodec().decode(data)["sections"], sections)

    def test_trailing_bytes_are_rejected(self) -> None:
        for codec, name in (
            (UITextCodec(), "UIText"),
            (RideCodec(), "Ride"),
            (MapNpcCodec(), "MapNpc"),
            (MapPortalCodec(), "MapPortal"),
            (MapObjectCodec(), "MapObject"),
        ):
            data = codec.encode({name: []}) + b"\0"
            with self.assertRaises(FormatError, msg=name):
                codec.decode(data)

    def test_missing_section(self) -> None:
        for codec in (UITextCodec(), RideCodec(), MapNpcCodec(), MapPortalCodec(),
                      MapObjectCodec()):
            with self.assertRaises(FormatError, msg=codec.name):
                codec.encode({})



class NewFormatTests(unittest.TestCase):
    """``MapList``, ``WorldMap`` and ``ExtraExchange`` (the newest ports)."""

    def test_maplist_writes_byte_and_character_lengths(self) -> None:
        record = {
            "MapID": 1,
            "MapName": "DATS_001",
            "MapPath": "Data\\Map\\x.nif",
            "BGSound": "s.mp3",
            "Width": 60000,
            "Height": 60000,
            "MapDescription_Eng": "Dats Center",
            "MapDescription": "닷트본부",
            "ResurrectionMapID": 1,
            "MapRegionID": 0,
            "FatigueType": 0,
            "FatigueDeBuff": 0,
            "FatigueStartTime": 5,
            "FatigueAddTime": 5,
            "FatigueAddPoint": -10,
            "CameraMaxLevel": 2,
            "XgConsumeType": 0,
            "BattleTagUse": 0,
        }
        data = MapListCodec().encode({"MapList": [record]})
        self.assertEqual(MapListCodec().decode(data)["sections"]["MapList"], [record])
        # count, MapID, then int32 byte length + the ASCII bytes
        self.assertEqual(data[4:8], (1).to_bytes(4, "little"))
        self.assertEqual(data[8:12], (8).to_bytes(4, "little"))
        self.assertEqual(data[12:20], b"DATS_001")
        # the UTF-16 description stores its length in characters
        index = data.index("Dats Center".encode(UTF16))
        self.assertEqual(data[index - 4 : index], (11).to_bytes(4, "little"))

    def test_worldmap_record_sizes(self) -> None:
        world = {
            "ID": 1,
            "Name": "Real World",
            "Comment": "c",
            "WorldType": 1,
            "UI_X": 2,
            "UI_Y": 3,
        }
        area = {
            "d_nMapID": 1,
            "d_szName": "a",
            "d_szComment": "b",
            "d_nAreaType": 1,
            "d_nFieldType": 2,
            "d_nFTDetail": 3,
            "d_nUI_X": 4,
            "d_nUI_Y": 5,
            "d_fGaussianBlur": [f32(1.0), f32(2.0), f32(0.5)],
        }
        sections = {"WorldMapInfo": [world], "AreaMapInfo": [area]}
        data = WorldMapCodec().encode(sections)
        # 4 + (2 + 96 + 512 + 2*3) world + 4 + (2 + 96 + 512 + 2 + 4 + 2*2 + 12) area
        self.assertEqual(len(data), 4 + 616 + 4 + 632)
        self.assertEqual(WorldMapCodec().decode(data)["sections"], sections)

    def test_worldmap_area_needs_three_blur_values(self) -> None:
        area = {
            "d_nMapID": 1,
            "d_szName": "a",
            "d_szComment": "b",
            "d_nAreaType": 1,
            "d_nFieldType": 2,
            "d_nFTDetail": 3,
            "d_nUI_X": 4,
            "d_nUI_Y": 5,
            "d_fGaussianBlur": [f32(1.0)],
        }
        with self.assertRaises(FormatError):
            WorldMapCodec().encode({"WorldMapInfo": [], "AreaMapInfo": [area]})

    def test_extra_exchange_nesting_and_counts(self) -> None:
        exchange = {
            "DigimonID": 75020,
            "MaterialType": 2,
            "RequiredLevel": 0,
            "Price": 0,
            "WayType": 2,
            "ItemCount": 1,
            "MaterialData": [{"ItemID": 98701, "ItemCount": 1}],
            "MaterialCount": 1,
            "SubMaterialData": [{"ItemID": 98700, "ItemCount": 1}],
        }
        npc = {
            "NpcID": 90005,
            "ExtraExchangesID": [{"ID": 1, "ExtraExchange": [exchange]}],
        }
        sections = {"ExtraExchangeNPC": [npc]}
        data = ExtraExchangeCodec().encode(sections)
        # count, NpcId, idCount, Id, exchangeCount, exchange header (20 bytes),
        # one material (8), MaterialCount, one sub material (8)
        self.assertEqual(len(data), 4 + 4 + 4 + 2 + 4 + 20 + 8 + 4 + 8)
        self.assertEqual(ExtraExchangeCodec().decode(data)["sections"], sections)

    def test_extra_exchange_uses_the_client_field_widths(self) -> None:
        # CsExtraEvolutionMng: DWORD dwNPCIdx, USHORT usExchangeType,
        # DWORD dwObjectIDX / dwNeedMoney, USHORT usMaterialType / usWayType.
        exchange = {
            "DigimonID": 0xFFFFFFFF,
            "MaterialType": 0xFFFF,
            "RequiredLevel": -1,
            "Price": 0xFFFFFFFF,
            "WayType": 0xFFFF,
            "ItemCount": 0,
            "MaterialData": [],
            "MaterialCount": 0,
            "SubMaterialData": [],
        }
        npc = {
            "NpcID": 0xFFFFFFFF,
            "ExtraExchangesID": [{"ID": 0xFFFF, "ExtraExchange": [exchange]}],
        }
        data = ExtraExchangeCodec().encode({"ExtraExchangeNPC": [npc]})
        decoded = ExtraExchangeCodec().decode(data)["sections"]["ExtraExchangeNPC"]
        self.assertEqual(decoded[0]["NpcID"], 0xFFFFFFFF)
        self.assertEqual(decoded[0]["ExtraExchangesID"][0]["ID"], 0xFFFF)
        self.assertEqual(decoded[0]["ExtraExchangesID"][0]["ExtraExchange"][0], exchange)


class ServerPortTests(unittest.TestCase):
    """The formats unlocked by the ``the DMO server`` bin loaders and MISDMO schemas.

    Each case builds the smallest legal file for the layout, checks that the
    decode/encode round-trip is byte identical and that the record stride matches
    the client ``sizeof`` (the numbers that pin the layout of the shipped files).
    """

    def test_nature_matrix_and_element_table(self) -> None:
        row = struct.pack("<H11h", 16, 0, 25, -25, 0, 0, 0, 0, 0, 0, 0, 0)
        table = struct.pack("<i", 1) + struct.pack("<ii", 0, 1)
        table += struct.pack("<ii", 0, 1) + struct.pack("<ii", 0, 100)
        data = struct.pack("<i", 1) + row + table
        sections = NatureCodec().decode(data)["sections"]
        self.assertEqual(sections["Nature"][0]["Element"][1:3], [25, -25])
        self.assertEqual(
            sections["BaseElement"][0]["Element"][0]["Point"], [{"TargetType": 0, "Point": 100}]
        )
        self.assertEqual(NatureCodec().encode(sections), data)

    def test_map_region_group_record_sizes(self) -> None:
        data = (
            struct.pack("<ii", 1, 1) + bytes(604)
            + struct.pack("<ii", 1, 1) + bytes(16)
            + struct.pack("<ii", 1, 1) + bytes(52)
        )
        sections = MapRegionCodec().decode(data)["sections"]
        self.assertEqual([len(s["Info"]) for s in sections["Region"]], [1])
        self.assertEqual(MapRegionCodec().encode(sections), data)

    def test_map_monster_list_row_stride(self) -> None:
        data = (
            struct.pack("<i", 1)                       # file tables
            + struct.pack("<Ii", 13005, 1)             # FileID, buckets
            + struct.pack("<Ii", 2100, 1)              # map, spawn rows
            + bytes(48)                                # CsMapMonster::sINFO
        )
        sections = MapMonsterListCodec().decode(data)["sections"]
        row = sections["MapMonsterList"][0]["MapInformation"][0]["Monsters"][0]
        self.assertEqual(row["MapID"], 0)
        self.assertIn("u10", row)
        self.assertEqual(MapMonsterListCodec().encode(sections), data)

    def test_digimon_list_stride(self) -> None:
        data = struct.pack("<i", 1) + bytes(572)
        sections = DigimonListCodec().decode(data)["sections"]
        self.assertEqual(len(sections["Digimon_List"][0]["Skill"]), 4)
        self.assertEqual(DigimonListCodec().encode(sections), data)

    def test_digimon_evo_tree_and_battle_sections(self) -> None:
        data = struct.pack("<i", 1) + struct.pack("<IIi", 10001, 0, 1) + bytes(328)
        data += struct.pack("<i", 1) + struct.pack("<H", 500) + bytes(48)
        sections = DigimonEvoCodec().decode(data)["sections"]
        self.assertEqual(len(sections["DigimonEvo"][0]["EvolveObj"][0]["m_nEvolutionList"]), 9)
        self.assertEqual(DigimonEvoCodec().encode(sections), data)

    def test_skill_section_strides(self) -> None:
        data = struct.pack("<i", 1) + bytes(736)
        data += struct.pack("<i", 1) + bytes(36)
        data += struct.pack("<i", 1) + bytes(64)
        sections = SkillCodec().decode(data)["sections"]
        self.assertEqual(len(sections["Skill"][0]["Apply"]), 3)
        self.assertEqual(len(sections["AreaCheck"][0]["Area"]), 30)
        self.assertEqual(SkillCodec().encode(sections), data)

    def test_monster_section_strides(self) -> None:
        data = struct.pack("<i", 1) + bytes(396)
        data += struct.pack("<i", 1) + bytes(8)
        data += struct.pack("<i", 1) + bytes(144)
        data += struct.pack("<i", 1) + bytes(12)
        sections = MonsterCodec().decode(data)["sections"]
        self.assertEqual(len(sections["MonsterSkill"][0]["NoticeEff_Name"]), 0)
        self.assertEqual(MonsterCodec().encode(sections), data)

    def test_npc_conditional_extras_round_trip(self) -> None:
        record = bytearray(1176)                     # CsNpc::sINFO
        struct.pack_into("<i", record, 8, 3)         # Type = NT_PORTAL
        data = (
            struct.pack("<i", 1) + bytes(record)
            + struct.pack("<ii", 0, 0)               # Portal: _Unk, nData
            + struct.pack("<i", 0)                   # nExtra
            + struct.pack("<i", 0)                   # nModels
            + struct.pack("<i", 0)                   # nEvents
        )
        sections = NpcCodec().decode(data)["sections"]
        self.assertEqual(sections["Npc"][0]["Portal"], {"_Unk": 0, "Data": []})
        self.assertEqual(NpcCodec().encode(sections), data)

    def test_npc_requires_the_conditional_block_for_its_type(self) -> None:
        record = bytearray(1176)
        struct.pack_into("<i", record, 8, 1)         # Type = NT_TRADE (shop)
        data = (
            struct.pack("<i", 1) + bytes(record)
            + struct.pack("<i", 0)                   # Store.Items count
            + struct.pack("<i", 0)                   # nExtra
            + struct.pack("<i", 0)                   # nModels
            + struct.pack("<i", 0)                   # nEvents
        )
        sections = NpcCodec().decode(data)["sections"]
        del sections["Npc"][0]["Store"]
        with self.assertRaises(FormatError):
            NpcCodec().encode(sections)


    def test_new_element_ui_tables(self) -> None:
        attribute = struct.pack("<I", 7) + b"a.tga".ljust(128, b"\0") + struct.pack("<4i", 1, 2, 3, 4)
        nature = struct.pack("<I", 16) + b"b.tga".ljust(128, b"\0")
        nature += struct.pack("<4i", 5, 6, 7, 8) + struct.pack("<f", 90.0)
        data = struct.pack("<i", 1) + attribute + struct.pack("<i", 1) + nature
        self.assertEqual(len(attribute), 148)
        self.assertEqual(len(nature), 152)
        sections = NewElementCodec().decode(data)["sections"]
        self.assertEqual(sections["NatureTypeUI"][0]["Angle"], 90.0)
        self.assertEqual(NewElementCodec().encode(sections), data)


class XmlCheckTableTests(unittest.TestCase):
    """The ``tools/compare_xml.py`` recipe table must stay self consistent.

    The XML those recipes point at is not part of this repository any more, so the
    checks are only *run* when the caller supplies the trees through
    ``BINCONV_XML_DIR`` / ``BINCONV_REF_DIR``; everything else is verified here.
    """

    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(REPO_ROOT / "tools"))
        import compare_xml  # noqa: PLC0415

        cls.table = compare_xml

    def test_every_format_has_a_codec(self) -> None:
        for name in self.table.check_names():
            folder = name if for_stem(name) else None
            if folder is None:
                # ``ItemExchange`` is a section of ItemList, the rest are formats.
                self.assertEqual(name, "ItemExchange", name)
                self.assertIsNotNone(for_stem("ItemList"))
            else:
                self.assertIsNotNone(for_stem(name), name)

    def test_every_check_names_a_known_tree(self) -> None:
        for name in self.table.check_names():
            for check in self.table.CHECKS[name]:
                tree = check.path.partition("/")[0]
                with self.subTest(format=name, path=check.path):
                    self.assertIn(tree, ("xml", "ref"))
                    self.assertTrue(check.path.partition("/")[2], check.path)

    def test_alias_values_are_xml_names_not_json_keys(self) -> None:
        for name in self.table.check_names():
            for check in self.table.CHECKS[name]:
                for json_key, xml_name in check.alias.items():
                    self.assertNotEqual(
                        json_key, xml_name, f"{name}: alias maps {xml_name} to itself"
                    )

    def test_known_gaps_have_a_reason(self) -> None:
        for name in self.table.check_names():
            for check in self.table.CHECKS[name]:
                if check.known:
                    self.assertGreater(len(check.known), 20, f"{name}: explain the gap")

    def test_documented_checks_run_when_the_trees_are_supplied(self) -> None:
        import os  # noqa: PLC0415

        trees = {}
        for key, variable in (("xml", "BINCONV_XML_DIR"), ("ref", "BINCONV_REF_DIR")):
            value = os.environ.get(variable)
            if value:
                trees[key] = Path(value)
        if not trees:
            self.skipTest("set BINCONV_XML_DIR / BINCONV_REF_DIR to run the XML checks")
        self.assertEqual(self.table.run_checks(REPO_ROOT, ["all"], 3, trees), 0)


class CharCreateTableTests(unittest.TestCase):
    """``CharCreateTable.bin``: two counted lists of variable-length records."""

    def _sections(self) -> dict[str, list[dict]]:
        return {
            "CharacterList": [
                {
                    "TamerID": 80001,
                    "m_bShow": 1,
                    "m_bEnable": 1,
                    "m_nSeasonType": 1,
                    "m_sVoiceFile": "voice\\tamer01.wav",
                    "m_nIconIdx": 3,
                    "CountDC": 2,
                    "ItemID": [17001, 17003],
                }
            ],
            "DigimonList": [
                {
                    "m_digimonID": 31001,
                    "d_bShow": 1,
                    "d_bEnable": 0,
                    "m_sVoiceFile": "",
                }
            ],
        }

    def test_round_trip_keeps_both_lists(self) -> None:
        sections = self._sections()
        data = CharCreateTableCodec().encode(sections)
        self.assertEqual(CharCreateTableCodec().decode(data)["sections"], sections)

    def test_voice_is_length_prefixed_ascii(self) -> None:
        data = CharCreateTableCodec().encode(self._sections())
        # count, id (4..8), two bools (8..10), season (10..14),
        # then int32 length (14..18) + the ASCII bytes
        self.assertEqual(data[4:8], (80001).to_bytes(4, "little"))
        length = int.from_bytes(data[14:18], "little")
        self.assertEqual(length, len("voice\\tamer01.wav"))
        self.assertEqual(data[18 : 18 + length], b"voice\\tamer01.wav")

    def test_costume_count_must_match_the_list(self) -> None:
        sections = self._sections()
        sections["CharacterList"][0]["CountDC"] = 5
        data = CharCreateTableCodec().encode(sections)  # writes len(ItemID) == 2
        decoded = CharCreateTableCodec().decode(data)["sections"]
        self.assertEqual(decoded["CharacterList"][0]["CountDC"], 2)


class LayoutTests(unittest.TestCase):
    def test_section_path(self) -> None:
        self.assertEqual(section_path("ItemTap"), Path("ItemTap.json"))
        self.assertEqual(section_path("Main/CashShop"), Path("Main") / "CashShop.json")
        with self.assertRaises(FormatError):
            section_path("")

    def test_write_and_read_sections(self) -> None:
        sections = {"ItemList": [{"a": 1}], "ItemTap": [{"b": "tap"}]}
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "ItemList"
            written = write_sections(folder, sections, compact=False)
            self.assertEqual(sorted(p.name for p in written), ["ItemList.json", "ItemTap.json"])
            self.assertEqual(read_sections(folder), sections)

    def test_registry_resolves_folders_and_file_names(self) -> None:
        self.assertIsInstance(for_stem("Event"), EventCodec)
        self.assertIs(for_stem("itemlist"), for_stem("ItemList"))
        self.assertEqual(for_stem("Event").bin_name, "Event.bin")
        self.assertIsNone(for_stem("Nope"))

    def test_record_tags_cover_every_section_of_a_tagged_codec(self) -> None:
        tagged = [codec for codec in all_codecs() if codec.record_tags]
        self.assertTrue(tagged, "no codec declares record tags")
        for codec in tagged:
            self.assertEqual(sorted(codec.record_tags), sorted(codec.sections), codec.name)


class CliTests(unittest.TestCase):
    def _workspace(self, root: Path) -> tuple[Path, Path, Path]:
        bin_dir = root / "bin"
        json_dir = root / "json"
        out_dir = root / "bin_out"
        bin_dir.mkdir()
        (bin_dir / "Quest.bin").write_bytes(QuestCodec().encode(quest_sections()))
        return (bin_dir, json_dir, out_dir)

    def test_decompile_writes_one_file_per_section(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir, json_dir, _ = self._workspace(Path(tmp))
            code = main(["decompile", "--src", str(bin_dir), "--out", str(json_dir)])
            self.assertEqual(code, 0)
            self.assertEqual(
                sorted(p.name for p in (json_dir / "Quest").glob("*.json")), ["Quest.json"]
            )
            # No combined document is produced any more.
            self.assertFalse((json_dir / "Quest.json").exists())

    def test_compile_rebuilds_the_bin_from_the_section_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir, json_dir, out_dir = self._workspace(Path(tmp))
            self.assertEqual(main(["decompile", "--src", str(bin_dir), "--out", str(json_dir)]), 0)
            self.assertEqual(main(["compile", "--src", str(json_dir), "--out", str(out_dir)]), 0)
            self.assertEqual(
                (out_dir / "Quest.bin").read_bytes(), (bin_dir / "Quest.bin").read_bytes()
            )

    def test_decompile_skips_existing_json_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir, json_dir, _ = self._workspace(Path(tmp))
            self.assertEqual(main(["decompile", "--src", str(bin_dir), "--out", str(json_dir)]), 0)
            self.assertEqual(main(["decompile", "--src", str(bin_dir), "--out", str(json_dir)]), 0)
            self.assertEqual(main(["decompile", "--src", str(bin_dir), "--out", str(json_dir),
                                   "--overwrite"]), 0)

    def test_decompile_removes_stale_section_files(self) -> None:
        # A section list can shrink between releases; the leftover file would
        # otherwise be picked up again by ``compile``.
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir, json_dir, _ = self._workspace(Path(tmp))
            folder = json_dir / "Quest"
            folder.mkdir(parents=True)
            (folder / "Old.json").write_text("[]", encoding="utf-8")
            (folder / "Sub").mkdir()
            (folder / "Sub" / "Old.json").write_text("[]", encoding="utf-8")
            self.assertEqual(
                main(["decompile", "--src", str(bin_dir), "--out", str(json_dir),
                      "--overwrite"]),
                0,
            )
            self.assertEqual(sorted(p.name for p in folder.glob("*.json")), ["Quest.json"])
            self.assertFalse((folder / "Sub").exists())

    def test_compile_fails_when_a_section_file_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir, json_dir, out_dir = self._workspace(Path(tmp))
            self.assertEqual(main(["decompile", "--src", str(bin_dir), "--out", str(json_dir)]), 0)
            (json_dir / "Quest" / "Quest.json").unlink()
            self.assertEqual(main(["compile", "--src", str(json_dir), "--out", str(out_dir)]), 1)
            self.assertFalse((out_dir / "Quest.bin").exists())

    def test_event_round_trips_through_the_folder_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            original = EventCodec().encode(event_sections())
            (bin_dir / "Event.bin").write_bytes(original)
            json_dir = root / "json"
            out_dir = root / "bin_out"

            self.assertEqual(main(["decompile", "--src", str(bin_dir), "--out", str(json_dir)]), 0)
            self.assertEqual(
                sorted(p.stem for p in (json_dir / "Event").glob("*.json")),
                sorted(EventCodec().sections),
            )
            self.assertEqual(main(["compile", "--src", str(json_dir), "--out", str(out_dir)]), 0)
            self.assertEqual((out_dir / "Event.bin").read_bytes(), original)

    def test_cashshop_round_trips_through_the_folder_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            original = CashShopCodec().encode(cashshop_sections(shops=2))
            (bin_dir / "CashShop.bin").write_bytes(original)
            json_dir = root / "json"
            out_dir = root / "bin_out"

            self.assertEqual(main(["decompile", "--src", str(bin_dir), "--out", str(json_dir)]), 0)
            self.assertEqual(
                sorted(p.stem for p in (json_dir / "CashShop").glob("*.json")),
                sorted(CashShopCodec().sections),
            )
            self.assertEqual(main(["compile", "--src", str(json_dir), "--out", str(out_dir)]), 0)
            self.assertEqual((out_dir / "CashShop.bin").read_bytes(), original)


class PackTests(unittest.TestCase):
    """The ``.pf``/``.hf`` pair (``binconv/pack.py``, ``binconv/blobs.py``)."""

    def test_name_hash_matches_the_retail_index(self) -> None:
        # Values read out of the shipped Pack03.hf.
        cases = {
            "Talk.bin": 0x515BD0E7,
            "Achieve.bin": 0x632442F0,
            "DigimonEvo.bin": 0xDE9D00CC,
            "Cuid.bin": 0x632AD480,
            "Event.bin": 0xE56D5E5D,
            "NewTutorial.bin": 0xABE373B9,
        }
        for name, expected in cases.items():
            with self.subTest(name=name):
                self.assertEqual(name_hash(name), expected)
                # Case and the folder part do not take part in the hash.
                self.assertEqual(name_hash(f"data\\bin\\english\\{name}"), expected)
                self.assertEqual(name_hash(name.upper()), expected)

    def test_write_and_read_round_trip(self) -> None:
        files = {"data\\bin\\english\\A.bin": b"first", "data\\bin\\english\\B.bin": b"second!"}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            entries = write_pack(files.items(), root / "P.pf", root / "P.hf")
            self.assertEqual([entry.size for entry in entries], [5, 7])
            # The pack is a header plus one chunk and payload per file, nothing else.
            self.assertEqual((root / "P.pf").stat().st_size, 8 + 2 * CHUNK_SIZE + 12)
            self.assertEqual((root / "P.hf").stat().st_size, 8 + 2 * ENTRY_SIZE)

            read = read_pack(root / "P.pf", root / "P.hf")
            self.assertEqual({entry.path: data for entry, data in read}, files)
            self.assertEqual({entry.hash for entry, _ in read},
                             {name_hash("A.bin"), name_hash("B.bin")})

    def test_chunk_path_is_xored_and_offset_follows_the_chunk(self) -> None:
        files = [("data\\bin\\english\\Talk.bin", b"\x00" * 3)]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_pack(files, root / "P.pf", root / "P.hf")
            pack = (root / "P.pf").read_bytes()
            self.assertEqual(struct.unpack_from("<II", pack, 0), (0x10, 0))
            encoded = files[0][0].encode()
            self.assertEqual(pack[8:8 + len(encoded)], bytes(b ^ 0xD0 for b in encoded))
            self.assertEqual(struct.unpack_from("<Ii", pack, 260 + 8),
                             (0, len(encoded)))
            entry = read_index(root / "P.hf")[0]
            self.assertEqual(entry.offset, 8 + CHUNK_SIZE)
            self.assertEqual(entry.flag, 1)
            self.assertEqual(entry.alloc_size, 3)

    def test_index_is_sorted_by_hash(self) -> None:
        files = [(f"data\\bin\\english\\{name}.bin", name.encode())
                 for name in ("Zulu", "alpha", "Mike")]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_pack(files, root / "P.pf", root / "P.hf")
            hashes = [entry.hash for entry in read_index(root / "P.hf")]
            self.assertEqual(hashes, sorted(hashes))

    def test_duplicate_name_hash_is_rejected(self) -> None:
        files = [("data\\bin\\english\\Talk.bin", b"a"), ("other\\Talk.bin", b"b")]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(FormatError):
                write_pack(files, root / "P.pf", root / "P.hf")
            self.assertFalse((root / "P.pf").exists())

    def test_collect_uses_the_ntfs_order(self) -> None:
        # The retail packer walks the folder in FindFirstFile order, which puts
        # '_' after the letters and compares upper-cased.
        names = ["Digimon_Book.bin", "DigimonEvo.bin", "DMBase.bin", "DigimonParcel.bin"]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in names:
                (root / name).write_bytes(name.encode())
            collected = collect(root, ".bin", "data\\bin\\english\\")
            self.assertEqual([path.rsplit("\\", 1)[-1] for path, _ in collected],
                             ["DigimonEvo.bin", "DigimonParcel.bin",
                              "Digimon_Book.bin", "DMBase.bin"])
            self.assertTrue(all(path.startswith("data\\bin\\english\\")
                                for path, _ in collected))

    def test_extract_writes_the_payloads(self) -> None:
        files = {"data\\bin\\english\\A.bin": b"first", "data\\bin\\english\\B.bin": b"second!"}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_pack(files.items(), root / "P.pf", root / "P.hf")
            written = extract(root, root / "out")
            self.assertEqual(sorted(path.name for path in written), ["A.bin", "B.bin"])
            self.assertEqual((root / "out" / "A.bin").read_bytes(), b"first")
            self.assertEqual(extract(root, root / "one", ["B.bin"]),
                             [root / "one" / "B.bin"])

    def test_blob_is_shipped_and_its_size_is_pinned(self) -> None:
        self.assertEqual([blob.name for blob in BLOBS], ["NewTutorial.bin"])
        with tempfile.TemporaryDirectory() as tmp:
            written = copy_into(Path(tmp))
            self.assertEqual([path.name for path in written], ["NewTutorial.bin"])
            self.assertEqual(written[0].stat().st_size, BLOBS[0].size)
            self.assertEqual(written[0].read_bytes(), BLOBS[0].path.read_bytes())

    def test_build_writes_the_tree_and_the_pack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir, json_dir, out_dir = root / "bin", root / "json", root / "bin_out"
            bin_dir.mkdir()
            (bin_dir / "Quest.bin").write_bytes(QuestCodec().encode(quest_sections()))
            self.assertEqual(
                main(["decompile", "--src", str(bin_dir), "--out", str(json_dir)]), 0)
            self.assertEqual(
                main(["build", "--src", str(json_dir), "--out", str(out_dir),
                      "--only", "Quest"]),
                0,
            )
            tree = out_dir / "Pack03" / "Data" / "Bin" / "English"
            self.assertTrue((tree / "Quest.bin").exists())
            self.assertTrue((tree / "NewTutorial.bin").exists())  # the blob is copied
            entries = read_pack(out_dir / "Pack03.pf", out_dir / "Pack03.hf")
            self.assertEqual(sorted(entry.name for entry, _ in entries),
                             ["NewTutorial.bin", "Quest.bin"])
            self.assertTrue(all(entry.path.startswith("data\\bin\\english\\")
                                for entry, _ in entries))
            self.assertEqual((tree / "Quest.bin").read_bytes(),
                             (bin_dir / "Quest.bin").read_bytes())


    def test_patch_without_changes_is_byte_identical(self) -> None:
        files = [(f"data\\bin\\english\\{name}.bin", name.encode() * 3)
                 for name in ("Alpha", "Bravo", "Charlie")]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_pack(files, root / "base.pf", root / "base.hf")
            patch_pack(root / "base.pf", root / "base.hf", files,
                       root / "out.pf", root / "out.hf")
            self.assertEqual((root / "out.pf").read_bytes(), (root / "base.pf").read_bytes())
            self.assertEqual((root / "out.hf").read_bytes(), (root / "base.hf").read_bytes())

    def test_patch_keeps_the_base_index_order(self) -> None:
        # The retail index is *not* sorted by hash, so patching must not re-sort it.
        files = [(f"data\\bin\\english\\{name}.bin", name.encode() * 3)
                 for name in ("Alpha", "Bravo", "Charlie")]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_pack(files, root / "base.pf", root / "base.hf")
            raw = (root / "base.hf").read_bytes()
            head, records = raw[:8], [raw[8 + i * ENTRY_SIZE:8 + (i + 1) * ENTRY_SIZE]
                                      for i in range(3)]
            shuffled = head + records[2] + records[0] + records[1]
            (root / "base.hf").write_bytes(shuffled)

            patch_pack(root / "base.pf", root / "base.hf", files[:1],
                       root / "out.pf", root / "out.hf")
            self.assertEqual((root / "out.hf").read_bytes(), shuffled)

        files = [(f"data\\bin\\english\\{name}.bin", name.encode() * 3)
                 for name in ("Alpha", "Bravo", "Charlie")]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_pack(files, root / "base.pf", root / "base.hf")
            before_payload = {entry.name: data
                              for entry, data in read_pack(root / "base.pf", root / "base.hf")}
            report = patch_pack(
                root / "base.pf", root / "base.hf",
                [("data\\bin\\english\\Bravo.bin", b"NEW"), ("data\\bin\\english\\Delta.bin", b"D")],
                root / "out.pf", root / "out.hf")
            self.assertEqual(report["replaced"], ["Bravo.bin"])
            self.assertEqual(report["added"], ["Delta.bin"])
            self.assertEqual(report["kept"], ["Alpha.bin", "Charlie.bin"])

            after = {entry.name: (entry, data)
                     for entry, data in read_pack(root / "out.pf", root / "out.hf")}
            self.assertEqual(sorted(after), ["Alpha.bin", "Bravo.bin", "Charlie.bin", "Delta.bin"])
            self.assertEqual(after["Bravo.bin"][1], b"NEW")
            self.assertEqual(after["Bravo.bin"][0].size, 3)
            self.assertEqual(after["Delta.bin"][1], b"D")
            # Untouched payloads keep their bytes; the first entry keeps its offset.
            for name in ("Alpha.bin", "Charlie.bin"):
                self.assertEqual(after[name][1], before_payload[name])
            self.assertEqual(after["Alpha.bin"][0].offset, 8 + CHUNK_SIZE)
            # New files are appended after the base payloads.
            self.assertGreater(after["Delta.bin"][0].offset,
                               after["Charlie.bin"][0].offset)
            # The index stays a sorted, well formed table.
            self.assertEqual(len(read_index(root / "out.hf")), 4)

    def test_hash_models_agree_for_the_standard_prefix(self) -> None:
        # The retail seed is the bare-name hash of the folder prefix, so the client
        # source's "whole path, seed 5381" model must land on the same values.
        prefix = "data\\bin\\english\\"
        for name in ("Talk.bin", "NewTutorial.bin", "ItemList.bin", "CashShop.bin"):
            with self.subTest(name=name):
                self.assertEqual(
                    name_hash(name, HASH_SEED),
                    name_hash(prefix + name, PATH_SEED, full_path=True),
                )
        self.assertEqual(name_hash("Talk.bin"), 0x515BD0E7)
        self.assertEqual(name_hash("NewTutorial.bin"), 0xABE373B9)

    def test_hash_seed_option_changes_the_index(self) -> None:
        files = [("data\\bin\\english\\Talk.bin", b"x")]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_pack(files, root / "a.pf", root / "a.hf")
            write_pack(files, root / "b.pf", root / "b.hf", seed=0)
            retail = read_index(root / "a.hf")[0].hash
            custom = read_index(root / "b.hf")[0].hash
            self.assertEqual(retail, name_hash("Talk.bin"))
            self.assertEqual(custom, name_hash("Talk.bin", 0))
            self.assertNotEqual(retail, custom)

    def test_hash_path_option(self) -> None:
        path = "data\\bin\\english\\Talk.bin"
        # Path + the retail seed is the odd one out; path + 5381 is the retail value.
        self.assertNotEqual(name_hash(path, full_path=True), name_hash(path))
        self.assertEqual(name_hash(path, PATH_SEED, full_path=True), name_hash("Talk.bin"))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_pack([(path, b"x")], root / "p.pf", root / "p.hf", full_path=True)
            self.assertEqual(read_index(root / "p.hf")[0].hash, name_hash(path, full_path=True))

    def test_dual_index_adds_nothing_for_the_standard_prefix(self) -> None:
        standard = [("data\\bin\\english\\Talk.bin", b"x")]
        korean = [("data\\bin\\korean\\Talk.bin", b"x")]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_pack(standard, root / "a.pf", root / "a.hf", dual=True)
            # Both models coincide, so the pack is identical to a plain one.
            write_pack(standard, root / "b.pf", root / "b.hf")
            self.assertEqual((root / "a.hf").read_bytes(), (root / "b.hf").read_bytes())
            self.assertEqual(len(read_index(root / "a.hf")), 1)

            # A different prefix makes the path model diverge, so it gets two records.
            write_pack(korean, root / "c.pf", root / "c.hf", dual=True)
            self.assertEqual(len(read_index(root / "c.hf")), 2)
            self.assertEqual(
                {entry.hash for entry in read_index(root / "c.hf")},
                {name_hash("Talk.bin"),
                 name_hash("data\\bin\\korean\\Talk.bin", PATH_SEED, full_path=True)},
            )
            self.assertEqual(
                [entry.name for entry, _ in read_pack(root / "c.pf", root / "c.hf")],
                ["Talk.bin"],
            )


class DocsTests(unittest.TestCase):
    """The markdown must not rot: no dangling links, no paths that do not exist."""

    def _pages(self) -> list[Path]:
        return [REPO_ROOT / "README.md", *sorted((REPO_ROOT / "docs").glob("*.md"))]

    def test_relative_links_resolve(self) -> None:
        missing = []
        for page in self._pages():
            for target in re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", page.read_text(encoding="utf-8")):
                if "://" in target or target.startswith("mailto:"):
                    continue
                if not (page.parent / target).exists():
                    missing.append(f"{page.relative_to(REPO_ROOT).as_posix()} -> {target}")
        self.assertEqual(missing, [])

    def test_no_references_to_removed_trees(self) -> None:
        # ``dmz-client`` / ``dmz-server`` are external checkouts, ``PROGRAM`` and
        # ``reference`` are no longer part of the repository.
        banned = ("dmz-client", "dmz-server", "PROGRAM/", "PROGRAM\\",
                  "reference/csharp", "reference/xml", "reference_harness",
                  "BinXmlConverter.pdb")
        found = []
        for page in self._pages():
            text = page.read_text(encoding="utf-8")
            for needle in banned:
                if needle in text:
                    found.append(f"{page.relative_to(REPO_ROOT).as_posix()}: {needle}")
        self.assertEqual(found, [])

    def test_every_doc_page_has_a_title_and_an_intro(self) -> None:
        for page in self._pages():
            lines = page.read_text(encoding="utf-8").splitlines()
            with self.subTest(page=page.name):
                self.assertTrue(lines[0].startswith("# "), lines[0])
                body = [line for line in lines[1:] if line.strip()][:1]
                self.assertTrue(body and not body[0].startswith(("#", "|", "*", "-")), body)


if __name__ == "__main__":
    unittest.main()

