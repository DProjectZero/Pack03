"""``TamerList.bin`` -- the tamer definitions and the emote table.

Layout from the client, ``Tamer.h`` (``CsTamer::sINFO`` with ``TAMER_MAX_SKILL_COUNT``
5, ``TAMER_COMMENT_LEN`` 512, and ``CsEmotion::sINFO`` with ``EMOTION_STR_LEN`` 16,
``EMOTION_CMD_COUNT`` 5) read by ``TamerMng.cpp::_LoadBin`` (lines 435-460)::

    int32 nCount
    nCount x CsTamer::sINFO                1500 bytes
        DWORD s_dwTamerID
        TCHAR s_szName[64]                         128 bytes
        char  s_cSoundDirName[64]
        BYTE  s_nTamerType
        <3 bytes of struct padding>
        sSKILL s_Skill[5]                  {DWORD s_dwID}
        TCHAR s_szComment[512]                    1024 bytes
        TCHAR s_szPart[64]                         128 bytes
        TCHAR s_szGender[64]                       128 bytes   (COSTUME_GENDER builds)

    int32 nEmotionCount
    nEmotionCount x CsEmotion::sINFO       204 bytes
        DWORD s_nID
        TCHAR s_szName[16]                          32 bytes
        TCHAR s_szCmd[5][16]                       160 bytes
        DWORD s_nAniID
        BYTE  s_nUseCmdCount
        <3 bytes of struct padding>

The shipped file holds 12 tamers and 9 emotions (19 844 bytes = 4 + 12 * 1500 +
4 + 9 * 204), which decodes exactly to EOF.  The 1 500-byte stride proves this
build is compiled with ``COSTUME_GENDER`` (``s_szGender`` present).
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, field, read_records, write_records
from ..fields import read_fields, write_fields

TAMER_MAX_SKILL_COUNT = 5
TAMER_COMMENT_LEN = 512
EMOTION_STR_LEN = 16
EMOTION_CMD_COUNT = 5

TAMER_FIELDS = [
    ("TamerID", "u32"),
    ("Name", ("w", 64)),
    ("SoundDirName", ("c", "ascii", 64)),
    ("TamerType", "u8"),
    ("_pad0", "u8"),
    ("_pad1", "u16"),
]

TAMER_TAIL_FIELDS = [
    ("Comment", ("w", TAMER_COMMENT_LEN)),
    ("Part", ("w", 64)),
    ("Gender", ("w", 64)),
]

EMOTION_FIELDS = [("ID", "u32"), ("Name", ("w", EMOTION_STR_LEN))]

EMOTION_TAIL_FIELDS = [("AniID", "u32"), ("UseCmdCount", "u8"), ("_pad0", "u8"), ("_pad1", "u16")]


def _read_tamer(reader: Reader) -> dict[str, Any]:
    tamer = read_fields(reader, TAMER_FIELDS)
    tamer["Skill"] = [{"ID": reader.u32()} for _ in range(TAMER_MAX_SKILL_COUNT)]
    tamer.update(read_fields(reader, TAMER_TAIL_FIELDS))
    return tamer


def _write_tamer(writer: Writer, tamer: dict[str, Any]) -> None:
    where = "TamerList"
    write_fields(writer, TAMER_FIELDS, tamer)
    skills = tamer.get("Skill")
    if not isinstance(skills, list) or len(skills) != TAMER_MAX_SKILL_COUNT:
        raise FormatError(
            f"{where}: 's_Skill' must be a list of {TAMER_MAX_SKILL_COUNT} entries"
        )
    for skill in skills:
        writer.u32(field(skill, "ID", where))
    write_fields(writer, TAMER_TAIL_FIELDS, tamer)


def _read_emotion(reader: Reader) -> dict[str, Any]:
    emotion = read_fields(reader, EMOTION_FIELDS)
    emotion["Cmd"] = [reader.wstring(EMOTION_STR_LEN) for _ in range(EMOTION_CMD_COUNT)]
    emotion.update(read_fields(reader, EMOTION_TAIL_FIELDS))
    return emotion


def _write_emotion(writer: Writer, emotion: dict[str, Any]) -> None:
    where = "Emotion"
    write_fields(writer, EMOTION_FIELDS, emotion)
    commands = emotion.get("Cmd")
    if not isinstance(commands, list) or len(commands) != EMOTION_CMD_COUNT:
        raise FormatError(f"{where}: 's_szCmd' must be a list of {EMOTION_CMD_COUNT} strings")
    for command in commands:
        writer.wstring(command, EMOTION_STR_LEN)
    write_fields(writer, EMOTION_TAIL_FIELDS, emotion)


class TamerListCodec(Codec):
    name = "TamerList"
    filenames = ("tamerlist",)
    sections = ("TamerList", "Emotion")
    record_tags = {"TamerList": "Tamer", "Emotion": "Emotion"}

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        sections = {"TamerList": read_records(reader, _read_tamer)}
        sections["Emotion"] = read_records(reader, _read_emotion)
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": sections}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        write_records(writer, self._items(sections, "TamerList"), _write_tamer)
        write_records(writer, self._items(sections, "Emotion"), _write_emotion)
        return writer.getvalue()

