# The one unsupported table: `NewTutorial.bin`

`NewTutorial.bin` (4 084 B, name hash `0xabe373b9`) is the only file in
`Pack03.hf` without a codec. This page records what is known about it, so the
next person does not repeat the search.

## What was tried

The retail `GDMO.exe` is Themida-packed with XIGNCODE, so an unpacked client was
never available. A **clean source build** now is —
`DProject_R_ENG.exe` (11 024 384 B) with its own 122 MB PDB, built from the
client source tree, no anti-cheat — analysed with Ghidra 12.2 headless.

Two failures are worth recording:

* The default headless heap (2 GB) is not enough. Auto-analysis dies with
  `java.lang.OutOfMemoryError: Java heap space` inside `AddressTableAnalyzer`
  after the PDB stage. Set `GHIDRA_HEADLESS_MAXMEM=8G` before calling
  `analyzeHeadless.bat`.
* Give the PDB to the importer by keeping it next to the EXE; the PDB analyzer
  then resolves 344 581 symbols, including every class in `TutorialUITraceData.h`.

## Result: the clean build has no reader either

| check | result |
|---|---|
| `NewTutorial` anywhere in the EXE (ASCII or UTF-16) | **0 hits** |
| `NewTutorial` anywhere in the 122 MB PDB | **0 hits** |
| `CsTalk_Tutorial`, `CTutorialContents`, `sTraceData`, `cIndicatorInfos` in the PDB | 238 / 4 568 / 71 / 119 hits |
| enumerating every `.bin` literal in the EXE | 49 names — **none** is `NewTutorial.bin` |
| the client source tree (`LibProj`, `DProject`) | never mentions the name |
| the server source tree | never mentions the name |

The tutorial content that *does* load comes from text assets, not from a table:

| asset | where it is named |
|---|---|
| `Data\Interface\Tutorial\TutorialIndicator.xml` | `cIndicatorInfos::LoadTutorialScript` (`11.Tutorial/TutorialIndicator.cpp:474`) — via `CsFPS::CsFPSystem::IsExistOnlyPack(0, …)` / `Allocate_GetFileData(0, …)`, i.e. from **another pack**, by explicit path |
| `Data\Interface\Tutorial\TutorialPlayerData.Json` | tutorial progress |
| `Data\NP\Media\Tutorial_Open.wmv`, `Tutorial_End.wmv` | tutorial movies |

Note that `Tutorial.bin` **is** a different, real table (`CsTalkMng::_LoadBin_Tutorial`,
`#define TUTORIAL_BIN "Tutorial.bin"`, `int32` count + `CsTalk_Tutorial::sINFO`
records of `TCHAR[256]`). It is not this file: `4 084 = 4 + n · 512` has no
integer solution, and the payload is paths, not talk text.

## What the bytes actually hold

48 strings, and they describe tutorial steps:

| count | string |
|---|---|
| 40 | `Tutorial\Eng\Tutorial_<chapter>_<page>.tga`, chapters 0–8 |
| 4 | `ZoneMap` (a window name) |
| 2 | `Data\Effect\_Quest\Tutorial1_Area.nif` |
| 2 | `7994;57:` — stale heap text behind a NUL, not a field |

The header is `int32 9` (the nine steps the old note mentions), then `1`,
`90084`, `1459`. Step ids run `1459…1467`, quest ids `90018` and `90084…90089`.

Every image reference starts a record, and every record breaks at `+0x40` — the
first field is `char szImage[0x40]`. The tails fall into three shapes, which is
why the earlier note called these records variable-length (no uniform record size
divides the file):

| records | size | tail |
|---|---|---|
| 9 | 0x50 | 4 words |
| 24 | 0x60 | 8 words — two of them are the **next quest id / next step** pair |
| 6 | 0xA0 | 24 words: a second `char[0x40]` at `+0x4C` (`ZoneMap` or the effect path), and at `+0x48/+0x4C/+0x50` an `x`, `y` and a `float` radius (`300.0` in both records that carry one) |
| 1 | 0x54 | a 0x50 record plus the file's trailing `0x00000050` |

That field set is `sTraceData` / `cTraceBase` from
`DProject/_Interface/11.Tutorial/TutorialUITraceData.h` (tooltip image, target
window, effect list, next quest/step/trace index, portal, video). In other
words the file is the **compiled indicator script** — the retail form of
`TutorialIndicator.xml` — written by the retail exporter.

## Why it is still a blob

The tails contain values that are not ids:

* `0x4BCB9C`, `0x4BCBAC`, `0x4BCBB4`, `0x4BCBBC`, `0x4BCBD4` follow
  **`0x4BCB94 + 8 · k`**, where `k` is the count word next to them (verified for
  k = 1, 3, 4, 5, 8) — the signature of a pointer field that was dumped as-is
  instead of being serialised, each step of `k` moving it 8 bytes.
* Two records carry `7994;57:` where `7994` and `5772` also appear as `x`/`y`
  one word later — text left behind in a reused buffer.

A file that carries addresses from one binary and text from a previous write
cannot be regenerated deterministically, so no codec would be byte-exact. It is
committed as `blob/NewTutorial.bin` and copied verbatim; `binconv/blobs.py` pins
the size.

## What would finish the job

1. The retail `Data/Interface/Tutorial/TutorialIndicator.xml` — it is the schema
   behind these records and would name the tail words. A retail v487 `GDMO.exe`
   or PDB would answer the other half (whether the client re-derives the pointer
   fields), but it has to be unpacked first.
2. Then a codec can go in `binconv/formats/newtutorial.py`, the `BLOBS` entry
   and `blob/NewTutorial.bin` can be deleted — nothing else has to change.

## Ghidra is exhausted for this file

Nothing more can come out of static analysis on the binaries that exist: the
retail `GDMO.exe` (v487) is Themida-packed with XIGNCODE, and the clean source
build predates the table — no code, no symbol and no literal in it mentions
`NewTutorial`. The missing ingredient is *data* (the retail XML), not a binary.

If the import has to be repeated for another question, only two settings matter —
the heap and the PDB sitting next to the EXE:

```bat
set GHIDRA_HEADLESS_MAXMEM=8G
C:\ghidra\support\analyzeHeadless.bat C:\ghidra_projects Pack03 ^
  -import "<client-source>\Release\GSP\DProject_R_ENG.exe" -overwrite ^
  -analysisTimeoutPerFile 7200
```

Then use Ghidra's built-in searches (*Search → For Strings* for `NewTutorial` and
`.bin`, *Search → Program Text* for `TutorialIndicator`). The first comes back
empty, which is the result; no helper script or saved project is kept in the repo.
