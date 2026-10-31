"""``Scene.bin`` -- the cutscene scripts and their camera targets.

Layout from the client, ``SceneData.h`` (``CSceneData::sSceneInfo``, ``sData``;
``MAX_SCENE_CHARNUM`` 5) and ``SceneDataMng.h`` (``sTargetData``), read by
``SceneDataMng.cpp::_LoadBin`` (lines 333-382)::

    int32 nScenes
    per scene:
        CSceneData::sSceneInfo               212 bytes
            DWORD s_dwSceneID
            bool  s_bUse
            <1 byte of struct padding: TCHAR follows on a 2-byte boundary>
            TCHAR s_szTitle[64]                    128 bytes
            <2 bytes of struct padding>
            int   s_nMap
            int   s_nResion
            bool  s_bSkip
            char  s_szMusic[64]
            <3 bytes of struct tail padding>

        int32 nLines
        per line:
            CSceneData::sData                2204 bytes
                DWORD s_dwMainTarget
                DWORD s_dwTarget[5]
                DWORD s_dwAni
                TCHAR s_szTalk[1024]              2048 bytes
                char  s_szEffect[64]
                char  s_szSound[64]

    int32 nTargets
    per target:
        CsSceneDataMng::sTargetData           80 bytes
            DWORD s_dwUID
            DWORD s_dwModelID
            float s_fDist
            float s_fHeight
            TCHAR s_szName[32]                     64 bytes

The shipped file holds 194 scenes with 1 645 lines plus 153 camera targets
(3 679 732 bytes), which decodes exactly to EOF.
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, field, read_records, write_records
from ..fields import read_fields, write_fields

MAX_SCENE_CHARNUM = 5

SCENE_INFO_FIELDS = [
    ("SceneID", "u32"),
    ("Use", "u8"),
    ("_pad0", "u8"),
    ("Title", ("w", 64)),
    ("_pad1", "u16"),
    ("Map", "i32"),
    ("Resion", "i32"),
    ("Skip", "u8"),
    ("Music", ("c", "ascii", 64)),
    ("_pad2", "u8"),
    ("_pad3", "u16"),
]

SCENE_DATA_FIELDS = [
    ("Ani", "u32"),
    ("Talk", ("w", 1024)),
    ("Effect", ("c", "ascii", 64)),
    ("Sound", ("c", "ascii", 64)),
]

TARGET_FIELDS = [
    ("UID", "u32"),
    ("ModelID", "u32"),
    ("Dist", "f32"),
    ("Height", "f32"),
    ("Name", ("w", 32)),
]


def _read_line(reader: Reader) -> dict[str, Any]:
    line = {"MainTarget": reader.u32()}
    line["Target"] = [reader.u32() for _ in range(MAX_SCENE_CHARNUM)]
    line.update(read_fields(reader, SCENE_DATA_FIELDS))
    return line


def _write_line(writer: Writer, line: dict[str, Any]) -> None:
    where = "Scene"
    writer.u32(field(line, "MainTarget", where))
    targets = line.get("Target")
    if not isinstance(targets, list) or len(targets) != MAX_SCENE_CHARNUM:
        raise FormatError(f"{where}: 's_dwTarget' must be a list of {MAX_SCENE_CHARNUM}")
    for target in targets:
        writer.u32(target)
    write_fields(writer, SCENE_DATA_FIELDS, line)


def _read_scene(reader: Reader) -> dict[str, Any]:
    scene = read_fields(reader, SCENE_INFO_FIELDS)
    count = reader.i32()
    if count < 0 or count > (len(reader.data) - reader.pos):
        raise FormatError(
            f"{reader.name}: implausible scene line count {count} "
            f"at offset {reader.pos - 4}"
        )
    scene["Line"] = [_read_line(reader) for _ in range(count)]
    return scene


def _write_scene(writer: Writer, scene: dict[str, Any]) -> None:
    write_fields(writer, SCENE_INFO_FIELDS, scene)
    lines = scene.get("Line")
    if not isinstance(lines, list):
        raise FormatError("Scene: 'Line' must be a list")
    writer.i32(len(lines))
    for line in lines:
        _write_line(writer, line)


def _read_target(reader: Reader) -> dict[str, Any]:
    return read_fields(reader, TARGET_FIELDS)


def _write_target(writer: Writer, target: dict[str, Any]) -> None:
    write_fields(writer, TARGET_FIELDS, target)


class SceneCodec(Codec):
    name = "Scene"
    filenames = ("scene",)
    sections = ("Scene", "Target")
    record_tags = {"Scene": "Scene", "Target": "Target"}

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        sections = {"Scene": read_records(reader, _read_scene)}
        sections["Target"] = read_records(reader, _read_target)
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": sections}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        write_records(writer, self._items(sections, "Scene"), _write_scene)
        write_records(writer, self._items(sections, "Target"), _write_target)
        return writer.getvalue()
