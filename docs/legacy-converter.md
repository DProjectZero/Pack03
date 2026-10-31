# The original converter, and what it got wrong

This page records where the format knowledge came from, and the bugs that were
found and worked around while porting it. Neither the tool nor its sources are part
of this repository; the codecs in `binconv/formats/` are the specification now.

## Where the format knowledge comes from

Most of the byte layouts in this project were first read out of **the game's
original WinForms table converter**, a leaked tool that shipped as
`BinXmlConverter.exe` next to its PDB. That PDB turned out to be a *portable PDB
with embedded sources*: the compiler had stored all 36 source files compressed
inside it, so they could be recovered verbatim, without a decompiler.

Those sources defined, for every table, the read order (which is the byte layout)
and the XML element order (which is where the JSON key order comes from). They
were used as the specification while this port was written and then **removed from
the repository** — they are not ours to redistribute. Nothing in `binconv/`
needs them any more: the codecs are the spec now, and every one of them is checked
against the retail data itself.

Two things survive from that work and are worth knowing:

* the *naming policy* for JSON keys is recorded in [naming](naming.md),
* the *bugs* listed below were found by comparing that tool's output with what the
  DMO client actually reads. They are history, not open issues.

The **DMO client** is the higher authority wherever the two disagree: its managers
`fread` the files at runtime, so they define the real layout. That source is not
part of this repository either; [what the DMO client expects](client-notes.md)
summarises what was learned from it.

## How the recovered sources were organised

One C# file per table (`ItemList.cs`, `Buff.cs`, …), each a static class with four
methods:

| method | role |
|---|---|
| `XxxToXml(string binPath)` | reads the binary — **this defines the byte layout** |
| `ExportXxxToXml(string xmlPath, ...)` | writes XML — defines field names and order |
| `ImportXxxFromXml(string xmlPath)` | reads the XML back |
| `ExportXxxToBinary(string binPath, ...)` | writes the binary |

The write path is *not* symmetric with the read path in several tables (see the
list below), which is why this project follows the reader everywhere.

## Bugs found in the original tool (and worked around here)

The old program's *writers* are not symmetric with its readers, so some of its
own recompiles are broken. The Python codecs follow the **reader** (the layout
the game actually reads):

* `Buff`: `BuffClass` is read as a `short` but written as a 32-bit `int`
  (see the layout bug further down).
* `ItemExchange`: each record is `[ExchangeItem_No int][CsItemExchange::sINFO]`.
  The old reader took that key as the *previous* record's trailing `unk2`, so
  every key was off by one and the **last** one was the `ItemAcessorys` count
  (184); its writer then re-emitted the key plus a stray `ItemExchangeNo`,
  shifting the whole section. JSON now stores `ExchangeItem_No` per record
  (0..82 in the shipped file) and no `unk2`.
* `ItemAcessorys`: the section **does** start with a count (184); the old reader
  assumed a fixed table without one — which only worked because the count had
  been swallowed by the exchange section above. Its XML export also writes
  `OptIdx` into the `Min` element, so the old XML lost the real minimum
  values (`1, 2, 3, …` instead of `5, 10, 100`). The JSON contains the true
  values read from the binary.
* `AcessorysEnchant`: the XML export writes `Index_Enchant` twice, so the old
  XML never showed `Factor1`; the JSON has it.
* `Quest`: `Immediate`/`ResetQuest` are written to XML but never read from the
  binary (always `0`); they are therefore not part of the JSON schema.
* `Event`: `Event.Name` is decoded as **ASCII** by the old reader although the
  field is a 1024 byte UTF-16 buffer, so its XML shows `""` for most events and
  a stray `"C"` for the rest. The JSON holds the real names (`"Come Back Tamer!
  Event Reward"`, `"Congratulations. Tamer level reached 10."`, …); verify with
  `--ignore Name`. The old writer also emitted 512 UTF-16 characters, i.e. the
  full buffer, while ignoring the `AttendenceTime` record count.
* `Event`: `TimeEvent.unknow` is read and thrown away by the old reader; the
  writer then re-emits `0`. JSON keeps it.
* `DMBase`: the writer serialises `jumpbooster.dwMapID`, a field the reader never
  fills (it fills the `JumpMaps` list), so the old tool threw a
  `NullReferenceException` on every jump booster record. JSON keeps the maps the
  reader saw.
* `DMBase`: `PaneltyInfo` is `level, exp, drop` in the client struct; the old
  reader had exp and drop swapped and its XML export swapped them back, hiding
  it. The shipped data holds the same value in both columns, so nothing changes.
* `DMBase`: the old reader merged `Attack`/`HitRate` into one `int32` and
  reported the struct's trailing padding as `Ht`/`Unknow2` (constant 18/12), and
  its `unk` in `CsBaseMapInfo` is padding too. JSON names them `Attack`,
  `HitRate`, `Padding`, `_pad1`.
* `CashShop`: the `CASHINFO` export prints a second set of members the reader
  never fills (`CashName`, `bActive`, `dwProductID`, `szStartTime`, `szEndTime`,
  `packageItems`, `Desc`), so those XML elements are always empty and the real
  product name only appears in the `Name`/`Description` elements. `cashshop_id`
  is copied from the parent group instead of being read. The JSON keeps exactly
  the fields that exist in the file.
* `CashShop`: the writer hardcodes the shop count (`writer.Write(2)` for the
  first shop) and writes `CashShopMainInformation.UnknowItemsTitle` nowhere,
  although the XML export prints it. JSON derives the count from the lists.
* `MapNpc`: the XML export prints `MapID` before `NpcID` although the reader takes
  `NpcID` first; only the element order differs (JSON keeps the read order).
* `MapObject`: the writer emits `Factor` before `FactorCnt` while the
  reader takes the count first, so recompiling with the old tool swapped the two
  values of every object (same byte layout, different meaning). JSON keeps the
  read order.
* `Ride`: the writer pads/truncates the 1024 byte comment with `Array.Resize`,
  which can cut away the terminator; a comment longer than 510 characters
  produces a record whose `ReadZString` runs into the following fields.
* `Buff`: the client struct is `USHORT BuffClass`, 2 bytes of alignment
  padding, then the two `DWORD` skill codes, and `TCHAR EffectFile[64]`,
  1 byte of padding, `USHORT ConditionLv`. The converter read the first
  padding as `unknow`, took `ConditionLv` from the *second* padding byte plus
  the low half of the real value (154/922/410 instead of 0/3/1) and turned the
  last byte into a bogus `u` field. Its writer also emitted four bytes for the
  `int`-typed `BuffClass` and shifted every following record.
* `Achieve`: the reader hardcodes **18** header records (`dcount = 18`, "parte
  sem funçao alguma"); the table is really a recursive tree whose counts are in
  the file, so any other category layout would be mis-parsed.
* `Achieve`: `ReadZString` skips NULs instead of stopping at them, so any string
  buffer that still holds a previous, longer value returns that leftover as
  data. The client reads the same fields as C strings, so `binconv` truncates at
  the first NUL (`("w", N)`); 67 values change. `Display2` is not a field at
  all — it is the `bool`/`TCHAR` alignment padding byte.
* `Buff`, `Quest`, `Ride`, `ItemList`: same string issue — the client declares
  `TCHAR` buffers, the converter used `ReadZString`. `binconv` reads fixed
  buffers for all of them (no values change in the shipped data, but a stale
  buffer would have been reported as content).
* `ExtraExchange`: the client (`CsExtraEvolutionMng::SaveBin`) writes both
  material counts, but the old converter's *writer* dropped `MaterialCount`, so
  recompiling with it desynchronised every record after the first. JSON keeps the
  field and writes it back. The two fields the converter could not name are now
  `MaterialType`/`WayType` (client names) instead of `Unknow`/`Unknow1`;
  compare them with `--alias Unknow=MaterialType --alias Unknow1=WayType`.
* `WorldMap`: the two string buffers are `TCHAR[48]`/`TCHAR[256]` that the client
  uses as C strings; the old reader's `ReadZString` returned the stale text
  behind the NUL for 3 of the 123 comments. JSON follows the client.
* `ItemList`: the accessory table's count is now taken from the list length
  instead of being pinned to 184 (`ItemMaking`/`ItemAcessorys` sizes and the
  option count of 16 are unchanged).
* `ServerItemList.xml` is a *derived view* of `ItemList` (names stripped to
  ASCII), so it is regenerated instead of being stored in JSON
  (`binconv.formats.itemlist.server_view`).
