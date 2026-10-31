# JSON field names

The JSON in `json/` is the tracked source of truth, so field names are part of the
project's API.  This note records the policy and every deliberate departure from it.

## Policy (P2: curated, clarity first)

1. **Layout authority is the client source.**  Names never change what is read or
   written; every rename is layout-neutral and is verified by the full sweep
   (`48 ok, 0 failed`) plus a byte-identical recompile.
2. **One key per field, chosen for clarity.**  Hungarian prefixes are dropped
   because JSON already shows the value: `s_szComment` → `Comment`,
   `s_nBuffClass` → `BuffClass`, `dwDigimonSkillCode` → `DigimonSkillCode`.
   Padding stays `_pad0`, `_pad1`, … (it *is* the clearest name for bytes that
   exist only because of struct alignment, and the numbered form keeps the
   byte-exact ordering obvious).
3. **The old C# converter's names are kept where they are better than the
   client's**, e.g. `dwNeedMoney` → `NeedMoney` reads better than the client's
   `s_dwNeedsMoney` stem, `dwNeedsMoney`-style abbreviations are expanded, and
   `Price` (ExtraExchange) stays because it is what the field means.
4. **Names the C# converter invented are dropped** (`Unknow`, `Unknow1`,
   `ID_Maybe`): the client member wins — `usMaterialType`, `usWayType`, `ID`.
5. **Obvious client typos are corrected** while the stem is otherwise untouched:
   `Valocity` → `Velocity`, `CritcalRate` → `CriticalRate`,
   `Enchent` → `Enchant`, `FixedFigyre` → `FixedFigure`.
6. **Numbered arrays keep their number** (`Icon1..6`, `Abil1..4`, `Quest1..3`,
   `EffectFactor0..2`): the index is the meaning.
7. **Two fields in the same record may not share a key.**  The client has a few
   duplicate stems; those were disambiguated by hand:
   * `ItemList`: `s_bUseTimeType` → `IsUseTimeType` (bool) next to
     `s_btUseTimeType` → `UseTimeType` (BYTE).
   * `MapPortal`: two `int` members in one 60-byte portal record —
     `s_dwPortalType` → `PortalType`, `s_ePortalType` → `PortalTypeExtra`.
   Both were caught by the sweep (3 and 1 differing bytes) and re-verified.

## Deliberately *not* renamed

* `_pad0`, `_pad1`, … — struct padding (see above).
* Fields whose client stem is already opaque (`unk2`, `unk3`, `unks`, `unkss` in
  `ItemList`) stay as `blob` fields; inventing a meaning would be worse than
  admitting we do not know it.
* `Spirit_NPC` and `SvLineUp` have **no reader anywhere** (client, server or the
  old converter), so their names are inferred from the bytes and documented as
  such in the module docstrings: `Type/SubType/ID/ItemCount/ItemCode0-2/
  Reserved0-6/EvolveCode0-1/ReservedLow0-2/Flag1-4`, and
  `Slot/Order/Name` for the five Demon Lords.

## Where to look

* `binconv/formats/<format>.py` — the field tables are the authority.
* `tools/compare_xml.py` — `Check.alias` maps a JSON key to the *XML* element name
  the old converter emitted, so the XML diffs keep working after a rename.
* `docs/client-notes.md` — which client header each layout came from.
