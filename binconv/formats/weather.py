"""``Weather.bin`` -- the per-map weather cycles.

Layout from the client, ``Weather.h`` (``CsWeather::sINFO``, ``CsWeather::sELEMENT``)
read by ``WeatherMng.cpp::_LoadBin`` (lines 227-264)::

    int32 nGroups
    per group:                                   ; CsWeatherGroup
        int32 nWeatherCount
        per weather:
            CsWeather::sINFO                     24 bytes
                DWORD s_dwMapID
                int   s_nCenterX, s_nCenterY, s_nRadius
                int   s_nElementCount             (drives the element list below)
                UINT  s_nTotalLoopMin
            s_nElementCount x CsWeather::sELEMENT     12 bytes
                int   s_nTime_Min
                int   s_nFatigue
                BYTE  s_Type                  ; eW_TYPE: 0 none, 1 snow, 2 rain
                BYTE  s_nLevel
                <2 bytes of struct padding>

The shipped file holds 7 groups, 13 weather entries and 47 elements (908 bytes),
which decodes exactly to EOF.  ``s_nElementCount`` is derived from the element
array on compile.
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, field, read_records, write_records
from ..fields import read_fields, write_fields

WEATHER_INFO_FIELDS = [
    ("s_dwMapID", "u32"),
    ("s_nCenterX", "i32"),
    ("s_nCenterY", "i32"),
    ("s_nRadius", "i32"),
]

WEATHER_ELEMENT_FIELDS = [
    ("s_nTime_Min", "i32"),
    ("s_nFatigue", "i32"),
    ("s_Type", "u8"),
    ("s_nLevel", "u8"),
    ("_pad0", "u16"),
]


def _read_weather(reader: Reader) -> dict[str, Any]:
    weather = read_fields(reader, WEATHER_INFO_FIELDS)
    count = reader.i32()
    if count < 0 or count > (len(reader.data) - reader.pos):
        raise FormatError(
            f"{reader.name}: implausible weather element count {count} "
            f"at offset {reader.pos - 4}"
        )
    weather["s_nTotalLoopMin"] = reader.u32()
    weather["Element"] = [read_fields(reader, WEATHER_ELEMENT_FIELDS) for _ in range(count)]
    return weather


def _write_weather(writer: Writer, weather: dict[str, Any]) -> None:
    where = "Weather"
    write_fields(writer, WEATHER_INFO_FIELDS, weather)
    elements = weather.get("Element")
    if not isinstance(elements, list):
        raise FormatError(f"{where}: 'Element' must be a list")
    writer.i32(len(elements))
    writer.u32(field(weather, "s_nTotalLoopMin", where))
    for element in elements:
        write_fields(writer, WEATHER_ELEMENT_FIELDS, element)


def _read_group(reader: Reader) -> dict[str, Any]:
    return {"Weather": read_records(reader, _read_weather)}


def _write_group(writer: Writer, group: dict[str, Any]) -> None:
    records = group.get("Weather")
    if not isinstance(records, list):
        raise FormatError("Weather: each group must have a 'Weather' list")
    write_records(writer, records, _write_weather)


class WeatherCodec(Codec):
    name = "Weather"
    filenames = ("weather",)
    sections = ("Weather",)
    record_tags = {"Weather": "Group"}

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        groups = read_records(reader, _read_group)
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": {"Weather": groups}}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        write_records(writer, self._items(sections, "Weather"), _write_group)
        return writer.getvalue()
