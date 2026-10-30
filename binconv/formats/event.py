"""``Event.bin`` -- time limited event tables.

Ported from ``reference/csharp/Event.cs``.  One file, six sections, in this
order (the reader has no header, so the order *is* the layout)::

    AttendenceTime  2 x TimeSpan, nine int32 each, **no count field**
    Event           count, 6 slot item table, 1024 byte name buffer
    MensalEvent     count, 6 slot item table, two 64 byte UTF-16 names
    MonthlyEvent    count, 512 char message, 28 slot item table
    TimeEvent       count, length prefixed strings, records may be 4 bytes
    Event100Days    count, six length prefixed strings, named item table

Details worth knowing:

* The item tables store **all** ``ItemId`` values first and **all**
  ``ItemCount`` values afterwards (the C# reader fills the pairs in two
  passes), and the slot count is fixed by the format -- the reader always takes
  six (or twenty-eight) slots, whatever the file says.
* ``AttendenceTime`` has no count: the reader always consumes two time spans.
* ``Event.Name`` is a 1024 byte buffer that the C# reader decodes as **ASCII**,
  which is why the old XML shows ``""`` for most events and a single stray
  letter (``"C"``) for the rest: the buffer really holds a NUL terminated
  UTF-16 name (``"Come Back Tamer! Event Reward"``, ``"Congratulations. Tamer
  level reached 10."``, ...).  JSON keeps the real name, so a recompile no
  longer erases the event texts.  This field is the *only* intentional
  difference from the old XML (compare with ``--ignore Name``).
* ``TimeEvent`` and ``Event100Days`` strings are ``int32 characters`` followed
  by UTF-16 data (no NUL terminator), so the length is derived on encode.
* A ``TimeEvent`` record whose ``Id`` is 0 is **four bytes long**: the C# reader
  skips the rest (``continue``) and leaves a null entry in its array, which makes
  the old XML export crash.  JSON keeps such a record as ``{"Id": 0}``.
* ``TimeEvent.unknow`` is the trailing int16 the C# reader discards.  It is
  stored anyway so a round-trip stays byte exact; the old writer always emitted
  ``0`` there.
"""

from __future__ import annotations

from typing import Any, Sequence

from ..binary import FormatError, Reader, UTF16, Writer
from ..codec import Codec, field, read_records, write_records
from ..fields import read_fields, write_fields

TIMESPAN_FIELDS = [
    ("tm_sec", "i32"),
    ("tm_min", "i32"),
    ("tm_hour", "i32"),
    ("tm_mday", "i32"),
    ("tm_mon", "i32"),
    ("tm_year", "i32"),
    ("tm_wday", "i32"),
    ("tm_yday", "i32"),
    ("tm_isdst", "i32"),
]

MENSAL_EVENT_FIELDS = [
    ("Id", "i32"),
    ("s_nUse", "i32"),
    ("s_nIndex", "i32"),
    ("s_nType", "i32"),
    ("s_nSuccessType", "i32"),
    ("s_nSuccessValue", "i32"),
    ("s_nItemKind", "i32"),
]

#: ``AttendenceTime`` has no count field, the reader always takes this many.
ATTENDENCE_SLOTS = 2
EVENT_SLOTS = 6
MENSAL_EVENT_SLOTS = 6
MONTHLY_EVENT_SLOTS = 28

EVENT_NAME_CHARS = 512  # 1024 byte UTF-16 buffer, NUL terminated
MENSAL_NAME_CHARS = 32  # 64 byte UTF-16 buffers
MONTHLY_MESSAGE_CHARS = 512  # 1024 byte UTF-16 buffer

EVENT_100DAYS_STRINGS = (
    "Event",
    "EventTitle",
    "EventDescript",
    "StartTime",
    "EndTime",
    "Reset",
)


# -- item tables --------------------------------------------------------
def _read_slots(reader: Reader, slots: int) -> list[dict[str, Any]]:
    """Read *slots* ``ItemId``/``ItemCount`` pairs stored as two flat arrays."""

    ids = [reader.i32() for _ in range(slots)]
    counts = [reader.i16() for _ in range(slots)]
    return [{"ItemId": item_id, "ItemCount": count} for item_id, count in zip(ids, counts)]


def _write_slots(writer: Writer, items: Any, slots: int, where: str) -> None:
    if not isinstance(items, list):
        raise FormatError(f"{where}: item table must be a list")
    if len(items) != slots:
        raise FormatError(
            f"{where}: expected exactly {slots} item slot(s), got {len(items)}"
        )
    for item in items:
        writer.i32(field(item, "ItemId", where))
    for item in items:
        writer.i16(field(item, "ItemCount", where))


# -- length prefixed UTF-16 strings ------------------------------------
def _read_text(reader: Reader) -> str:
    """Read ``int32 characters`` followed by that many UTF-16 characters."""

    size = reader.i32()
    if size < 0:
        raise FormatError(
            f"{reader.name}: negative string length {size} at offset {reader.pos - 4}"
        )
    # `Encoding.Unicode.GetString` does not trim, so neither do we: the decoded
    # text keeps embedded NULs and re-encodes to the same byte count.
    return reader.raw(size * 2).decode(UTF16, "replace")


def _write_text(writer: Writer, value: Any) -> None:
    text = value if isinstance(value, str) else str(value)
    data = text.encode(UTF16, "replace")
    writer.i32(len(data) // 2)
    writer.raw(data)


def _list(record: dict[str, Any], name: str, where: str) -> list[dict[str, Any]]:
    try:
        value = record[name]
    except KeyError:
        raise FormatError(f"{where}: missing required list {name!r}") from None
    if not isinstance(value, list):
        raise FormatError(f"{where}: {name!r} must be a list")
    return value


# -- AttendenceTime ----------------------------------------------------
def _read_attendence(reader: Reader) -> list[dict[str, Any]]:
    return [read_fields(reader, TIMESPAN_FIELDS) for _ in range(ATTENDENCE_SLOTS)]


def _write_attendence(writer: Writer, records: Sequence[dict[str, Any]]) -> None:
    items = list(records)
    if len(items) != ATTENDENCE_SLOTS:
        raise FormatError(
            f"AttendenceTime: the game always reads exactly {ATTENDENCE_SLOTS} "
            f"time span(s), got {len(items)}"
        )
    for record in items:
        write_fields(writer, TIMESPAN_FIELDS, record)


# -- Event -------------------------------------------------------------
def _read_event(reader: Reader) -> dict[str, Any]:
    record = {"s_TableNo": reader.i32(), "TimeInMinutes": reader.i32()}
    record["EventItems"] = _read_slots(reader, EVENT_SLOTS)
    record["Name"] = reader.wstring(EVENT_NAME_CHARS)
    return record


def _write_event(writer: Writer, record: dict[str, Any]) -> None:
    writer.i32(field(record, "s_TableNo", "Event"))
    writer.i32(field(record, "TimeInMinutes", "Event"))
    _write_slots(writer, _list(record, "EventItems", "Event"), EVENT_SLOTS, "Event")
    writer.wstring(field(record, "Name", "Event"), EVENT_NAME_CHARS)


# -- MensalEvent -------------------------------------------------------
def _read_mensal(reader: Reader) -> dict[str, Any]:
    record = read_fields(reader, MENSAL_EVENT_FIELDS)
    record["MensalItems"] = _read_slots(reader, MENSAL_EVENT_SLOTS)
    record["Name"] = reader.wstring(MENSAL_NAME_CHARS)
    record["EndTime"] = reader.wstring(MENSAL_NAME_CHARS)
    return record


def _write_mensal(writer: Writer, record: dict[str, Any]) -> None:
    write_fields(writer, MENSAL_EVENT_FIELDS, record)
    _write_slots(
        writer,
        _list(record, "MensalItems", "MensalEvent"),
        MENSAL_EVENT_SLOTS,
        "MensalEvent",
    )
    writer.wstring(field(record, "Name", "MensalEvent"), MENSAL_NAME_CHARS)
    writer.wstring(field(record, "EndTime", "MensalEvent"), MENSAL_NAME_CHARS)


# -- MonthlyEvent ------------------------------------------------------
def _read_monthly(reader: Reader) -> dict[str, Any]:
    record = {
        "s_nTableNo": reader.i32(),
        "s_szMessage": reader.wstring(MONTHLY_MESSAGE_CHARS),
    }
    record["MonthlyItems"] = _read_slots(reader, MONTHLY_EVENT_SLOTS)
    return record


def _write_monthly(writer: Writer, record: dict[str, Any]) -> None:
    writer.i32(field(record, "s_nTableNo", "MonthlyEvent"))
    writer.wstring(field(record, "s_szMessage", "MonthlyEvent"), MONTHLY_MESSAGE_CHARS)
    _write_slots(
        writer,
        _list(record, "MonthlyItems", "MonthlyEvent"),
        MONTHLY_EVENT_SLOTS,
        "MonthlyEvent",
    )


# -- TimeEvent ---------------------------------------------------------
def _read_time_event(reader: Reader) -> dict[str, Any]:
    record: dict[str, Any] = {"Id": reader.i32()}
    if record["Id"] == 0:
        return record  # the C# reader stops here (and leaves a null entry)
    record["StartDate"] = _read_text(reader)
    record["EndDate"] = _read_text(reader)
    record["Day"] = reader.i32()
    record["StartTime"] = _read_text(reader)
    record["EndTime"] = _read_text(reader)
    record["ItemId"] = reader.i32()
    record["ItemCount"] = reader.i16()
    record["unknow"] = reader.i16()
    return record


def _write_time_event(writer: Writer, record: dict[str, Any]) -> None:
    writer.i32(field(record, "Id", "TimeEvent"))
    if record["Id"] == 0:
        return
    _write_text(writer, field(record, "StartDate", "TimeEvent"))
    _write_text(writer, field(record, "EndDate", "TimeEvent"))
    writer.i32(field(record, "Day", "TimeEvent"))
    _write_text(writer, field(record, "StartTime", "TimeEvent"))
    _write_text(writer, field(record, "EndTime", "TimeEvent"))
    writer.i32(field(record, "ItemId", "TimeEvent"))
    writer.i16(field(record, "ItemCount", "TimeEvent"))
    writer.i16(record.get("unknow", 0))


# -- Event100Days ------------------------------------------------------
def _read_cem_item(reader: Reader) -> dict[str, Any]:
    record = {"Name": _read_text(reader)}
    record["ItemId"] = reader.i32()
    record["ItemCount"] = reader.i16()
    record["Unknow"] = reader.i16()
    return record


def _write_cem_item(writer: Writer, record: dict[str, Any]) -> None:
    _write_text(writer, field(record, "Name", "Event100Days item"))
    writer.i32(field(record, "ItemId", "Event100Days item"))
    writer.i16(field(record, "ItemCount", "Event100Days item"))
    writer.i16(record.get("Unknow", 0))


def _read_100days(reader: Reader) -> dict[str, Any]:
    record: dict[str, Any] = {"Id": reader.i32()}
    for name in EVENT_100DAYS_STRINGS:
        record[name] = _read_text(reader)
    record["EventItems"] = read_records(reader, _read_cem_item)
    return record


def _write_100days(writer: Writer, record: dict[str, Any]) -> None:
    writer.i32(field(record, "Id", "Event100Days"))
    for name in EVENT_100DAYS_STRINGS:
        _write_text(writer, field(record, name, "Event100Days"))
    write_records(writer, _list(record, "EventItems", "Event100Days"), _write_cem_item)


class EventCodec(Codec):
    name = "Event"
    filenames = ("event",)
    sections = (
        "AttendenceTime",
        "Event",
        "MensalEvent",
        "MonthlyEvent",
        "TimeEvent",
        "Event100Days",
    )
    record_tags = {
        "AttendenceTime": "TimeSpan",
        "Event": "Event",
        "MensalEvent": "MensalEvent",
        "MonthlyEvent": "MonthlyEvent",
        "TimeEvent": "TimeEvent",
        "Event100Days": "Event100Days",
    }

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        sections: dict[str, Any] = {"AttendenceTime": _read_attendence(reader)}
        sections["Event"] = read_records(reader, _read_event)
        sections["MensalEvent"] = read_records(reader, _read_mensal)
        sections["MonthlyEvent"] = read_records(reader, _read_monthly)
        sections["TimeEvent"] = read_records(reader, _read_time_event)
        sections["Event100Days"] = read_records(reader, _read_100days)
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": sections}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        _write_attendence(writer, self._items(sections, "AttendenceTime"))
        write_records(writer, self._items(sections, "Event"), _write_event)
        write_records(writer, self._items(sections, "MensalEvent"), _write_mensal)
        write_records(writer, self._items(sections, "MonthlyEvent"), _write_monthly)
        write_records(writer, self._items(sections, "TimeEvent"), _write_time_event)
        write_records(writer, self._items(sections, "Event100Days"), _write_100days)
        return writer.getvalue()
