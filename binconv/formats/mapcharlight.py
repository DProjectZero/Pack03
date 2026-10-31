"""``MapCharLight.bin`` -- per-map character lighting (directional or point lights).

Layout from the client, ``MapCharLight.h`` (``CsMapCharLight::sINFO_BASE`` /
``sINFO_DIR`` / ``sINFO_POINT``) read by ``MapCharLightMng.cpp::_LoadBin``
(lines 349-381)::

    int32 nGroups
    per group:                                  ; keyed by s_dwMapID
        int32 nCountLight
        per light:
            int32 nType                         ; 0 = directional, 1 = point
            sINFO_DIR                          108 bytes when nType == 0
            sINFO_POINT                         84 bytes when nType == 1

    sINFO_BASE                              56 bytes (both variants start with it)
        DWORD s_dwMapID
        bool  s_bChar
        bool  s_bShadow
        <2 bytes of struct padding>
        int   s_nType
        bool  s_bEnableLight
        <3 bytes of struct padding>
        float s_fDiffuse[3], s_fAmbient[3], s_fSpecular[3], s_fPower

    sINFO_DIR      = sINFO_BASE + float s_fRot[3][3], s_fPos[3], s_fScale
    sINFO_POINT    = sINFO_BASE + float s_Pos[3], s_C, s_L, s_Q, s_Range

The selector written ahead of the struct (``nType``) is kept as ``_Type`` because
the struct carries its own independent ``s_nType``.  The shipped file holds 116
groups with 227 directional lights and no point lights (25 892 bytes), which
decodes exactly to EOF.
"""

from __future__ import annotations

from typing import Any, Sequence

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, field, read_records, write_records
from ..fields import read_fields, write_fields

LIGHT_DIR = 0
LIGHT_POINT = 1

BASE_FIELDS: list[tuple[str, Any]] = [
    ("MapID", "u32"),
    ("Char", "u8"),
    ("Shadow", "u8"),
    ("_pad0", "u16"),
    ("Type", "i32"),
    ("EnableLight", "u8"),
    ("_pad1", "u8"),
    ("_pad2", "u16"),
]

DIR_FLOATS = (("Diffuse", 3), ("Ambient", 3), ("Specular", 3))
BASE_TAIL = (("Power", 1),)
DIR_TAIL = (("Rot", 9), ("Pos", 3), ("Scale", 1))
POINT_TAIL = (("s_Pos", 3), ("s_C", 1), ("s_L", 1), ("s_Q", 1), ("s_Range", 1))


def _read_floats(reader: Reader, groups: Sequence[tuple[str, int]]) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    for name, count in groups:
        out[name] = [reader.f32() for _ in range(count)]
    return out


def _write_floats(
    writer: Writer, groups: Sequence[tuple[str, int]], record: dict[str, Any], where: str
) -> None:
    for name, count in groups:
        values = record.get(name)
        if not isinstance(values, list) or len(values) != count:
            raise FormatError(f"{where}: {name!r} must be a list of {count} numbers")
        for value in values:
            writer.f32(value)


def _read_light(reader: Reader) -> dict[str, Any]:
    light = {"_Type": reader.i32()}
    light.update(read_fields(reader, BASE_FIELDS))
    light.update(_read_floats(reader, DIR_FLOATS))
    light.update(_read_floats(reader, BASE_TAIL))
    tail = DIR_TAIL if light["_Type"] == LIGHT_DIR else POINT_TAIL
    if light["_Type"] not in (LIGHT_DIR, LIGHT_POINT):
        raise FormatError(f"{reader.name}: unknown light type {light['_Type']}")
    light.update(_read_floats(reader, tail))
    # s_fRot is a float[3][3] in the client; keep it flat so the JSON stays simple.
    return light


def _write_light(writer: Writer, light: dict[str, Any]) -> None:
    where = "MapCharLight"
    kind = field(light, "_Type", where)
    writer.i32(kind)
    write_fields(writer, BASE_FIELDS, light)
    _write_floats(writer, DIR_FLOATS, light, where)
    _write_floats(writer, BASE_TAIL, light, where)
    if kind == LIGHT_DIR:
        _write_floats(writer, DIR_TAIL, light, where)
    elif kind == LIGHT_POINT:
        _write_floats(writer, POINT_TAIL, light, where)
    else:
        raise FormatError(f"{where}: unknown light type {kind}")


def _read_group(reader: Reader) -> dict[str, Any]:
    return {"Light": read_records(reader, _read_light)}


def _write_group(writer: Writer, group: dict[str, Any]) -> None:
    lights = group.get("Light")
    if not isinstance(lights, list):
        raise FormatError("MapCharLight: each group must have a 'Light' list")
    write_records(writer, lights, _write_light)


class MapCharLightCodec(Codec):
    name = "MapCharLight"
    filenames = ("mapcharlight",)
    sections = ("MapCharLight",)
    record_tags = {"MapCharLight": "Group"}

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        groups = read_records(reader, _read_group)
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": {"MapCharLight": groups}}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        write_records(writer, self._items(sections, "MapCharLight"), _write_group)
        return writer.getvalue()
