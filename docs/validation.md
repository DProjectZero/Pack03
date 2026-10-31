# Validation

How the converter is checked against the retail data, and what is exact versus merely equivalent.

## What is checked

Two independent checks are used for every format:

1. **Ground truth** — decompiled JSON is compared value by value with the XML
   the old tool produced (`tools/compare_xml.py`, `tools/verify_sections.py`;
   `--nested` also descends into item tables, `--ignore` skips fields the old
   reader got wrong).
2. **Round-trip** — `decode` then `encode` must reproduce the original file
   (`tools/verify_roundtrip.py`). Recompiling `json/Quest/` yields a
   byte-identical `Quest.bin`.

`ItemList.bin` is byte-identical except for **790 bytes out of 24 005 453**: the
original file contains leftover heap pointers *after* the NUL terminator of some
fixed-size strings. The reader discards them, so they cannot be represented in
JSON; the recompiled file is still valid and the decoder reports how many bytes
were normalised.

`Event.bin` reproduces **four of its six sections byte for byte**
(`AttendenceTime`, `Event`, `TimeEvent`, `Event100Days`). The 708 remaining
bytes sit behind the NUL terminator of the `MensalEvent` name/date buffers and
of the `MonthlyEvent` message buffer, where the original file keeps
uninitialised memory (a heap string like `c90.crt_1fc8…` and UTF-16 garbage).

`DMBase.bin` reproduces **eleven of its twelve sections byte for byte**; the
1 134 differing bytes are all inside the 27 `Store` item file names, whose
128-byte buffers keep leftover heap text (`erties="Excel 12.0 M…`) after the
`Base\0` terminator.

`DMBase` has no XML in the dump produced by the original tool, so its ground truth
came from running that tool's own exporter over `DMBase.bin` and comparing the
result document by document (`--ref-dir` in [the helper scripts](tools.md)).

`CashShop.bin` round-trips **byte for byte** (5 165 814 bytes) and all **51**
documents the exporter wrote for it match the JSON
(`tools/verify_cashshop.py`, which maps every `Main/`, `TamerInfo1/Expansion/`,
… file onto the matching record). That 51-document tree is the `CashShop` ground
truth, produced the same way.

`UIText.bin`, `MapNpc.bin`, `MapPortal.bin`, `MapObject.bin`, `Buff.bin` and
`Achieve.bin` are byte identical apart from the stale bytes *behind* the string
terminators (`Ride` 41 182, `Buff` 70 370, `Achieve` 117 978, …): the game's own
writers never clear those buffers, `binconv` zero fills them, so `decompile`
reports them as *padding normalised* rather than `OK`.

`Achieve.bin` and `Buff.bin` intentionally differ from the old XML in a few
fields, because the old converter misread them (see the bug list below). For
`Achieve` that is 67 of 1 008 text values (the client shows an **empty** title
for those achievements; the converter showed the leftover `"ronze Tamer"`), for
`Buff` it is `ConditionLv` on every record (154 → 0 …).

`MapList.bin` (22 734 bytes, 113 maps) and `ExtraExchange.bin` (2 372 bytes,
2 npcs) round-trip **byte for byte** and match their XML completely.
`WorldMap.bin` reproduces both sections apart from 15 611 stale bytes behind the
`TCHAR` terminators, and 3 of its 123 comments differ from the old XML for the
same reason as `Achieve` (the client reads an empty comment, the converter
returned the leftover text of a previous revision).

The full sweep over `the retail install` is **48 of 49** bins: **23 exact and 25
padding-only, 0 mismatches**. The remaining file is `NewTutorial.bin`, which has
no reader anywhere and is shipped as a blob (see
[the one shipped blob](#the-one-shipped-blob)). Of the nine
formats added before these, `Nature`,
`MapMonsterList` and `DigimonEvo` are byte identical; the others only normalise
leftovers behind the string terminators (`Skill` 1 074 836, `Monster` 288 164,
`Digimon_List` 97 234, `MapRegion` 96 697, `Npc` 3 445, `New_Element` 1 046 bytes
— `Npc` and `New_Element` are the cleanest because most of their text buffers are
zeroed). Of the fifteen added last, `Passive_Ability`, `Weather`, `MapCharLight`
and `InfiniteWar` are byte identical and the rest normalise padding only
(`Reward` 1 149 434, `Scene` 377 068, `Tactics` 54 538, `Cuid` 51 560,
`AddExp` 6 936, `Digimon_Book` 5 657, `TamerList` 6 127, `Tutorial` 5 277,
`MasterCard` 4 576, `Gotcha` 3 977, `Data_Exchange` 918 bytes). Of the three added
last, `Spirit_NPC` and `SvLineUp` are byte identical and `Talk` only normalises the
padding behind its strings (207 377 bytes over 1 223 rows).
`Npc`'s 1 176-byte `CsNpc::sINFO` is followed by type-dependent blocks; `compile`
re-derives them from `Type` (`NT_PORTAL`, the six shop-like types,
`NT_SPECIAL_EVENT`) and the `ExtraInfo` list, so a JSON edit cannot desynchronise
the stream — the same guard the client's `NpcMng` has.

`decompile --overwrite` also deletes section files that a previous run produced
but the current format no longer has (it prints `removed N stale file(s)`), so a
shrinking section list cannot leave a stale document behind for `compile`.

## Ground truth from the original tool

The XML dump only holds the documents the original tool was actually run on. For the
formats it was not, the ground truth was produced by compiling that tool's own
exporter and letting it write the documents — nothing was re-implemented, so those
files were valid ground truth for `tools/compare_xml.py`, `tools/verify_sections.py`
and `tools/verify_cashshop.py`.

Neither the tool nor its output is part of this repository. If you have such a dump,
point the helpers at it with `--xml-dir` / `--ref-dir`; without one, the same
guarantees come from the round-trip and pack checks above, which use your own retail
data instead.

