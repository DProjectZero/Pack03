# What the DMO client expects

Where each table's layout comes from, and which manager reads which file. Only needed when changing a codec.

## How to read them

Every data format is a class with four static methods:

| method | role |
|---|---|
| `XxxToXml(string binPath)` | reads the binary — **this defines the byte layout** |
| `ExportXxxToXml(string xmlPath, ...)` | writes XML — defines field names/order |
| `ImportXxxFromXml(string xmlPath)` | reads XML back |
| `ExportXxxToBinary(string binPath, ...)` | writes the binary |

Watch out for the write path: several `ExportXxxToBinary` methods are *not*
symmetric with their readers (they write a 32-bit value where the reader takes a
16-bit one, or add/omit fields). `binconv` always follows the reader, which is
what reproduces the original files exactly.

`BinToXml.cs` and `BinToXml2.cs` are the WinForms event handlers; they are the
authoritative map of which `.bin` produces which XML documents (and where the
old tool's hardcoded paths point).

## The client source is the real spec

The client's own source tree is the authority for every byte layout (it is not
part of this repository). The parts that define the data formats:

| path | what it gives |
|---|---|
| `LibProj/CsFileTable/*.h`, `*.cpp` | one `CsXxx::sINFO` struct plus a `_LoadBin` / `_LoadFilePack` per `.bin` — the authoritative layout, field types and default values |
| `LibProj/CsFilePack/` | the `.pf` / `.hf` pack format (`FPHeader.h`, `CsFileHash.h`, `FPHeader.cpp` for the name hash) |
| `DProject/_Interface/Game/` | how the loaded data is actually displayed (string usage, indices, guards) |
| `LibProj/CsFileTable/_*Header.h`, `_*Define.h` | shared buffer sizes (`ITEM_NAME_LEN`, `EVENT_MSG_LEN`, …) |

All of those are paths *inside the client tree*; the paragraphs below assume you
have it checked out somewhere and is why the module docstrings in
`binconv/formats/` name the file each layout came from.

How to read a format there:

1. Find the loader: `Select-String -Path LibProj\CsFileTable\*.cpp -Pattern 'Xxx\.bin'`
   gives the `#define XXX_BIN` and the surrounding `_LoadFilePack`, which shows
   the real read order (per field, per struct, or with counts).
2. Read the struct in the matching `.h`. Under `UNICODE`, `TCHAR` is 2 bytes and
   **MSVC alignment padding is part of the file** because the writer uses
   `fwrite( &info, sizeof( sINFO ), 1, fp )`.
3. Compare with `binconv/formats/<format>.py`; a `TCHAR name[N]` member is a
   fixed buffer used as a C string, i.e. `("w", N)` — *not* `ReadZString`,
   which skips NULs instead of stopping at them.

Concrete cases where this changed the port (all now follow the client):

* `Achieve`: `Title` etc. are `TCHAR` buffers used as C strings, so they end
  at the first NUL. The converter's `ReadZString` returned stale buffer contents
  — achievement 1505's title is empty, the converter reported `"ronze Tamer"`
  (the leftover of a longer title, with its first character overwritten by the
  new terminator). `Display2` is the `bool`/`TCHAR` alignment padding byte.
* `Achieve`: the category table is a **recursive tree** (`TCHAR s_szType[32]`,
  `int childCount`, children…), not 18 fixed records.
* `Buff`: `BuffClass` is a `USHORT` followed by 2 bytes of padding, and
  `ConditionLv` is preceded by 1 byte of padding. The converter read the
  padding as part of the values (`ConditionLv` 154 instead of 0) and invented
  a trailing `u` field.
* `Quest`, `Ride`, `ItemList`: names/comments are `TCHAR` buffers, read as fixed
  buffers now.
* `WorldMap` (`CsWorldMap::sINFO`): `Name`/`Comment` are `TCHAR[48]` /
  `TCHAR[256]` C strings and `WorldType` is a `BYTE` followed by alignment
  padding — the converter read it as a `USHORT` and its `ReadZString` returned
  stale text for 3 of the 123 comments. The layout is the same size either way,
  so only the values differ.
* `MapList` (`CsMapList::sINFO`, `CsMapListMng::_LoadBin`): order and types match
  the converter's reader exactly (the three ASCII fields are `std::string`, i.e.
  `int32` length + bytes; the descriptions are `std::wstring`). The two `MapID`s
  are `DWORD`. Watch out when comparing sources: the **excel** path
  (`MapListMng.cpp:241-242`) swaps `s_szMapDiscript` and `s_szMapDiscript_Eng`,
  the bin path does not.
* `ExtraExchange` (`CsExtraEvolutionMng`, ``ExtraEvolutionTable.cpp`` -- the
  loader is *not* named after the format): the converter's *writer* drops
  `MaterialCount`, which is why nothing recompiled with the old tool loads again;
  the client's `SaveBin` writes it, and so does this port. The two fields the
  converter called `Unknow`/`Unknow1` are `USHORT MaterialType`/`WayType`,
  and the JSON uses those names (`--alias` keeps the XML comparison working).

## Which loader reads which bin

The loader class is **not** always named after the file (`ExtraExchange.bin` is
read by `CsExtraEvolutionMng`). Grep for the `#define …_BIN "…bin"` string when
looking for the reader of a format:

| bin | loader (`LibProj/CsFileTable/`) |
|---|---|
| `Achieve.bin` | `AchieveMng` |
| `AddExp.bin` | `AddExp` |
| `BattleTable.bin` | `BattleTableMng` |
| `Buff.bin` | `BuffMng` |
| `CashShop.bin` | `CashShopMng` |
| `CharCreateTable.bin` | `CharacterCreateListInfo` |
| `Cuid.bin` | `CUIDMng` |
| `Data_Exchange.bin` | `DigimonMng` |
| `Digimon_Book.bin`, `Digimon_List.bin`, `New_Element.bin`, `Passive_Ability.bin`, `Ride.bin` | `DigimonMng` |
| `DigimonEvo.bin` | `CDigimonEvolution` |
| `DigimonParcel.bin` | `DigimonParcelManager` |
| `DMBase.bin` | `BaseMng` |
| `Event.bin` | `Event` |
| `EffectList.bin` | `EffectMng` → `CsEffectMng` (literal path, no define) |
| `ExtraExchange.bin` | `ExtraEvolutionTable` → `CsExtraEvolutionMng` |
| `Gotcha.bin` | `CsGotchaMng` |
| `InfiniteWar.bin` | `InfiniteWarManager` |
| `ItemList.bin` | `ItemMng` |
| `MapCharLight.bin` | `MapCharLightMng` |
| `MapList.bin` | `MapListMng` |
| `MapMonsterList.bin` | `MapMonsterMng` (`#define MAP_LIST_MONSTER`) |
| `MapNpc.bin` | `MapNpcMng` |
| `MapObject.bin` | `MapObjectMng` |
| `MapPortal.bin` | `MapPortalMng` |
| `MapRegion.bin` | `MapRegionMng` |
| `MasterCard.bin` | `Master_CardMng` |
| `Monster.bin` | `MonsterMng` |
| `Nature.bin` | `NatureMng` |
| `Npc.bin` | `NpcMng` |
| `Quest.bin` | `QuestMng` |
| `Reward.bin` | `RewardMng` |
| `Scene.bin` | `SceneDataMng` |
| `ServerTransfer.bin` | `ServerRelocateTable` |
| `Skill.bin` | `SkillMng` |
| `Tactics.bin` | `TacticsMng` |
| `TimeCharge.bin` | `TimeChargeMng` → `CsTimeChargeMng` (literal path, no define) |
| `Talk.bin` | `TalkMng` |
| `TamerList.bin` | `TamerMng` |
| `Tutorial.bin` | `TalkMng_Tutorial` |
| `UIText.bin` | `UI_Text` |
| `Weather.bin` | `WeatherMng` |
| `WorldMap.bin` | `WorldMapMng` |

Six shipped bins have **no** `#define …_BIN` name. Three of them are still loaded
by the client, under a literal path or a differently named define:

| bin | how it is loaded |
|---|---|
| `EffectList.bin` | `CsEffectMng` (`EffectMng.cpp` — `SaveBin` 72, `_LoadBin` 91, `_LoadFilePack` 122) with a **literal** `"EffectList.bin"` |
| `MapMonsterList.bin` | `CsMapMonsterMng` (`MapMonsterMng.cpp:176`, `#define MAP_LIST_MONSTER`, three call sites 180/232/279) |
| `TimeCharge.bin` | `CsTimeChargeMng` (`TimeChargeMng.cpp` — literal `"TimeCharge.bin"` at 144/250/351) |

The remaining three are **not referenced anywhere in this client snapshot** — a
recursive search of `LibProj/CsFileTable`, `LibProj/CsDM`,
`LibProj/TableManager` and `DProject` finds no occurrence of
`NewTutorial`, `Spirit_NPC` or `SvLineUp`. The old C# converter does not read them
either (no file under `the recovered C# sources/` mentions the names) and neither does the
server, so nothing arbitrates their layout.

Two of them still resolved from the bytes alone — `Spirit_NPC` (42 fixed 88-byte
records behind an `int32` count) and `SvLineUp` (5 × 72 B: slot, order, `wchar[32]`
boss name) tile their files exactly, so they are ported with inferred field names.
`NewTutorial` has variable-length records (9 steps, `Tutorial\Eng\*.tga` paths) and
no source to pin the boundaries down, so it stays unsupported: the retail file is
shipped verbatim as `blob/NewTutorial.bin` (the only non-reverse-engineered binary
in this repo) and copied into every build, so the rebuilt pack still holds all 49
files. See the *Packing* section of the top-level `README.md`, and
[`newtutorial.md`](newtutorial.md) for the Ghidra pass over an unpacked client
(the PDB has no `NewTutorial` symbol either, so the verdict stands) and the
partial record layout recovered from the bytes.

Since a loader can hide behind a literal path, search for the **file name**
(`'EffectList.bin'`), not just for `#define …_BIN`, when looking for a reader.

## Cross-checking against the server source (`the DMO server`)

The emulator at `../the DMO server` (DigitalWorldOnline) re-reads the same files and is
useful as a *second opinion* on a layout — but never as the primary spec: its
readers skip whatever the server does not need, and some of their comments are
stale. Three artifacts matter:

| path | what it is |
|---|---|
| `src/Source/Application/DigitalWorldOnline.Application.GameAssets/Bins/*BinLoader.cs` | 16 hand-written parsers (`Achieve`, `Buff`, `CashShop`, `CharCreateTable`, `DigimonEvo`, `Digimon_List`, `DMBase`, `Event`, `ItemList`, `Map` (MapList/MapPortal/MapRegion/MapMonsterList), `Monster`, `Nature`, `Skill`). Each docstring names the client function it mirrors (`SkillMng::SaveBin`, `NatureMng::_SaveBinBaseElement`, …) and quotes the record sizes — a fast index into the client files |
| `src/Tools/NPCEditor/Util/Npc.json`, `MapNpc.json` | **MISDMO/Arves100 v487 schemas** for the generic `binerp` bin↔xml tool. `Npc.json` models the type-dependent structs (`<Struct> if Type == NpcType.Portal`, store lists, `SpecialEvent`, dynamic `ExtraInfo`) that the client's 24 `fread`s obscure |
* `Cuid.bin` and `Data_Exchange.bin` store their names in **cp949** (EUC-KR), not
  ASCII. Decoding them as ASCII replaces the Korean bytes with `?` and the
  re-encode silently corrupts the file (`Data_Exchange` shows up as a one-byte
  diff per character). Use `("c", "cp949", n)`.
* `InfiniteWar.bin` and `MasterCard.bin` are written through `CmUtil::CmBinSave`,
  whose string helpers are *length prefixed and unterminated*: `int32` character
  count + UTF-16LE for `std::wstring`, `int32` byte count + raw bytes for
  `std::string`.
* `CsMaster_CardLeader::sINFO` is **44** bytes but `CsMaster_CardLeaderAbility::sINFO`
  is only **40** (`USHORT ID`, 2 bytes of padding, 3 × 12-byte `sTerms`).
  Guessing 44 for both drifts one byte per ability row, and the next section's
  count lands on garbage (it read 54 111 187 in our first attempt).
* `Tactics.bin` is built with `DATA_MAX` = 2 (`DATA_LV1` + `DATA_LV2`), so
  `CsTactics::sINFO` is 20 bytes behind the 4-byte key: `int DigimonID`,
  `int ReqItemS_Type[2]`, `USHORT ReqItemCount[2]`, `BYTE LimitLevel[2]`,
  `BYTE ViewWarning[2]`. Do not use `DATA_MAX_GRADE` (1) — that macro is
  redefined inside `TacticsMng.cpp` for the Excel loader only.
* `Scene.bin` has a third section that is easy to miss: after the
  `sSceneInfo` + `sData` loop, `CsSceneDataMng::_LoadBin` reads another count and
  `sTargetData` (80 bytes) rows.
* `Gotcha.bin`'s mystery-coin table is **empty**, so the shipped bytes cannot tell
  the 12-byte layout (`EGG_PREFERMENT` off) from the 20-byte one (flag on); the
  codec documents both and writes the 12-byte form.
* `Digimon_Book.bin` composition rows keep two bytes of heap garbage:
  `SaveBin` never copies `Evolslot` into the record it writes. They are kept as
  `Padding` so the JSON stays byte exact.
* `Passive_Ability.bin` writes one count per `ePASSIVE_TYPE`; `PA_START` is 1 and
  `PA_MAX` is 2, so the whole file is a single `int32 0`. Its loader also proves
  the enum did not grow in this build.
* `TamerList.bin`'s 1 500-byte `CsTamer::sINFO` stride proves the build defines
  `COSTUME_GENDER` (the `Gender[64]` member) — the header alone is ambiguous.
* `MapCharLight.bin` writes an `int32 Type` selector *before* each light struct,
  and `sINFO_BASE` carries its own `Type`; keep both.

| `BIN_PHASE_TRACKER.md` | their roadmap only (Npc next, then Quest/MasterCard) — no layouts |

`src/Tools/BinXmlConverter` and `BinXmlConverteer` are the *same* old WinForms
converter already recovered into `the recovered C# sources/`, and `DataImporter` reads
xml/csv, not bins. Nothing there covers `Talk`, `Tactics`, `Gotcha`,
`MasterCard`, `Digimon_Book`, `Passive_Ability`, `Data_Exchange`, `Cuid`,
`Reward`, `Scene`, `Tutorial`, `TamerList`, `Weather`, `AddExp`, `MapCharLight`
or `InfiniteWar`.

Every spec taken from there was re-validated against the shipped bytes before a
codec was written (walk the layout in Python and require the cursor to land
exactly on EOF):

| bin | structure | result |
|---|---|---|
| `Nature.bin` | 11 × 24 B matrix + `[i32 cmpType][i32 bases][i32 base][i32 points][{i32,i32}…]` | remainder 0 |
| `MapRegion.bin` | 604 B / 16 B / 52 B records in three counted group sections | 88/435, 8/21, 10/65, remainder 0 |
| `MapMonsterList.bin` | 1 043 file tables → map buckets → 48 B rows | 93 maps, 3 517 rows, remainder 0 |
| `Skill.bin` | 736 B / 36 B / 64 B sections | 5 322/64/93 = 3 925 260 B (file size) |
| `Monster.bin` | 396 B / 8 B / 144 B / 12 B sections | 2 138/100/2 044/31 = 1 142 172 B, remainder 0 |
| `Digimon_List.bin` | 572 B records | 4 + 634 × 572 = 362 652 B |
| `DigimonEvo.bin` | 8 B head + n × 328 B objects, then 5 × 50 B | 140 trees, 639 objects, remainder 254 B = 4 + 5 × 50 |
| `Npc.bin` | 1 176 B head + conditional blocks + models/events | 1 861/609/1, remainder 0 |
| `New_Element.bin` | 148 B attribute rows + 152 B nature rows | 4 + 5 × 148 + 4 + 11 × 152 = 2 420 B (file size) |

Two corrections that came out of this:

* **`Nature.bin` is not blocked.** `Nature.h:21` really is
  `struct sINFO { USHORT ID; short Element[MaxCount]; }` (24 B), written by
  `SaveBin` before `_SaveBinBaseElement`. The earlier "the loader reads int32 but
  the file is int16" conflict came from treating `_LoadBinBaseElement` — which
  only handles the attribute table — as the whole reader.
* **`New_Element.bin` is not a nature table**, although `NatureBinLoader`'s
  docstring claims "identical byte layout". It is the element *UI* table
  (`DigimonStatus\Element\*.tga` icon paths and positions), written by
  `DigimonMng.cpp:1731-1762` under `#define NEW_ELEMENT_TABLE_BIN` (`ElementUI.h`:
  `CsAttributeTypeUI` 148 B, `CsNatureTypeUI` 152 B). The define hides the name —
  searching for `#define …_BIN` only works if you also match the string literal.

Reproducing the check needs nothing but the standard library, e.g. for `Npc.bin`:

```python
data = open("../the retail install/Npc.bin", "rb").read()   # walk 1 176 B heads,
                                                      # Portal/Store/Special/ExtraInfo,
                                                      # then models (140) and events (60)
```

The ported codecs in `binconv/formats/` are the same walk, so
`python binconv.py decompile --only Npc` re-runs it and fails loudly if the cursor
does not land on EOF.
