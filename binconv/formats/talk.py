"""``Talk.bin`` -- every dialogue table: digimon lines, event talk, system messages,
tips and loading tips.

Layout from the client, ``TalkMng.cpp::_LoadBin`` (lines 72-95), which calls the
per-table loaders in this order::

    _LoadBin_Digimon(fp);      // TalkMng_Digimon.cpp:162
    _LoadBin_Event(fp);        // TalkMng_Event.cpp:125
    _LoadBin_Message(fp);      // TalkMng_Message.cpp:316
    _LoadBin_Tip(fp);          // TalkMng_Tip.cpp:109
    _LoadBin_LoadingTip(fp);   // TalkMng_Tip.cpp:284
    #ifdef SIMPLE_TOOLTIP
    _LoadBin_ToolTip(fp);      // TalkMng_Message.cpp:266
    #endif

so the file is five counted sections (plus an optional sixth) —::

    1) CsTalk_Digimon::sINFO        412 bytes including the key
        DWORD  key
        DWORD  s_dwParam
        USHORT s_nType                       eTP: quest / npc / digimon / skill
        <2 bytes of struct padding>
        TCHAR  s_szText[100]
        TCHAR  s_szList[100]

    2) CsTalk_Event::sINFO          408 bytes
        DWORD  key
        DWORD  s_dwTalkNum
        TCHAR  s_szText[200]

    3) CsTalk_Message::sINFO        560 bytes (the key *is* s_dwID)
        DWORD  s_dwID
        int    s_MsgType                     eMESSAGE_TYPE 1..5
        int    s_Type                        eTYPE 1..4
        TCHAR  s_TitleName[16]
        TCHAR  s_Message[256]
        DWORD  s_dwLinkID

    4) CsTalk_Tip::sINFO            404 bytes
        DWORD  key
        TCHAR  s_szTip[200]

    5) CsLoading_Tip::sINFO         408 bytes
        DWORD  key
        TCHAR  s_szLoadingTip[200]
        int    s_nLevel

    6) CsTalk_Tooltip::sINFO        3076 bytes  (``SIMPLE_TOOLTIP`` builds only)
        DWORD  s_dwID
        TCHAR  s_Title[512]
        TCHAR  s_Message[1024]

The shipped file is 627 368 bytes: 39 digimon lines, 230 event lines, 845
messages, 58 tips and 51 loading tips, which ends exactly at EOF — this build is
compiled **without** ``SIMPLE_TOOLTIP``, so the tooltip section is absent.  The
codec accepts an optional ``TalkTooltip`` section for builds that have one.
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, field, read_records, write_records
from ..fields import read_fields, write_fields

FT_TALK_DIGIMON_LEN = 100
FT_EVENTTALK_LEN = 200
FT_TALK_MSG_TITLE_LEN = 16
FT_TALK_MSG_BODY_LEN = 256
FT_TALK_TIP_LEN = 200
FT_TOOLTIP_TITLE_BODY_LEN = 512
FT_TOOLTIP_MSG_BODY_LEN = 1024

DIGIMON_FIELDS = [
    ("Param", "u32"),
    ("Type", "u16"),
    ("_pad0", "u16"),
    ("Text", ("w", FT_TALK_DIGIMON_LEN)),
    ("List", ("w", FT_TALK_DIGIMON_LEN)),
]

EVENT_FIELDS = [
    ("TalkNum", "u32"),
    ("Text", ("w", FT_EVENTTALK_LEN)),
]

MESSAGE_FIELDS = [
    ("ID", "u32"),
    ("MsgType", "i32"),
    ("ButtonType", "i32"),
    ("TitleName", ("w", FT_TALK_MSG_TITLE_LEN)),
    ("Message", ("w", FT_TALK_MSG_BODY_LEN)),
    ("LinkID", "u32"),
]

TIP_FIELDS = [("Tip", ("w", FT_TALK_TIP_LEN))]

LOADING_TIP_FIELDS = [
    ("LoadingTip", ("w", FT_TALK_TIP_LEN)),
    ("Level", "i32"),
]

TOOLTIP_FIELDS = [
    ("ID", "u32"),
    ("s_Title", ("w", FT_TOOLTIP_TITLE_BODY_LEN)),
    ("Message", ("w", FT_TOOLTIP_MSG_BODY_LEN)),
]


def _keyed(fields: list[tuple[str, Any]]):
    """A row that starts with a ``DWORD`` map key (the key is not in the struct)."""

    def read(reader: Reader) -> dict[str, Any]:
        record = {"Key": reader.u32()}
        record.update(read_fields(reader, fields))
        return record

    def write(writer: Writer, record: dict[str, Any]) -> None:
        writer.u32(field(record, "Key", "Talk"))
        write_fields(writer, fields, record)

    return read, write


def _plain(fields: list[tuple[str, Any]]):
    def read(reader: Reader) -> dict[str, Any]:
        return read_fields(reader, fields)

    def write(writer: Writer, record: dict[str, Any]) -> None:
        write_fields(writer, fields, record)

    return read, write


_read_digimon, _write_digimon = _keyed(DIGIMON_FIELDS)
_read_event, _write_event = _keyed(EVENT_FIELDS)
_read_message, _write_message = _plain(MESSAGE_FIELDS)
_read_tip, _write_tip = _keyed(TIP_FIELDS)
_read_loading_tip, _write_loading_tip = _keyed(LOADING_TIP_FIELDS)
_read_tooltip, _write_tooltip = _plain(TOOLTIP_FIELDS)


class TalkCodec(Codec):
    name = "Talk"
    filenames = ("talk",)
    sections = (
        "TalkDigimon",
        "TalkEvent",
        "TalkMessage",
        "TalkTip",
        "TalkLoadingTip",
        "TalkTooltip",
    )
    record_tags = {
        "TalkDigimon": "Digimon",
        "TalkEvent": "Event",
        "TalkMessage": "Message",
        "TalkTip": "Tip",
        "TalkLoadingTip": "LoadingTip",
        "TalkTooltip": "Tooltip",
    }

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        sections = {"TalkDigimon": read_records(reader, _read_digimon)}
        sections["TalkEvent"] = read_records(reader, _read_event)
        sections["TalkMessage"] = read_records(reader, _read_message)
        sections["TalkTip"] = read_records(reader, _read_tip)
        sections["TalkLoadingTip"] = read_records(reader, _read_loading_tip)
        # The tooltip table only exists in SIMPLE_TOOLTIP builds; the shipped file
        # ends here, so an empty remainder means "no sixth section".
        sections["TalkTooltip"] = (
            read_records(reader, _read_tooltip) if reader.pos < len(data) else []
        )
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": sections}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        write_records(writer, self._items(sections, "TalkDigimon"), _write_digimon)
        write_records(writer, self._items(sections, "TalkEvent"), _write_event)
        write_records(writer, self._items(sections, "TalkMessage"), _write_message)
        write_records(writer, self._items(sections, "TalkTip"), _write_tip)
        write_records(writer, self._items(sections, "TalkLoadingTip"), _write_loading_tip)
        tooltips = sections.get("TalkTooltip")
        if tooltips:
            if not isinstance(tooltips, list):
                raise FormatError("Talk: 'TalkTooltip' must be a list")
            write_records(writer, tooltips, _write_tooltip)
        return writer.getvalue()

