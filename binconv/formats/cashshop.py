"""``CashShop.bin`` -- the cash shop catalogue.

Ported from the original converter (``CashShop.cs``) and audited against the client
(``CsFileTable/CashShopMng.cpp::CsCashShopMng::SaveBin`` and
``CashShop.h``).  The file starts with a shop count and repeats one *shop* per
entry, then closes with the web banner table::

    count                       number of shops (2 in the shipped file)
    per shop:  int tableType, int categoryCount, category[categoryCount]
                 category:  int key, wstring name, int subCount,
                            subcategory[subCount]
                              subcategory: int key, wstring name, int groupCount,
                                           group[groupCount]
    WebData:   count, per entry int tableType + count + banner[count]

Every ``CASHINFO`` product (the innermost record) is, exactly as the client
writes it::

    wsName, wsComment            length prefixed UTF-16
    bActive                      bool (1 byte)
    dwProductID                  DWORD
    szStartTime[64], szEndTime[64]   fixed ASCII buffers, NUL padded
    nPurchaseCashType, nStandardSellingPrice, nRealSellingPrice, nSalePersent,
    nIconID, nMaskType, nDispType, nDispCount      eight int32
    count, package items (s_nItemID: DWORD, s_nItemCnt: int)

The client splits a shop into five categories (``Main``, ``Tamer``, ``Digimon``,
``Avatar``, ``Packages``), which is why the exporter produced one document per
category, and why ``Main.json``/``TamerInfo.json``/... hold one record per shop.
``CashShopInformationCount`` is the subcategory level (``key`` + ``wsCategoryName``
+ product groups) and ``CASHINFO`` sits one level below it.

Details worth knowing:

* The old XML export wrote a second set of names (``CashName``, ``bActive``,
  ``dwProductID``, ``szStartTime``, ``szEndTime``, ``packageItems``, ``Desc``)
  that the reader never fills, so those elements are always empty.  JSON keeps
  the fields that really exist in the file.
* ``CASHINFO.cashshop_id`` is *derived* (``s.cashshop_id = CashInfo.CashShopId``),
  it is not stored in the file and therefore not in JSON either.
* ``CashShopMainInformation.UnknowItemsTitle`` is exported to XML but neither
  read nor written -- JSON does not have it.
* ``CashShopPackageInfo.PackageName`` is declared but never read or written.
* The C# writer hardcodes the shop count (``writer.Write(2)`` when ``index == 0``);
  JSON derives it from the length of the document lists.
* ``CashWebData.m_mapWebData`` is the number of ``CashWebInfo`` entries in the
  file, so it is derived on write instead of being stored twice.
* ``CashWebDataInfo.Size``/``Size2`` are the explicit byte lengths of the two
  ASCII (banner file name / link) fields -- ``strlen`` of the text, no
  terminator is stored.  Trailing NULs are not kept in JSON; the sizes are, so a
  recompile reproduces the original byte count.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, field, read_records, write_records
from ..fields import read_text, write_text

#: ``szStartTime``/``szEndTime`` -- fixed ``char[64]`` buffers, written with
#: ``CmBinSave::Save_String( fp, szStartTime, sizeof(szStartTime) )``.
DATE_BYTES = 64


#: ``(unknow field, caption field, group list field)`` per category block.
#: A ``None`` unknow means the caption continues the previous block (the tamer,
#: digimon and avatar shops start straight after their document header).
TAMER_CATEGORIES: Sequence[tuple[str | None, str, str]] = (
    (None, "ExpasionName", "ExpansionItems"),
    ("unknow4", "ExpName", "ExpItems"),
    ("unknow5", "MovimentName", "MovimentItems"),
    ("unknow6", "ChatName", "ChatItems"),
    ("unknow7", "EtcName", "EtcItems"),
)

DIGIMON_CATEGORIES: Sequence[tuple[str | None, str, str]] = (
    (None, "DigiEggName", "DigiEgg"),
    ("unknow5", "EvolutionName", "EvolutionItems"),
    ("unknow6", "HatchName", "HatchItems"),
    ("unknow7", "ReinforcedName", "ReinforcedItems"),
    ("unknow8", "RidingName", "RidingItems"),
    ("unknow9", "EtcName", "EtcItems"),
)

AVATAR_CATEGORIES: Sequence[tuple[str | None, str, str]] = (
    (None, "ReinforcedName", "ReinforcedItems"),
    ("unknow5", "HeadName", "HeadItems"),
    ("unknow6", "TopName", "TopItems"),
    ("unknow7", "BottomName", "BottomItems"),
    ("unknow8", "GlovesName", "GlovesItems"),
    ("unknow9", "ShoesName", "ShoesItems"),
    ("unknow10", "FashionName", "FashionItems"),
    ("unknow11", "CostumeName", "CostumeItems"),
)

#: ``CASHINFO`` price/display block, in file order.
CASHINFO_FIELDS = (
    "PurchaseCashType",
    "StandardSellingPrice",
    "RealSellingPrice",
    "SalePersent",
    "IconID",
    "MaskType",
    "DispType",
    "DispCount",
)


# -- helpers ------------------------------------------------------------
def _text(record: dict[str, Any], name: str, where: str) -> str:
    value = field(record, name, where)
    if not isinstance(value, str):
        raise FormatError(f"{where}: field {name!r} must be a string")
    return value


def _list(record: dict[str, Any], name: str, where: str) -> list[Any]:
    try:
        value = record[name]
    except KeyError:
        raise FormatError(f"{where}: missing required list {name!r}") from None
    if not isinstance(value, list):
        raise FormatError(f"{where}: {name!r} must be a list")
    return value


def _read_count(reader: Reader, what: str) -> int:
    count = reader.i32()
    if count < 0 or count > (len(reader.data) - reader.pos):
        raise FormatError(
            f"{reader.name}: implausible {what} count {count} at offset {reader.pos - 4}"
        )
    return count


def _read_ascii(reader: Reader) -> tuple[int, str]:
    """``int32 size`` + *size* ASCII bytes, trailing NULs removed."""

    size = reader.i32()
    if size < 0 or size > (len(reader.data) - reader.pos):
        raise FormatError(
            f"{reader.name}: implausible string size {size} at offset {reader.pos - 4}"
        )
    return size, reader.raw(size).decode("ascii", "replace").rstrip("\0")


def _write_ascii(writer: Writer, size: Any, value: str, where: str) -> None:
    data = value.encode("ascii", "replace")
    if not isinstance(size, int) or size < 0:
        raise FormatError(f"{where}: 'Size' must be a non negative integer")
    # Unused room in the original buffer is NUL filled; an edited, longer text
    # grows the field instead of being truncated.
    size = max(size, len(data))
    writer.i32(size)
    writer.raw(data.ljust(size, b"\0"))


# -- Item / CashShopInformationCount / CASHINFO -------------------------
def _read_item(reader: Reader) -> dict[str, Any]:
    return {"ItemID": reader.i32(), "Amount": reader.i32()}


def _write_item(writer: Writer, record: dict[str, Any]) -> None:
    writer.i32(field(record, "ItemID", "CashItems"))
    writer.i32(field(record, "Amount", "CashItems"))


def _read_cashinfo(reader: Reader) -> dict[str, Any]:
    record: dict[str, Any] = {
        "Name": read_text(reader),
        "Description": read_text(reader),
        "Enabled": reader.u8(),
        "unique_id": reader.i32(),
        "Date1": reader.cstring("ascii", DATE_BYTES),
        "Date2": reader.cstring("ascii", DATE_BYTES),
    }
    for name in CASHINFO_FIELDS:
        record[name] = reader.i32()
    record["CashItems"] = read_records(reader, _read_item)
    return record


def _write_cashinfo(writer: Writer, record: dict[str, Any]) -> None:
    where = "CASHINFO"
    write_text(writer, _text(record, "Name", where))
    write_text(writer, _text(record, "Description", where))
    writer.u8(field(record, "Enabled", where))
    writer.i32(field(record, "unique_id", where))
    writer.cstring(_text(record, "Date1", where), "ascii", DATE_BYTES)
    writer.cstring(_text(record, "Date2", where), "ascii", DATE_BYTES)
    for name in CASHINFO_FIELDS:
        writer.i32(field(record, name, where))
    write_records(writer, _list(record, "CashItems", where), _write_item)


def _read_group(reader: Reader) -> dict[str, Any]:
    return {
        "CashShopID": reader.i32(),
        "CashInfo": read_records(reader, _read_cashinfo),
    }


def _write_group(writer: Writer, record: dict[str, Any]) -> None:
    where = "CashShopInformationCount"
    writer.i32(field(record, "CashShopID", where))
    write_records(writer, _list(record, "CashInfo", where), _write_cashinfo)


# -- category blocks ----------------------------------------------------
def _read_categories(
    reader: Reader, specs: Iterable[tuple[str | None, str, str]]
) -> dict[str, Any]:
    """Read the ``unknow`` / caption / group list triples of one shop document."""

    record: dict[str, Any] = {}
    for unknow, caption, items in specs:
        if unknow is not None:
            record[unknow] = reader.i32()
        record[caption] = read_text(reader)
        record[items] = read_records(reader, _read_group)
    return record


def _write_categories(
    writer: Writer,
    specs: Iterable[tuple[str | None, str, str]],
    record: dict[str, Any],
    where: str,
) -> None:
    """Write the ``unknow`` / caption / group list triples of one shop document."""

    for unknow, caption, items in specs:
        if unknow is not None:
            writer.i32(field(record, unknow, where))
        write_text(writer, _text(record, caption, where))
        write_records(writer, _list(record, items, where), _write_group)


def _read_header(reader: Reader) -> dict[str, Any]:
    """``unknow, CategoryName, unknow1, unknow2, AllName, unknow3, unknow4``."""

    record = {"unknow": reader.i32(), "CategoryName": read_text(reader)}
    record["unknow1"] = reader.i32()
    record["unknow2"] = reader.i32()
    record["AllName"] = read_text(reader)
    record["unknow3"] = reader.i32()
    record["unknow4"] = reader.i32()
    return record


def _write_header(writer: Writer, record: dict[str, Any], where: str) -> None:
    writer.i32(field(record, "unknow", where))
    write_text(writer, _text(record, "CategoryName", where))
    writer.i32(field(record, "unknow1", where))
    writer.i32(field(record, "unknow2", where))
    write_text(writer, _text(record, "AllName", where))
    writer.i32(field(record, "unknow3", where))
    writer.i32(field(record, "unknow4", where))


# -- documents ----------------------------------------------------------
def _read_main(reader: Reader) -> dict[str, Any]:
    record = {
        "unknow": reader.i32(),
        "unknow1": reader.i32(),
        "unknow2": reader.i32(),
        "MainTitle": read_text(reader),
        "unknow3": reader.i32(),
        "unknow4": reader.i32(),
        "MainNewTitle": read_text(reader),
    }
    record["MainNewItems"] = _read_product_ids(reader)
    record["unknow5"] = reader.i32()
    record["MainHotTitle"] = read_text(reader)
    record["MainHotItems"] = _read_product_ids(reader)
    record["unknow6"] = reader.i32()
    record["MainEventTitle"] = read_text(reader)
    record["MainEventItems"] = _read_product_ids(reader)
    record["unknow7"] = reader.i64()
    record["MainUnknowItems"] = _read_product_ids(reader)
    record["unknow8"] = reader.i32()
    return record


def _read_product_ids(reader: Reader) -> list[dict[str, Any]]:
    """``int32 count`` + ``int64 ProductID`` values of one main page list."""

    count = _read_count(reader, "ProductID")
    if count > (len(reader.data) - reader.pos) // 8:
        raise FormatError(
            f"{reader.name}: implausible ProductID count {count} "
            f"at offset {reader.pos - 4}"
        )
    return [{"ProductID": reader.i64()} for _ in range(count)]


def _write_product_ids(writer: Writer, values: Any, where: str) -> None:
    if not isinstance(values, list):
        raise FormatError(f"{where}: must be a list of ProductID records")
    writer.i32(len(values))
    for value in values:
        writer.i64(field(value, "ProductID", f"{where} item"))


def _write_main(writer: Writer, record: dict[str, Any]) -> None:
    where = "Main"
    writer.i32(field(record, "unknow", where))
    writer.i32(field(record, "unknow1", where))
    writer.i32(field(record, "unknow2", where))
    write_text(writer, _text(record, "MainTitle", where))
    writer.i32(field(record, "unknow3", where))
    writer.i32(field(record, "unknow4", where))
    write_text(writer, _text(record, "MainNewTitle", where))
    _write_product_ids(writer, _list(record, "MainNewItems", where), "Main.MainNewItems")
    writer.i32(field(record, "unknow5", where))
    write_text(writer, _text(record, "MainHotTitle", where))
    _write_product_ids(writer, _list(record, "MainHotItems", where), "Main.MainHotItems")
    writer.i32(field(record, "unknow6", where))
    write_text(writer, _text(record, "MainEventTitle", where))
    _write_product_ids(
        writer, _list(record, "MainEventItems", where), "Main.MainEventItems"
    )
    writer.i64(field(record, "unknow7", where))
    _write_product_ids(
        writer, _list(record, "MainUnknowItems", where), "Main.MainUnknowItems"
    )
    writer.i32(field(record, "unknow8", where))


def _read_tamer(reader: Reader) -> dict[str, Any]:
    # The tamer shop starts with its own caption instead of an unknow int.
    record = {"CategoryName": read_text(reader)}
    record["unknow"] = reader.i32()
    record["unknow1"] = reader.i32()
    record["AllName"] = read_text(reader)
    record["unknow2"] = reader.i32()
    record["unknow3"] = reader.i32()
    record.update(_read_categories(reader, TAMER_CATEGORIES))
    return record


def _write_tamer(writer: Writer, record: dict[str, Any]) -> None:
    where = "TamerInfo"
    write_text(writer, _text(record, "CategoryName", where))
    writer.i32(field(record, "unknow", where))
    writer.i32(field(record, "unknow1", where))
    write_text(writer, _text(record, "AllName", where))
    writer.i32(field(record, "unknow2", where))
    writer.i32(field(record, "unknow3", where))
    _write_categories(writer, TAMER_CATEGORIES, record, where)


def _read_digimon(reader: Reader) -> dict[str, Any]:
    record = _read_header(reader)
    record.update(_read_categories(reader, DIGIMON_CATEGORIES))
    return record


def _write_digimon(writer: Writer, record: dict[str, Any]) -> None:
    _write_header(writer, record, "DigimonInfo")
    _write_categories(writer, DIGIMON_CATEGORIES, record, "DigimonInfo")


def _read_avatar(reader: Reader) -> dict[str, Any]:
    record = _read_header(reader)
    record.update(_read_categories(reader, AVATAR_CATEGORIES))
    return record


def _write_avatar(writer: Writer, record: dict[str, Any]) -> None:
    _write_header(writer, record, "AvatarInfo")
    _write_categories(writer, AVATAR_CATEGORIES, record, "AvatarInfo")


def _read_package(reader: Reader) -> dict[str, Any]:
    # Unlike the digimon/avatar shops the package block has no ``unknow3`` /
    # ``unknow4`` pair after ``AllName``.
    record = {"unknow": reader.i32(), "CategoryName": read_text(reader)}
    record["unknow1"] = reader.i32()
    record["unknow2"] = reader.i32()
    record["AllName"] = read_text(reader)
    record["PackageItems"] = read_records(reader, _read_group)
    return record


def _write_package(writer: Writer, record: dict[str, Any]) -> None:
    where = "PackageInfo"
    writer.i32(field(record, "unknow", where))
    write_text(writer, _text(record, "CategoryName", where))
    writer.i32(field(record, "unknow1", where))
    writer.i32(field(record, "unknow2", where))
    write_text(writer, _text(record, "AllName", where))
    write_records(writer, _list(record, "PackageItems", where), _write_group)


# -- web banners --------------------------------------------------------
def _read_web_info(reader: Reader) -> dict[str, Any]:
    size, image = _read_ascii(reader)
    size2, url = _read_ascii(reader)
    return {
        "Size": size,
        "sWebImageFile": image,
        "Size2": size2,
        "sWebLinkUrl": url,
    }


def _write_web_info(writer: Writer, record: dict[str, Any]) -> None:
    where = "CashWebDataInfo"
    _write_ascii(
        writer,
        field(record, "Size", where),
        _text(record, "sWebImageFile", where),
        f"{where}.sWebImageFile",
    )
    _write_ascii(
        writer,
        field(record, "Size2", where),
        _text(record, "sWebLinkUrl", where),
        f"{where}.sWebLinkUrl",
    )


def _read_web(reader: Reader) -> dict[str, Any]:
    record = {"TableType": reader.i32()}
    record["CashWebInfo"] = read_records(reader, _read_web_info)
    return record


def _write_web(writer: Writer, record: dict[str, Any]) -> None:
    where = "WebData"
    writer.i32(field(record, "TableType", where))
    write_records(writer, _list(record, "CashWebInfo", where), _write_web_info)


class CashShopCodec(Codec):
    """``CashShop.bin`` <-> ``json/CashShop/{Main,TamerInfo,...}.json``."""

    name = "CashShop"
    filenames = ("cashshop",)
    sections = (
        "Main",
        "TamerInfo",
        "DigimonInfo",
        "AvatarInfo",
        "PackageInfo",
        "WebData",
    )
    #: Here a record *is* a whole XML document (``Main/CashShopMainInformation.xml``
    #: for ``Main[0]``), so the tags are document roots; ``WebData`` is the usual
    #: repeated element inside a single document.
    record_tags = {
        "Main": "CashShopMainInformation",
        "TamerInfo": "CashShopTamerInfo",
        "DigimonInfo": "CashShopDigimonInfo",
        "AvatarInfo": "CashShopAvatarInfo",
        "PackageInfo": "CashShopPackageInfo",
        "WebData": "CashWebData",
    }

    #: One record per shop; the file's leading count is their number.
    shop_sections = ("Main", "TamerInfo", "DigimonInfo", "AvatarInfo", "PackageInfo")

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        count = reader.i32()
        if count < 0 or count > (len(data) - reader.pos):
            raise FormatError(f"{source}: implausible shop count {count} at offset 0")
        sections: dict[str, list[Any]] = {name: [] for name in self.shop_sections}
        for _ in range(count):
            sections["Main"].append(_read_main(reader))
            sections["TamerInfo"].append(_read_tamer(reader))
            sections["DigimonInfo"].append(_read_digimon(reader))
            sections["AvatarInfo"].append(_read_avatar(reader))
            sections["PackageInfo"].append(_read_package(reader))
        sections["WebData"] = read_records(reader, _read_web)
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": sections}

    def encode(self, sections: dict[str, Any]) -> bytes:
        shops = {name: self._items(sections, name) for name in self.shop_sections}
        count = len(shops["Main"])
        for name, records in shops.items():
            if len(records) != count:
                raise FormatError(
                    f"{name}: {len(records)} record(s) but Main has {count}; every "
                    "shop needs one record in each of "
                    f"{', '.join(self.shop_sections)}"
                )

        writer = Writer()
        writer.i32(count)
        for index in range(count):
            _write_main(writer, shops["Main"][index])
            _write_tamer(writer, shops["TamerInfo"][index])
            _write_digimon(writer, shops["DigimonInfo"][index])
            _write_avatar(writer, shops["AvatarInfo"][index])
            _write_package(writer, shops["PackageInfo"][index])
        write_records(writer, self._items(sections, "WebData"), _write_web)
        return writer.getvalue()
