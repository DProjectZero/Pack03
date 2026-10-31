"""``ItemList.bin`` -- item database (the largest format).

Ported from the original converter (``ItemList.cs``) and audited against the client
(``CsFileTable/ItemMng.cpp::CsItemMng::SaveBin`` plus the
structs in ``Item.h`` and ``_ItemDefine.h``).  The file is a chain of 16
sections; the item array itself uses **1596** byte fixed size records
(``CsItem::sINFO``), everything else is a ``count`` + records block except
``ItemAcessorys``, which is a count followed by 184 entries with 16 option slots
each.

Layout details from the audit:

* ``s_szName`` / ``s_szComment`` / ``s_szTypeComment`` are ``TCHAR`` buffers of
  ``ITEM_NAME_LEN`` (64) / ``ITEM_COMMENT_LEN`` (512) / ``ITEM_NAME_LEN``, and
  ``s_cNif`` is a ``char[ITEM_FILE_LEN]`` (64) -- all fixed buffers, read as
  C strings.
* ``s_nSection`` only exists with ``DEBUFF_ITEM`` (this build has it); the single
  bytes the converter called ``unkt``/``unkr``/``uktest``/``ukteste1`` are the
  struct's alignment padding.
* ``ItemExchange`` records are ``[ExchangeItem_No int][CsItemExchange::sINFO]``
  (40 bytes, ``USHORT`` index/price/count fields with padding after
  ``s_dwItemIndex`` and at the end).  The old reader treated the key as the
  *previous* record's trailing field, so the last key was lost: it swallowed the
  ``ItemAcessorys`` count (184) instead.
* ``ItemAcessorys`` starts with its own count -- the old reader assumed a fixed
  184 entry table with no count, which only worked because the count had been
  consumed by the exchange section above.
* ``ItemMaking`` stores its category names as ``int charCount`` +
  ``charCount * 2`` bytes of UTF-16; ``ItemLook`` stores its file name as
  ``int byteSize`` + bytes.
* ``ItemDisplay`` is a ``(nItemS, dwDispID)`` pair table; ``ItemRankEffectList``
  and ``ItemLook`` are variable length (a count is stored per record).

Notes on deviations from the original tool (the reader layout is reproduced
faithfully here):

* ``ServerItemList`` is a *derived view* of ``ItemList`` (names stripped to
  ASCII), so it is not stored in JSON; :func:`server_view` regenerates it.
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, UTF16, Writer, encode_blob
from ..codec import Codec, field, read_records, write_records
from ..fields import field_size, read_fields, write_fields

ACCESSORY_COUNT = 184
ACCESSORY_OPTIONS = 16

ITEM_FIELDS = [
    ("ItemID", "u32"),
    ("Name", ("w", 64)),
    ("Icon", "u32"),
    ("Comment", ("w", 512)),
    ("Nif", ("c", "utf-8", 64)),
    ("Class", "u16"),
    ("TypeComment", ("w", 64)),
    ("CodeTag", "u8"),
    ("unkt", "u8"),
    ("Type_L", "u16"),
    ("Type_S", "u16"),
    ("TypeValue", "u32"),
    ("Section", "u32"),
    ("SellType", "u16"),
    ("UseMode", "u8"),
    ("unkr", "u8"),
    ("UseTimeGroup", "u16"),
    ("Overlap", "u16"),
    ("TamerReqMinLevel", "u16"),
    ("TamerReqMaxLevel", "u16"),
    ("DigimonReqMinLevel", "u16"),
    ("DigimonReqMaxLevel", "u16"),
    ("Possess", "u16"),
    ("EquipSeries", "u16"),
    ("UseCharacter", "u16"),
    ("IsDummy", "u8"),
    ("uktest", "u8"),
    ("Drop", "u16"),
    ("ukteste1", "u16"),
    ("EventItemType", "u32"),
    ("EventItemPrice", "u16"),
    ("DigiCorePrice", "u16"),
    ("ScanPrice", "u32"),
    ("Sale", "u32"),
    ("Model_Nif", ("c", "utf-8", 64)),
    ("Model_Effect", ("c", "utf-8", 64)),
    ("Model_Loop", "u8"),
    ("Model_Shader", "u8"),
    ("SkillCodeType", "u16"),
    ("Skill", "u32"),
    ("ApplyRateMax", "u8"),
    ("ApplyRateMin", "u8"),
    ("ApplyElement", "u8"),
    ("unk", "u8"),
    ("SocketCount", "u16"),
    ("SoundID", "u16"),
    ("Belonging", "u8"),
    ("unk2", ("blob", 3)),
    ("Quest1", "u32"),
    ("Quest2", "u32"),
    ("Quest3", "u32"),
    ("DigiviceSkillSlot", "u8"),
    ("DigiviceChipsetSlot", "u8"),
    ("unk3", ("blob", 2)),
    ("QuestRequire", "u32"),
    ("IsUseTimeType", "u8"),
    ("unk4", ("blob", 3)),
    ("UseTime_Min", "u32"),
    ("UseBattle", "u8"),
    ("unks", "u8"),
    ("DoNotUseType", "u16"),
    ("UseTimeType", "u8"),
    ("unkss", ("blob", 3)),
]

TAP_FIELDS = [("SellClass", "u16"), ("Name", ("w", 32))]
COOLTIME_FIELDS = [("GroupID", "i32"), ("TimeGroup", ("blob", 12))]
DISPLAY_FIELDS = [("ItemS", "i32"), ("DispID", "i32")]
TYPENAME_FIELDS = [("ID", "i32"), ("Name", ("w", 64))]
RANK_FIELDS = [("ID", "i32"), ("Drop_Class", "i16"), ("Drop_Count", "i16")]
ELEMENT_FIELDS = [("ItemID", "i32")]
#: ``CsItemExchange::sINFO`` (40 bytes) -- the client writes ``[ExchangeItem_No
#: int][sINFO]`` per record; the key is a separate field, not part of the struct.
EXCHANGE_FIELDS = [
    ("NpcID", "u32"),
    ("ItemIndex", "u16"),
    ("_pad0", "u16"),
    ("ItemID", "u32"),
    ("Exchange_Code_A", "i32"),
    ("Exchange_Code_B", "i32"),
    ("Exchange_Code_C", "i32"),
    ("Exchange_Code_D", "i32"),
    ("PropertyA_Price", "u16"),
    ("PropertyB_Price", "u16"),
    ("PropertyC_Price", "u16"),
    ("PropertyD_Price", "u16"),
    ("Count", "u16"),
    ("_pad1", "u16"),
]
OPTION_FIELDS = [
    ("OptIdx", "i16"),
    ("unknow", "i16"),
    ("Min", "u32"),
    ("Max", "u32"),
]
ACCESSORY_FIELDS = [
    ("index_Accessory1", "i32"),
    ("index_Accessory", "i32"),
    ("Gain_Option", "i16"),
    ("Changeable_Option_Number", "i16"),
]
ENCHANT_FIELDS = [
    ("ID", "i32"),
    ("Index_Enchant", "i32"),
    ("Enchant_Option", "i16"),
    ("Factor1", "i16"),
]
MAKING_GROUP_FIELDS = [
    ("Index", "i32"),
    ("Type_No", "i32"),
    ("Item_Num", "i32"),
    ("Item_Code", "i32"),
    ("Item_Num1", "i32"),
]
XAI_FIELDS = [("ItemID", "i32"), ("XGauge", "i32"), ("MaxCrystal", "u8")]
RANK_EFFECT_FIELDS = [("ItemCode", "i32"), ("IconNo", "i32"), ("Rank", "i32")]
LOOK_FIELDS = [("Item_Code", "i32"), ("Di_No", "i32"), ("Change_Type", "i32")]


def _strip_to_ascii(text: str) -> str:
    """Port of ``StripUnicodeCharactersFromString`` (used for the server view)."""

    return "".join(
        ch
        for ch in text
        if ("a" <= ch <= "z")
        or ("A" <= ch <= "Z")
        or ("0" <= ch <= "9")
        or ch in "-() "
    )


def _read_accessories(reader: Reader) -> list[dict[str, Any]]:
    """ItemAcessorys: ``count`` (184 in the shipped file) then ``[key][sINFO]``."""

    count = reader.i32()
    if count < 0 or count > (len(reader.data) - reader.pos) // 4:
        raise FormatError(f"{reader.name}: implausible ItemAcessorys count {count}")
    table = []
    for _ in range(count):
        entry = read_fields(reader, ACCESSORY_FIELDS)
        entry["index"] = [read_fields(reader, OPTION_FIELDS) for _ in range(ACCESSORY_OPTIONS)]
        table.append(entry)
    return table


def _write_accessories(writer: Writer, table: list[dict[str, Any]]) -> None:
    writer.i32(len(table))
    for entry in table:
        write_fields(writer, ACCESSORY_FIELDS, entry)
        options = entry.get("index")
        if not isinstance(options, list) or len(options) != ACCESSORY_OPTIONS:
            raise FormatError(
                f"ItemAcessorys entry {entry.get('index_Accessory')}: "
                f"expected {ACCESSORY_OPTIONS} option slots"
            )
        for option in options:
            write_fields(writer, OPTION_FIELDS, option)


def _read_making(reader: Reader) -> list[dict[str, Any]]:
    """Read the nested ItemMaking tree (NPC > Abar > SubCategoty > itemMake)."""

    count = reader.i32()
    if count < 0:
        raise FormatError(f"{reader.name}: negative ItemMaking count ({count})")
    npcs = []
    for _ in range(count):
        npc = {"m_dwNpcIdx": reader.i32(), "m_mapMainCategoty": reader.i32()}
        categories = []
        for _ in range(npc["m_mapMainCategoty"]):
            abar = {"ID": reader.i32(), "ID1": reader.i32()}
            abar["CarteSize"] = reader.i32() * 2
            name_bytes = reader.raw(abar["CarteSize"]) if abar["CarteSize"] > 0 else b""
            abar["Abaname"] = name_bytes.decode(UTF16, "replace").strip().replace("\0", "")
            abar["size_mapSubCategoty"] = reader.i32()
            sub_categories = []
            for _ in range(abar["size_mapSubCategoty"]):
                sub = {"ID": reader.i32(), "ID1": reader.i32()}
                sub["SizeNameCate"] = reader.i32() * 2
                name_bytes = reader.raw(sub["SizeNameCate"]) if sub["SizeNameCate"] > 0 else b""
                sub["Name"] = name_bytes.decode(UTF16, "replace").strip().replace("\0", "")
                sub["fcount"] = reader.i32()
                recipes = []
                for _ in range(sub["fcount"]):
                    recipe = read_fields(
                        reader,
                        [
                            ("m_nUniqueIdx", "i32"),
                            ("m_dwItemIdx", "i32"),
                            ("m_nItemNum", "i32"),
                            ("m_nProbabilityofSuccess", "i32"),
                            ("ink", "i32"),
                            ("unk", "i32"),
                            ("Valor", "i32"),
                            ("m_dwItemCost", "i32"),
                        ],
                    )
                    recipe["index"] = [
                        read_fields(reader, [("m_dwItemIdx", "i32"), ("m_nItemNum", "i32")])
                        for _ in range(recipe["m_dwItemCost"])
                    ]
                    recipes.append(recipe)
                sub["index"] = recipes
                sub_categories.append(sub)
            abar["index"] = sub_categories
            categories.append(abar)
        npc["index"] = categories
        npcs.append(npc)
    return npcs


def _write_making(writer: Writer, npcs: list[dict[str, Any]]) -> None:
    writer.i32(len(npcs))
    for npc in npcs:
        writer.i32(npc["m_dwNpcIdx"])
        categories = npc["index"]
        writer.i32(len(categories))
        for abar in categories:
            writer.i32(abar["ID"])
            writer.i32(abar["ID1"])
            writer.i32(abar["CarteSize"] // 2)
            writer.raw(_pad_name(abar["Abaname"], abar["CarteSize"]))
            sub_categories = abar["index"]
            writer.i32(len(sub_categories))
            for sub in sub_categories:
                writer.i32(sub["ID"])
                writer.i32(sub["ID1"])
                writer.i32(sub["SizeNameCate"] // 2)
                writer.raw(_pad_name(sub["Name"], sub["SizeNameCate"]))
                recipes = sub["index"]
                writer.i32(len(recipes))
                for recipe in recipes:
                    for name in (
                        "m_nUniqueIdx",
                        "m_dwItemIdx",
                        "m_nItemNum",
                        "m_nProbabilityofSuccess",
                        "ink",
                        "unk",
                        "Valor",
                        "m_dwItemCost",
                    ):
                        writer.i32(recipe[name])
                    materials = recipe["index"]
                    for material in materials:
                        writer.i32(material["m_dwItemIdx"])
                        writer.i32(material["m_nItemNum"])


def _pad_name(value: str, size: int) -> bytes:
    encoded = value.encode(UTF16, "replace")
    if len(encoded) < size:
        encoded += b"\0" * (size - len(encoded))
    return encoded[:size]


class ItemListCodec(Codec):
    name = "ItemList"
    filenames = ("itemlist",)
    sections = (
        "ItemList",
        "ItemTap",
        "ItemCoolTime",
        "ItemDisplay",
        "ItemTypeName",
        "ItemRank",
        "ElementItem",
        "ElementItem1",
        "ItemExchange",
        "ItemAcessorys",
        "AcessorysEnchant",
        "ItemMaking",
        "ItemMakingGroupList",
        "ItemXai",
        "ItemRankEffectList",
        "ItemLook",
    )

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        sections: dict[str, Any] = {}
        sections["ItemList"] = read_records(reader, lambda r: read_fields(r, ITEM_FIELDS))
        sections["ItemTap"] = read_records(reader, lambda r: read_fields(r, TAP_FIELDS))
        sections["ItemCoolTime"] = read_records(reader, lambda r: read_fields(r, COOLTIME_FIELDS))
        sections["ItemDisplay"] = read_records(reader, lambda r: read_fields(r, DISPLAY_FIELDS))
        sections["ItemTypeName"] = read_records(reader, lambda r: read_fields(r, TYPENAME_FIELDS))
        sections["ItemRank"] = read_records(reader, lambda r: read_fields(r, RANK_FIELDS))
        sections["ElementItem"] = read_records(reader, lambda r: read_fields(r, ELEMENT_FIELDS))
        sections["ElementItem1"] = read_records(reader, lambda r: read_fields(r, ELEMENT_FIELDS))
        sections["ItemExchange"] = self._read_exchanges(reader)
        sections["ItemAcessorys"] = _read_accessories(reader)
        sections["AcessorysEnchant"] = read_records(
            reader, lambda r: read_fields(r, ENCHANT_FIELDS)
        )
        sections["ItemMaking"] = _read_making(reader)
        sections["ItemMakingGroupList"] = read_records(
            reader, lambda r: read_fields(r, MAKING_GROUP_FIELDS)
        )
        sections["ItemXai"] = read_records(reader, lambda r: read_fields(r, XAI_FIELDS))
        sections["ItemRankEffectList"] = read_records(reader, self._read_rank_effect)
        sections["ItemLook"] = read_records(reader, self._read_look)
        if reader.pos != len(data):
            raise FormatError(
                f"{source}: {len(data) - reader.pos} trailing byte(s) after ItemLook "
                f"(offset {reader.pos} of {len(data)})"
            )
        return {"format": self.name, "sections": sections}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        write_records(writer, self._items(sections, "ItemList"),
                      lambda w, r: write_fields(w, ITEM_FIELDS, r))
        write_records(writer, self._items(sections, "ItemTap"),
                      lambda w, r: write_fields(w, TAP_FIELDS, r))
        write_records(writer, self._items(sections, "ItemCoolTime"),
                      lambda w, r: write_fields(w, COOLTIME_FIELDS, r))
        write_records(writer, self._items(sections, "ItemDisplay"),
                      lambda w, r: write_fields(w, DISPLAY_FIELDS, r))
        write_records(writer, self._items(sections, "ItemTypeName"),
                      lambda w, r: write_fields(w, TYPENAME_FIELDS, r))
        write_records(writer, self._items(sections, "ItemRank"),
                      lambda w, r: write_fields(w, RANK_FIELDS, r))
        write_records(writer, self._items(sections, "ElementItem"),
                      lambda w, r: write_fields(w, ELEMENT_FIELDS, r))
        write_records(writer, self._items(sections, "ElementItem1"),
                      lambda w, r: write_fields(w, ELEMENT_FIELDS, r))
        self._write_exchanges(writer, self._items(sections, "ItemExchange"))
        _write_accessories(writer, self._items(sections, "ItemAcessorys"))
        write_records(writer, self._items(sections, "AcessorysEnchant"),
                      lambda w, r: write_fields(w, ENCHANT_FIELDS, r))
        _write_making(writer, self._items(sections, "ItemMaking"))
        write_records(writer, self._items(sections, "ItemMakingGroupList"),
                      lambda w, r: write_fields(w, MAKING_GROUP_FIELDS, r))
        write_records(writer, self._items(sections, "ItemXai"),
                      lambda w, r: write_fields(w, XAI_FIELDS, r))
        write_records(writer, self._items(sections, "ItemRankEffectList"),
                      self._write_rank_effect)
        write_records(writer, self._items(sections, "ItemLook"), self._write_look)
        return writer.getvalue()

    # -- sections with variable length records --------------------------
    @staticmethod
    def _read_exchanges(reader: Reader) -> list[dict[str, Any]]:
        """ItemExchange: count, then ``[ExchangeItem_No][sINFO]`` per record."""

        count = reader.i32()
        if count < 0 or count > len(reader.data):
            raise FormatError(f"{reader.name}: implausible ItemExchange count {count}")
        records = []
        for _ in range(count):
            record = {"ExchangeItem_No": reader.i32()}
            record.update(read_fields(reader, EXCHANGE_FIELDS))
            records.append(record)
        return records

    @staticmethod
    def _write_exchanges(writer: Writer, records: list[dict[str, Any]]) -> None:
        writer.i32(len(records))
        for record in records:
            writer.i32(field(record, "ExchangeItem_No", "ItemExchange"))
            write_fields(writer, EXCHANGE_FIELDS, record)

    @staticmethod
    def _read_rank_effect(reader: Reader) -> dict[str, Any]:
        record = {"ItemCode": reader.i32(), "Interval": reader.i32()}
        record["index"] = [
            read_fields(reader, RANK_EFFECT_FIELDS) for _ in range(record["Interval"])
        ]
        return record

    @staticmethod
    def _write_rank_effect(writer: Writer, record: dict[str, Any]) -> None:
        intervals = record["index"]
        writer.i32(record["ItemCode"])
        writer.i32(len(intervals))
        for interval in intervals:
            write_fields(writer, RANK_EFFECT_FIELDS, interval)

    @staticmethod
    def _read_look(reader: Reader) -> dict[str, Any]:
        record = read_fields(reader, LOOK_FIELDS)
        record["NameSize"] = reader.i32()
        name = reader.cstring("ascii", record["NameSize"]) if record["NameSize"] > 0 else ""
        record["File_Name"] = name.strip()
        return record

    @staticmethod
    def _write_look(writer: Writer, record: dict[str, Any]) -> None:
        write_fields(writer, LOOK_FIELDS, record)
        size = record["NameSize"]
        writer.i32(size)
        writer.cstring(record["File_Name"].strip(), "ascii", size)


def server_view(sections: dict[str, Any]) -> list[dict[str, Any]]:
    """Rebuild the derived ``ServerItemList`` view (names stripped to ASCII)."""

    items = []
    for item in sections["ItemList"]:
        copy = dict(item)
        copy["Name"] = _strip_to_ascii(item["Name"])
        items.append(copy)
    return items



