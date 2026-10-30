"""Unit tests for the converter primitives and a couple of codecs.

Run with:
    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from binconv.binary import FormatError, Reader, UTF16, Writer  # noqa: E402
from binconv.cli import main, read_sections, section_path, write_sections  # noqa: E402
from binconv.codec import compare_roundtrip  # noqa: E402
from binconv.formats import all_codecs, for_stem  # noqa: E402
from binconv.formats.achieve import ACHIEVE_FIELDS, AchieveCodec  # noqa: E402
from binconv.formats.buff import BuffCodec  # noqa: E402
from binconv.formats.cashshop import CashShopCodec  # noqa: E402
from binconv.formats.dmbase import DMBaseCodec  # noqa: E402
from binconv.formats.event import EventCodec  # noqa: E402
from binconv.formats.itemlist import ItemListCodec  # noqa: E402
from binconv.formats.mapnpc import MapNpcCodec  # noqa: E402
from binconv.formats.mapobject import MapObjectCodec  # noqa: E402
from binconv.formats.portal import PORTAL_INFO_FIELDS, MapPortalCodec  # noqa: E402
from binconv.formats.quest import QuestCodec  # noqa: E402
from binconv.formats.ride import RideCodec  # noqa: E402
from binconv.formats.uitext import UITextCodec  # noqa: E402
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


class ItemListLayoutTests(unittest.TestCase):
    def test_item_record_is_1596_bytes(self) -> None:
        from binconv.fields import field_size
        from binconv.formats.itemlist import ITEM_FIELDS

        # 14907 records * 1596 + 4 byte count = 23791576, which is exactly where
        # the ItemTap section starts in PROGRAM/DATA/ItemList.bin.
        self.assertEqual(field_size(ITEM_FIELDS), 1596)

    def test_section_names(self) -> None:
        codec = ItemListCodec()
        self.assertEqual(len(codec.sections), 16)
        self.assertEqual(codec.sections[0], "ItemList")
        self.assertIn("ItemAcessorys", codec.sections)


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
                    {"ConditionType": 1, "ConditionId": 0, "ConditionCount": 0}
                ],
                "QuestGoals": [
                    {
                        "GoalType": 1,
                        "GoalId": 20001,
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
        return [first] + [{"ItemId": 0, "ItemCount": 0}] * (count - 1)

    return {
        "AttendenceTime": [
            {"tm_sec": 1, "tm_min": 0, "tm_hour": 0, "tm_mday": 15, "tm_mon": 2,
             "tm_year": 117, "tm_wday": 0, "tm_yday": 0, "tm_isdst": 0},
            {"tm_sec": 59, "tm_min": 59, "tm_hour": 23, "tm_mday": 26, "tm_mon": 3,
             "tm_year": 117, "tm_wday": 8, "tm_yday": 411319584, "tm_isdst": 0},
        ],
        "Event": [
            {
                "s_TableNo": 30018,
                "TimeInMinutes": 0,
                "EventItems": slots(6, {"ItemId": 128578, "ItemCount": 1}),
                "Name": "Come Back Tamer! Event Reward",
            }
        ],
        "MensalEvent": [
            {
                "Id": 1, "s_nUse": 1, "s_nIndex": 1, "s_nType": 1,
                "s_nSuccessType": 1, "s_nSuccessValue": 35, "s_nItemKind": 3,
                "MensalItems": slots(6, {"ItemId": 10301, "ItemCount": 1}),
                "Name": "2016-04-26/00:01:00",
                "EndTime": "2018-09-28/12:59:00",
            }
        ],
        "MonthlyEvent": [
            {
                "s_nTableNo": 60000,
                "s_szMessage": "Event Reward",
                "MonthlyItems": slots(28, {"ItemId": 9766, "ItemCount": 20}),
            }
        ],
        "TimeEvent": [
            {
                "Id": 1,
                "StartDate": "2020-01-14 10:00:00",
                "EndDate": "2020-01-28 23:59:59",
                "Day": 0,
                "StartTime": "02:00:00",
                "EndTime": "05:00:00",
                "ItemId": 129135,
                "ItemCount": 1,
                "unknow": 0,
            }
        ],
        "Event100Days": [
            {
                "Id": 1,
                "Event": "100 Days of Digimon",
                "EventTitle": "Thanksgiving! Digimon Race(100D)!",
                "EventDescript": "Log-in everyday and get DigiEgg!",
                "StartTime": "2019-11-12 14:00:00",
                "EndTime": "2020-02-19 23:59:59",
                "Reset": "00:00:10",
                "EventItems": [
                    {"Name": "1D", "ItemId": 127041, "ItemCount": 1, "Unknow": 0},
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
        sections["TimeEvent"] = [{"Id": 0}]
        data = EventCodec().encode(sections)
        self.assertEqual(EventCodec().decode(data)["sections"]["TimeEvent"], [{"Id": 0}])

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
        "Id": 1001, "Level": 1, "Unknow1": 0, "Exp": 13500, "Hp": 90, "Ds": 30,
        "Ms": 100, "De": 10, "Ev": 5, "Ct": 5, "At": 20, "Ht": 10, "Unknow2": 0,
    }
    return {
        "TamerBaseInfo": [dict(stats)],
        "DigimonBaseInfo": [dict(stats, Id=31001, Hp=46)],
        "CsBaseMapInfo": [
            {"s_nMapID": 1, "s_nShoutSec": 15000, "s_bEnableCheckMacro": 0, "unk": 12}
        ],
        "JumpBooster": [{"dwItemID": 4811, "dwMapIDs": [3, 105, 110]}],
        "Party": [{"distc": 30000.0}],
        "Guild": [
            {
                "s_nLevel": 1, "s_nFame": 0, "s_nItemNo1": 26001, "s_nItemCount1": 1,
                "s_nItemNo2": 0, "s_nItemCount2": 0, "s_nMasterLevel": 0,
                "s_nNeedPerson": 0, "s_nMaxGuildPerson": 50, "s_nIncMember": 10,
                "s_nMaxGuild2Master": 3,
            }
        ],
        "Limit": [
            {
                "s_nMaxTacticsHouse": 200, "s_nMaxWareHouse": 245, "s_nUnionStore": 10,
                "s_nMaxShareStash": 14, "s_nConsume_XG": 500, "s_nCharge_XG": 500,
            }
        ],
        "Store": [
            {
                "s_fPerson_Charge": f32(0.02), "s_fEmployment_Charge": f32(0.0),
                "s_fStoreDist": f32(150.0),
                "StoreItems": [
                    {
                        "s_nItemID": 0, "s_nDigimonID": 0, "s_fScale": f32(0.0),
                        "s_nSlotCount": 3, "s_szFileName": "Base",
                    }
                ],
            }
        ],
        "PaneltyInfo": [{"s_nPaneltyLevel": 1, "s_nDrop": 100, "s_nExp": 100}],
        "EvolutionBaseApply": [
            {"EvolutionType": 1, "EvolutionName": "Digi-Tama", "EvolutionApplyValue": 100}
        ],
        "DigimonEvoMaxSkill": [
            {"nEvoType": 1, "s_SkillExpStartLv": 1, "s_SkillMaxLvs": [1]}
        ],
        "ExpansionData": [
            {"nOpenItemSubType": 20201, "nExpansionRank": 1, "nEvoType": [3, 4, 5, 6]}
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
            {"dwItemID": 5005, "dwMapIDs": [3, 105, 110, 1100]},
            {"dwItemID": 5006, "dwMapIDs": []},
        ]
        decoded = DMBaseCodec().decode(DMBaseCodec().encode(sections))["sections"]
        self.assertEqual(decoded["JumpBooster"], sections["JumpBooster"])

    def test_store_file_name_is_a_128_byte_utf16_field(self) -> None:
        data = DMBaseCodec().encode(dmbase_sections())
        self.assertIn("Base".encode(UTF16) + b"\0" * 8, data)

        # 63 characters + terminator fill the buffer; anything longer is cut off.
        sections = dmbase_sections()
        sections["Store"][0]["StoreItems"][0]["s_szFileName"] = "x" * 63
        decoded = DMBaseCodec().decode(DMBaseCodec().encode(sections))["sections"]
        self.assertEqual(decoded["Store"][0]["StoreItems"][0]["s_szFileName"], "x" * 63)

        sections["Store"][0]["StoreItems"][0]["s_szFileName"] = "x" * 70
        data = DMBaseCodec().encode(sections)
        self.assertIn(("x" * 64).encode(UTF16), data)

    def test_derived_counts_are_not_stored(self) -> None:
        sections = dmbase_sections()
        self.assertNotIn("mapcount", sections["JumpBooster"][0])
        self.assertNotIn("nSubCount", sections["DigimonEvoMaxSkill"][0])
        decoded = DMBaseCodec().decode(DMBaseCodec().encode(sections))["sections"]
        self.assertEqual(list(decoded["JumpBooster"][0]), ["dwItemID", "dwMapIDs"])

    def test_panelty_fields_keep_the_read_order(self) -> None:
        record = DMBaseCodec().decode(DMBaseCodec().encode(dmbase_sections()))["sections"][
            "PaneltyInfo"
        ][0]
        self.assertEqual(list(record), ["s_nPaneltyLevel", "s_nDrop", "s_nExp"])


def cashinfo(name: str = "Item") -> dict:
    """One ``CASHINFO`` record as the reader produces it."""

    return {
        "Name": name,
        "Description": "Desc",
        "Enabled": 1,
        "unique_id": 7,
        "Date1": "2000-01-01 00:00:00",
        "Date2": "2010-12-31 23:59:59",
        "nPurchaseCashType": 1,
        "nStandardSellingPrice": 100,
        "nRealSellingPrice": 90,
        "nSalePersent": 10,
        "nIconID": 5,
        "nMaskType": 1,
        "nDispType": 2,
        "nDispCount": 3,
        "CashItems": [{"ItemId": 1001, "Amount": 1}],
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
                    {"CashShopId": 11 + index, "CashInfo": [cashinfo()]}
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
            "nTableType": 0,
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
                "nPurchaseCashType",
                "nStandardSellingPrice",
                "nRealSellingPrice",
                "nSalePersent",
                "nIconID",
                "nMaskType",
                "nDispType",
                "nDispCount",
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
            {"ItemId": 5, "Amount": 6},
            {"ItemId": 7, "Amount": 8},
        ]
        decoded = CashShopCodec().decode(CashShopCodec().encode(sections))["sections"]
        self.assertEqual(
            decoded["TamerInfo"][0]["ExpansionItems"][0]["CashInfo"][0]["CashItems"],
            [{"ItemId": 5, "Amount": 6}, {"ItemId": 7, "Amount": 8}],
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
        "s_dwID": 1,
        "s_szName": "Attack Up",
        "s_szComment": "Increases attack",
        "s_nBuffIcon": 10,
        "s_nBuffType": 2,
        "s_nBuffLifeType": 1,
        "s_nBuffTimeType": 1,
        "s_nMinLv": 5,
        "s_nBuffClass": 3,
        "_pad0": 0,
        "s_dwSkillCode": 9001,
        "s_dwDigimonSkillCode": 4294967295,
        "s_bDelete": 0,
        "s_szEffectFile": "buff01.tga",
        "_pad1": 0,
        "s_nConditionLv": 1,
    }
    record.update(overrides)
    return record


class BuffCodecTests(unittest.TestCase):
    def test_record_is_476_bytes(self) -> None:
        sections = {"Buff": [buff_record(), buff_record(s_dwID=2)]}
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
        sections = {"Buff": [buff_record(s_nBuffClass=65535)]}
        data = BuffCodec().encode(sections)
        # count, s_dwID, 64 char name, 128 char comment, five u16 fields
        offset = 4 + 2 + 64 * 2 + 128 * 2 + 5 * 2
        self.assertEqual(data[offset : offset + 2], (65535).to_bytes(2, "little"))
        self.assertEqual(BuffCodec().decode(data)["sections"], sections)

    def test_condition_level_follows_the_padding_byte(self) -> None:
        # struct alignment: char[64] ends on an odd offset, USHORT is padded.
        sections = {"Buff": [buff_record(_pad1=0x9A, s_nConditionLv=3)]}
        data = BuffCodec().encode(sections)
        self.assertEqual(data[4 + 473 : 4 + 476], b"\x9a\x03\x00")
        decoded = BuffCodec().decode(data)["sections"]["Buff"][0]
        self.assertEqual(decoded["s_nConditionLv"], 3)
        self.assertEqual(decoded["_pad1"], 0x9A)

    def test_missing_and_trailing_bytes(self) -> None:
        with self.assertRaises(FormatError):
            BuffCodec().encode({})
        with self.assertRaises(FormatError):
            BuffCodec().decode(BuffCodec().encode({"Buff": []}) + b"\0")








def ride_record(**overrides) -> dict:
    record = {
        "s_dwDigimonID": 31001,
        "s_dwChangeRide": 31002,
        "s_fMoveSpeed": f32(1.5),
        "s_szComment": "Fast",
        "s_nRideType": 1,
        "s_fAniRate_Run": f32(1.0),
        "s_nSection": 3,
        "s_nNeedCount": 5,
        "s_nSection_2": 0,
        "s_nNeedCount_2": 0,
    }
    record.update(overrides)
    return record


def achieve_sections() -> dict:
    """A small but valid category tree (root + two categories + two sub-items)."""
    return {
        "AchieveUnknow": [
            {"s_szName": "", "s_listChild": 2},
            {"s_szName": "General", "s_listChild": 2},
            {"s_szName": "Tamer Lv", "s_listChild": 0},
            {"s_szName": "Digimon Lv", "s_listChild": 0},
            {"s_szName": "Quest", "s_listChild": 0},
        ],
        "Achieve": [
            {
                "s_nQuestID": 1500,
                "s_nIcon": 4,
                "s_nPoint": 99,
                "s_bDisplay": 1,
                "s_bDisplay2": 0,
                "s_szName": "Ranker",
                "s_szComment": "Reach the ranking",
                "s_szTitle": "Honor Guardian",
                "s_nGroup": 1,
                "s_nSubGroup": 7,
                "s_nType": 1,
                "s_nBuffCode": 0,
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
        sections["AchieveUnknow"][0]["s_listChild"] = 5
        with self.assertRaises(FormatError):
            AchieveCodec().encode(sections)

        # a record that no parent reaches
        sections = achieve_sections()
        sections["AchieveUnknow"][0]["s_listChild"] = 1
        sections["AchieveUnknow"][1]["s_listChild"] = 0
        with self.assertRaises(FormatError):
            AchieveCodec().encode(sections)

        # an empty tree
        sections = achieve_sections()
        sections["AchieveUnknow"] = []
        with self.assertRaises(FormatError):
            AchieveCodec().encode(sections)

    def test_point_is_sixteen_bits(self) -> None:
        sections = achieve_sections()
        sections["Achieve"][0]["s_nPoint"] = 40000
        data = AchieveCodec().encode(sections)
        # head: quest id, icon, point (u16), display, display2
        self.assertEqual(
            data[TYPE_BYTES + 4 + 8 : TYPE_BYTES + 4 + 10], (40000).to_bytes(2, "little")
        )
        self.assertEqual(
            AchieveCodec().decode(data)["sections"]["Achieve"][0]["s_nPoint"], 40000
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
        self.assertEqual(record["s_szName"], "Lv 20")
        self.assertEqual(record["s_szComment"], "Tamer reached level 20")
        self.assertEqual(record["s_szTitle"], "")

class SimpleCodecTests(unittest.TestCase):
    """The single section formats that are a plain ``count`` + fixed records."""

    def test_uitext_keeps_the_raw_text_length(self) -> None:
        sections = {
            "UIText": [
                {"ID_Maybe": 1234567890123, "Text": "Hello"},
                {"ID_Maybe": 0, "Text": "Hi\0there"},
            ]
        }
        data = UITextCodec().encode(sections)
        # count + (int64 + int32 + UTF-16) per record, NULs included
        self.assertEqual(len(data), 4 + (8 + 4 + 10) + (8 + 4 + 16))
        self.assertEqual(UITextCodec().decode(data)["sections"], sections)

    def test_ride_record_is_a_1060_byte_block(self) -> None:
        sections = {"Ride": [ride_record(), ride_record(s_szComment="")]}
        data = RideCodec().encode(sections)
        self.assertEqual(len(data), 4 + 2 * 1060)
        decoded = RideCodec().decode(data)["sections"]["Ride"]
        self.assertEqual(decoded[0]["s_szComment"], "Fast")
        self.assertEqual(decoded[0]["s_fMoveSpeed"], f32(1.5))
        # 512 UTF-16 characters, NUL padded like the old Array.Resize writer.
        self.assertIn("Fast".encode(UTF16) + b"\0" * (1024 - 8), data)

    def test_ride_comment_is_a_fixed_buffer(self) -> None:
        # 512 UTF-16 characters fill the buffer; a longer text is truncated to it.
        sections = {"Ride": [ride_record(s_szComment="x" * 510)]}
        data = RideCodec().encode(sections)
        self.assertEqual(len(data), 4 + 1060)
        decoded = RideCodec().decode(data)["sections"]["Ride"]
        self.assertEqual(decoded[0]["s_szComment"], "x" * 510)

        sections = {"Ride": [ride_record(s_szComment="x" * 600)]}
        decoded = RideCodec().decode(RideCodec().encode(sections))["sections"]["Ride"]
        self.assertEqual(decoded[0]["s_szComment"], "x" * 512)

    def test_mapnpc_record_order_and_size(self) -> None:
        sections = {
            "MapNpc": [
                {
                    "NpcID": 7,
                    "MapID": 3,
                    "InitPosX": 100,
                    "InitPosY": 200,
                    "s_fRotation": f32(90.0),
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
        info["s_dwPortalID"] = 11
        sections = {"MapPortal": [{"PortalInfos": [info, dict(info, s_dwPortalID=12)]}]}
        data = MapPortalCodec().encode(sections)
        self.assertEqual(len(data), 4 + 4 + 2 * 60)
        self.assertEqual(data[4:8], (2).to_bytes(4, "little"))
        self.assertNotIn("pMapGroup", sections["MapPortal"][0])
        decoded = MapPortalCodec().decode(data)["sections"]
        self.assertEqual(decoded["MapPortal"][0]["PortalInfos"][1]["s_dwPortalID"], 12)

    def test_mapobject_nested_counts_and_factor_order(self) -> None:
        sections = {
            "MapObject": [
                {
                    "MapId": 13,
                    "MapSourceObject": [
                        {
                            "ObjectId": 10511,
                            "OrderObject": [
                                {
                                    "OrderId": 1,
                                    "Object": [
                                        {
                                            "s_nOpenType": 1,
                                            "s_nFactorCnt": 500,
                                            "s_nFactor": 31420,
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


if __name__ == "__main__":
    unittest.main()

