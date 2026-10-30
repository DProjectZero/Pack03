"""Unit tests for the converter primitives and a couple of codecs.

Run with:
    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from binconv.binary import FormatError, Reader, UTF16, Writer  # noqa: E402
from binconv.cli import main, read_sections, section_path, write_sections  # noqa: E402
from binconv.codec import compare_roundtrip  # noqa: E402
from binconv.formats.itemlist import ItemListCodec  # noqa: E402
from binconv.formats.quest import QuestCodec  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()

