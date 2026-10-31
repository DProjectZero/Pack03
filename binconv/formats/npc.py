"""``Npc.bin`` -- the NPC table: definitions, models and event (card game) rows.

Layout from the client, ``Npc.h`` (``CsNpc::sINFO``, 1176 bytes) plus the type
dependent "extras" that ``NpcMng.cpp`` reads after it.  The conditionals are
driven by ``nsCsNpcTable::eNPC_TYPE`` (``nsCsNpcTable.h``); the field layout below
follows the v487 schema ``Npc.json`` from Arves100/MISDMO (shipped in the server
tree at ``Tools/NPCEditor/Util/Npc.json``).  Decoding the shipped file this way
lands exactly on EOF (1861 NPCs, 609 models, 1 event row).

::

    DWORD  s_dwNpcID, s_dwMapID
    int    s_eType                 ; nsCsNpcTable::eNPC_TYPE
    int    s_eMoveType             ; nsCsNpcTable::eNPC_MOVE
    DWORD  s_nDisplayPlag          ; eDISPLAY bit flags (client's spelling)
    DWORD  s_dwModelID
    TCHAR  s_szPenName[32]                     64 bytes
    TCHAR  s_szName[32]                        64 bytes
    TCHAR  s_szTalk[512]                     1024 bytes

    if s_eType == NT_PORTAL (3):
        int   _Unk
        int   nData
        per data: int _Unk; Requirements[3] { int Type; DWORD Id; DWORD Count; }

    if s_eType in {NT_TRADE(1), NT_GUILD(8), NT_DIGICORE(9), NT_EVENT_STORE(12),
                   NT_PROPERTY_STORE(14), NT_MASTERS_MATCHING(16)}:
        int   nItems
        DWORD Items[nItems]

    if s_eType == NT_SPECIAL_EVENT (19):
        int   Type                 ; 0 none, 2 Puppetmon card game
        if Type == 2: int nItems; DWORD Items[nItems]

    int   nExtra                   ; eNPC_EXTRA: NE_QUEST (0) is the only kind
    per extra:
        int TypeEx
        if TypeEx == NE_QUEST:
            int   ShowState        ; eNPC_SHOW: 0 hide, 1 show
            int   nActions
            per action: int CompleteType; int ShowAfterCompleted;
                        int nQuests; int QuestList[nQuests]

    int   nModels                  ; 609 x ModelInfo (140 bytes)
        DWORD  Id; USHORT _Unk0, _Unk1, _Unk2;
        TCHAR  ModelPath[64]; <2 bytes of struct padding>

    int   nEvents                  ; 1 x EventInfo (60 bytes)
        DWORD Id; USHORT Attempts; <pad>;
        DWORD BitsToPay, ItemToConsume, ItemConsumeCount;
        Items[5] { DWORD Id; SHORT Count; <pad> }

The conditional blocks are stored as ``Portal`` / ``Store`` / ``Special`` /
``ExtraInfo`` keys and are only present when ``s_eType`` (or ``TypeEx``) says so;
``compile`` re-derives their presence from the type, so the file cannot drift.
"""

from __future__ import annotations

from typing import Any

from ..binary import FormatError, Reader, Writer
from ..codec import Codec, field, read_records, write_records
from ..fields import read_fields, write_fields

NPC_NAME_LEN = 32
NPC_TALK_LEN = 512
PORTAL_REQUIREMENT_COUNT = 3
NPC_MODEL_PATH_LEN = 64
NPC_EVENT_ITEM_COUNT = 5

NT_NONE = 0
NT_PORTAL = 3
NT_SPECIAL_EVENT = 19
NT_STORE_TYPES = frozenset({1, 8, 9, 12, 14, 16})  # shop-like types carrying a store list
NE_QUEST = 0

MODEL_FIELDS = [
    ("ID", "u32"),
    ("_Unk0", "u16"),
    ("_Unk1", "u16"),
    ("_Unk2", "u16"),
    ("ModelPath", ("w", NPC_MODEL_PATH_LEN)),
    ("_pad0", "u16"),
]

EVENT_ITEM_FIELDS = [("ID", "u32"), ("Count", "i16"), ("_pad0", "i16")]

EVENT_FIELDS = [
    ("ID", "u32"),
    ("Attempts", "u16"),
    ("_pad0", "u16"),
    ("BitsToPay", "u32"),
    ("ItemToConsume", "u32"),
    ("ItemConsumeCount", "u32"),
]


def _count(reader: Reader, what: str) -> int:
    count = reader.i32()
    if count < 0 or count > (len(reader.data) - reader.pos):
        raise FormatError(
            f"{reader.name}: implausible {what} count {count} at offset {reader.pos - 4}"
        )
    return count


def _read_u32_list(reader: Reader, what: str) -> list[int]:
    return [reader.u32() for _ in range(_count(reader, what))]


def _write_u32_list(writer: Writer, values: Any, what: str) -> None:
    if not isinstance(values, list):
        raise FormatError(f"Npc: {what!r} must be a list")
    writer.i32(len(values))
    for value in values:
        writer.u32(value)


def _read_portal(reader: Reader) -> dict[str, Any]:
    portal: dict[str, Any] = {"_Unk": reader.i32()}
    portal["Data"] = [
        {
            "_Unk": reader.i32(),
            "Requirements": [
                {"Type": reader.u32(), "ID": reader.u32(), "Count": reader.u32()}
                for _ in range(PORTAL_REQUIREMENT_COUNT)
            ],
        }
        for _ in range(_count(reader, "portal data"))
    ]
    return portal


def _write_portal(writer: Writer, portal: dict[str, Any]) -> None:
    writer.i32(field(portal, "_Unk", "Npc.Portal"))
    data = portal.get("Data")
    if not isinstance(data, list):
        raise FormatError("Npc.Portal: 'Data' must be a list")
    writer.i32(len(data))
    for entry in data:
        writer.i32(field(entry, "_Unk", "Npc.Portal"))
        requirements = entry.get("Requirements")
        if not isinstance(requirements, list) or len(requirements) != PORTAL_REQUIREMENT_COUNT:
            raise FormatError(
                f"Npc.Portal: 'Requirements' must be a list of {PORTAL_REQUIREMENT_COUNT}"
            )
        for requirement in requirements:
            writer.u32(field(requirement, "Type", "Npc.Portal"))
            writer.u32(field(requirement, "ID", "Npc.Portal"))
            writer.u32(field(requirement, "Count", "Npc.Portal"))


def _read_extra(reader: Reader) -> dict[str, Any]:
    extra: dict[str, Any] = {"TypeEx": reader.i32()}
    if extra["TypeEx"] == NE_QUEST:
        extra["Quest"] = {
            "ShowState": reader.i32(),
            "Actions": [
                {
                    "CompleteType": reader.i32(),
                    "ShowAfterCompleted": reader.i32(),
                    "QuestList": _read_u32_list(reader, "quest action"),
                }
                for _ in range(_count(reader, "quest action"))
            ],
        }
    return extra


def _write_extra(writer: Writer, extra: dict[str, Any]) -> None:
    where = "Npc.ExtraInfo"
    type_ex = field(extra, "TypeEx", where)
    writer.i32(type_ex)
    if type_ex != NE_QUEST:
        return
    quest = extra.get("Quest")
    if not isinstance(quest, dict):
        raise FormatError(f"{where}: 'Quest' is required when TypeEx is {NE_QUEST}")
    writer.i32(field(quest, "ShowState", where))
    actions = quest.get("Actions")
    if not isinstance(actions, list):
        raise FormatError(f"{where}: 'Actions' must be a list")
    writer.i32(len(actions))
    for action in actions:
        writer.i32(field(action, "CompleteType", where))
        writer.i32(field(action, "ShowAfterCompleted", where))
        writer.i32(len(action.get("QuestList") or []))
        for quest_id in action.get("QuestList") or []:
            writer.u32(quest_id)


def _read_npc(reader: Reader) -> dict[str, Any]:
    npc: dict[str, Any] = {
        "NpcID": reader.u32(),
        "MapID": reader.u32(),
        "Type": reader.i32(),
        "MoveType": reader.i32(),
        "DisplayPlag": reader.u32(),
        "ModelID": reader.u32(),
        "PenName": reader.wstring(NPC_NAME_LEN),
        "Name": reader.wstring(NPC_NAME_LEN),
        "Talk": reader.wstring(NPC_TALK_LEN),
    }
    npc_type = npc["Type"]
    if npc_type == NT_PORTAL:
        npc["Portal"] = _read_portal(reader)
    if npc_type in NT_STORE_TYPES:
        npc["Store"] = {"Items": _read_u32_list(reader, "store item")}
    if npc_type == NT_SPECIAL_EVENT:
        special: dict[str, Any] = {"Type": reader.i32()}
        if special["Type"] == 2:
            special["Items"] = _read_u32_list(reader, "special item")
        npc["Special"] = special
    npc["ExtraInfo"] = [_read_extra(reader) for _ in range(_count(reader, "npc extra"))]
    return npc


def _write_npc(writer: Writer, npc: dict[str, Any]) -> None:
    where = "Npc"
    writer.u32(field(npc, "NpcID", where))
    writer.u32(field(npc, "MapID", where))
    npc_type = field(npc, "Type", where)
    writer.i32(npc_type)
    writer.i32(field(npc, "MoveType", where))
    writer.u32(field(npc, "DisplayPlag", where))
    writer.u32(field(npc, "ModelID", where))
    writer.wstring(field(npc, "PenName", where), NPC_NAME_LEN)
    writer.wstring(field(npc, "Name", where), NPC_NAME_LEN)
    writer.wstring(field(npc, "Talk", where), NPC_TALK_LEN)
    if npc_type == NT_PORTAL:
        portal = npc.get("Portal")
        if not isinstance(portal, dict):
            raise FormatError(f"{where}: 'Portal' is required for NT_PORTAL records")
        _write_portal(writer, portal)
    if npc_type in NT_STORE_TYPES:
        store = npc.get("Store")
        if not isinstance(store, dict):
            raise FormatError(f"{where}: 'Store' is required for type {npc_type}")
        _write_u32_list(writer, store.get("Items"), "Store.Items")
    if npc_type == NT_SPECIAL_EVENT:
        special = npc.get("Special")
        if not isinstance(special, dict):
            raise FormatError(f"{where}: 'Special' is required for NT_SPECIAL_EVENT")
        special_type = field(special, "Type", where)
        writer.i32(special_type)
        if special_type == 2:
            _write_u32_list(writer, special.get("Items"), "Special.Items")
    extras = npc.get("ExtraInfo")
    if not isinstance(extras, list):
        raise FormatError(f"{where}: 'ExtraInfo' must be a list")
    writer.i32(len(extras))
    for extra in extras:
        _write_extra(writer, extra)


def _read_model(reader: Reader) -> dict[str, Any]:
    return read_fields(reader, MODEL_FIELDS)


def _write_model(writer: Writer, model: dict[str, Any]) -> None:
    write_fields(writer, MODEL_FIELDS, model)


def _read_event(reader: Reader) -> dict[str, Any]:
    event = read_fields(reader, EVENT_FIELDS)
    event["Items"] = [read_fields(reader, EVENT_ITEM_FIELDS) for _ in range(NPC_EVENT_ITEM_COUNT)]
    return event


def _write_event(writer: Writer, event: dict[str, Any]) -> None:
    write_fields(writer, EVENT_FIELDS, event)
    items = event.get("Items")
    if not isinstance(items, list) or len(items) != NPC_EVENT_ITEM_COUNT:
        raise FormatError(f"NpcEvent: 'Items' must be a list of {NPC_EVENT_ITEM_COUNT}")
    for item in items:
        write_fields(writer, EVENT_ITEM_FIELDS, item)


class NpcCodec(Codec):
    name = "Npc"
    filenames = ("npc",)
    sections = ("Npc", "NpcModel", "NpcEvent")
    record_tags = {"Npc": "Npc", "NpcModel": "Model", "NpcEvent": "Event"}

    def decode(self, data: bytes, source: str = "<buffer>") -> dict[str, Any]:
        reader = Reader(data, source)
        sections = {"Npc": read_records(reader, _read_npc)}
        sections["NpcModel"] = read_records(reader, _read_model)
        sections["NpcEvent"] = read_records(reader, _read_event)
        if reader.pos != len(data):
            raise FormatError(f"{source}: {len(data) - reader.pos} trailing byte(s)")
        return {"format": self.name, "sections": sections}

    def encode(self, sections: dict[str, Any]) -> bytes:
        writer = Writer()
        write_records(writer, self._items(sections, "Npc"), _write_npc)
        write_records(writer, self._items(sections, "NpcModel"), _write_model)
        write_records(writer, self._items(sections, "NpcEvent"), _write_event)
        return writer.getvalue()


