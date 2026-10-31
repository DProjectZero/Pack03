"""``BattleTable.bin`` -- battle modes, their rewards and allowed digimon.

Ported from the client (``dmz-client/LibProj/CsFileTable/BattleTableMng.cpp``,
``_LoadBin`` lines 290-380) with the types from ``BattleTableMng.h``
(``sBattleMode`` and the reward item)::

    BattleMode:   int32 count, then per mode:
                      int32 nModeType
                      int32 nModeCount
                      per entry:
                          bool          m_bActive
                          int32         m_VsType
                          DWORD         m_dwMapID
                          std::string   m_strMapImgFile   int32 size + ASCII
                          unsigned int  m_nLimitDLv, m_nNeedTicket,
                                        m_nLimitJoinCount
                          int32         m_WinRankPoint, m_LoseRankPoint,
                                        m_WinRewardTalbeIdx, m_LoseRewardTalbeIdx

    BattleReward: int32 count, then per reward table:
                      int32 nIdx, int32 nItemCount
                      per item: DWORD m_dwItemCode, unsigned int m_Count

    BattleDigimon: int32 count, then per table:
                      int32 nIdx, int32 nDigimonCount
                      per digimon: DWORD dwDigimonIdx

Everything is read field by field, so there is no struct padding in the file.
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, field, read_records, write_records


def _count(reader: Reader, what: str) -> int:
    count = reader.i32()
    if count < 0 or count > len(reader.data):
        raise FormatError(f"{reader.name}: implausible {what} count {count}")
    return count


def _read_text(reader: Reader) -> str:
    size = reader.i32()
    if size < 0 or size > (len(reader.data) - reader.pos):
        raise FormatError(
            f"{reader.name}: implausible string size {size} at offset {reader.pos - 4}"
        )
    return reader.raw(size).decode("ascii", "replace")


def _write_text(writer: Writer, value: Any, where: str) -> None:
    if not isinstance(value, str):
        raise FormatError(f"{where} must be a string")
    data = value.encode("ascii", "replace")
    writer.i32(len(data))
    writer.raw(data)


def _read_mode(reader: Reader) -> dict[str, Any]:
    record: dict[str, Any] = {
        "m_bActive": reader.u8(),
        "m_VsType": reader.i32(),
        "m_dwMapID": reader.u32(),
    }
    record["m_strMapImgFile"] = _read_text(reader)
    record["m_nLimitDLv"] = reader.u32()
    record["m_nNeedTicket"] = reader.u32()
    record["m_nLimitJoinCount"] = reader.u32()
    record["m_WinRankPoint"] = reader.i32()
    record["m_LoseRankPoint"] = reader.i32()
    record["m_WinRewardTalbeIdx"] = reader.i32()
    record["m_LoseRewardTalbeIdx"] = reader.i32()
    return record


def _write_mode(writer: Writer, record: dict[str, Any]) -> None:
    where = "BattleMode"
    writer.u8(field(record, "m_bActive", where))
    writer.i32(field(record, "m_VsType", where))
    writer.u32(field(record, "m_dwMapID", where))
    _write_text(
        writer, field(record, "m_strMapImgFile", where), f"{where}.m_strMapImgFile"
    )
    writer.u32(field(record, "m_nLimitDLv", where))
    writer.u32(field(record, "m_nNeedTicket", where))
    writer.u32(field(record, "m_nLimitJoinCount", where))
    writer.i32(field(record, "m_WinRankPoint", where))
    writer.i32(field(record, "m_LoseRankPoint", where))
    writer.i32(field(record, "m_WinRewardTalbeIdx", where))
    writer.i32(field(record, "m_LoseRewardTalbeIdx", where))


def _read_mode_type(reader: Reader) -> dict[str, Any]:
    record = {"nModeType": reader.i32()}
    count = _count(reader, "battle mode")
    record["Modes"] = [_read_mode(reader) for _ in range(count)]
    return record


def _write_mode_type(writer: Writer, record: dict[str, Any]) -> None:
    writer.i32(field(record, "nModeType", "BattleMode"))
    modes = record.get("Modes")
    if not isinstance(modes, list):
        raise FormatError("BattleMode: 'Modes' must be a list")
    writer.i32(len(modes))
    for mode in modes:
        _write_mode(writer, mode)


def _read_reward_item(reader: Reader) -> dict[str, Any]:
    return {"m_dwItemCode": reader.u32(), "m_Count": reader.u32()}


def _write_reward_item(writer: Writer, record: dict[str, Any]) -> None:
    writer.u32(field(record, "m_dwItemCode", "BattleReward"))
    writer.u32(field(record, "m_Count", "BattleReward"))


def _read_reward(reader: Reader) -> dict[str, Any]:
    record = {"nIdx": reader.i32()}
    count = _count(reader, "battle reward item")
    record["nItemCount"] = count
    record["Items"] = [_read_reward_item(reader) for _ in range(count)]
    return record


def _write_reward(writer: Writer, record: dict[str, Any]) -> None:
    where = "BattleReward"
    writer.i32(field(record, "nIdx", where))
    items = record.get("Items")
    if not isinstance(items, list):
        raise FormatError(f"{where}: 'Items' must be a list")
    writer.i32(len(items))
    for item in items:
        _write_reward_item(writer, item)


def _read_digimon_table(reader: Reader) -> dict[str, Any]:
    record = {"nIdx": reader.i32()}
    count = _count(reader, "battle digimon")
    record["nDigimonCount"] = count
    record["Digimon"] = [{"dwDigimonIdx": reader.u32()} for _ in range(count)]
    return record


def _write_digimon_table(writer: Writer, record: dict[str, Any]) -> None:
    where = "BattleDigimon"
    writer.i32(field(record, "nIdx", where))
    digimon = record.get("Digimon")
    if not isinstance(digimon, list):
        raise FormatError(f"{where}: 'Digimon' must be a list")
    writer.i32(len(digimon))
    for entry in digimon:
        writer.u32(field(entry, "dwDigimonIdx", where))


class BattleTableCodec(Codec):
    name = "BattleTable"
    filenames = ("battletable",)
    sections = ("BattleMode", "BattleReward", "BattleDigimon")
    record_tags = {
        "BattleMode": "Mode",
        "BattleReward": "Reward",
        "BattleDigimon": "Digimon",
    }

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        sections = {"BattleMode": read_records(reader, _read_mode_type)}
        sections["BattleReward"] = read_records(reader, _read_reward)
        sections["BattleDigimon"] = read_records(reader, _read_digimon_table)
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": sections}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        write_records(writer, self._items(sections, "BattleMode"), _write_mode_type)
        write_records(writer, self._items(sections, "BattleReward"), _write_reward)
        write_records(
            writer, self._items(sections, "BattleDigimon"), _write_digimon_table
        )
        return writer.getvalue()
