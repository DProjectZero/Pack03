# Pack03 — DMO v487 binary table converter

Python replacement for the old WinForms `BinXmlConverter` tool.
It converts the game's binary data tables (`.bin`/`.dat`) to JSON and back, without a UI and without clicking one button per file.

```powershell
python binconv.py decompile     # bin/*.bin   -> json/<Format>/<Section>.json
python binconv.py compile       # json/<Format>/*.json -> bin_out/*.bin
```

## Where the format knowledge comes from

`PROGRAM/BinXmlConverter.pdb` is a *portable PDB with embedded sources*: the C#
compiler stored all 36 original source files compressed inside it. They were
recovered verbatim (no decompiler needed) into `reference/csharp/` by

```powershell
python tools/extract_pdb_sources.py
```

Those files are the specification for every codec in `binconv/formats/`: the
`XxxToXml` methods define the byte layout (read order and field types) and the
`ExportXxxToXml` methods define the element order used for the JSON keys.

## Usage

```powershell
python binconv.py decompile --src PROGRAM/DATA --out json        # convert the original data
python binconv.py decompile --only ItemList --overwrite
python binconv.py compile   --src json --out bin_out --overwrite
python binconv.py list-formats
```

| option | meaning |
|---|---|
| `--src` | input folder (searched recursively). Defaults: `bin` (one bin per format) / `json` (one folder per format) |
| `--out` | output folder. Defaults: `json` / `bin_out` |
| `--only` | comma separated format names, e.g. `--only Buff,Ride` |
| `--compact` | single line JSON instead of the default tab indented output |
| `--overwrite` | replace existing output files |
| `--no-recursive` | decompile only: do not descend into sub folders of `--src` |

Every file is reported as `OK`, `WARN`, `SKIP` (unsupported format) or `FAIL`
(with the reason). Decompiling also **verifies itself**: the document is
re-encoded in memory and compared with the input.

## Folder layout

| path | contents |
|---|---|
| `bin/` | input binaries (git-ignored); the shipped data lives in `PROGRAM/DATA` |
| `json/<Format>/` | decompiled tables, one file per section — **this is the tracked source of truth** |
| `bin_out/` | recompiled binaries (git-ignored) |
| `binconv/` | the converter (`binary.py`, `fields.py`, `codec.py`, `formats/`) |
| `reference/csharp/` | the recovered original C# sources |
| `tools/` | extraction and verification helpers |

## JSON schema

**One JSON file per section**, in a folder named after the input binary — the
same split as the old tool's `PROGRAM/XML` tree:

```
bin/ItemList.bin      ->  json/ItemList/ItemList.json
                          json/ItemList/ItemTap.json
                          json/ItemList/ItemAcessorys.json
                          ... (16 sections)
bin/Quest.bin         ->  json/Quest/Quest.json
```

A section file contains *only* the section value (a list of records, or a list
of scalars), so it diffs cleanly and can be edited on its own. The section name
is the file name; sub folders are used when a section is nested (`Main/X.json`).
Array length replaces the stored record counts.

The output is **human readable by default**: tab indented, one field per line,
UTF-8, LF line endings (`--compact` produces single line JSON instead).

```json
[
	{
		"UniqID": 2,
		"Level": 9,
		"Type": 0,
		"TitleTab": "Digital World_Whole",
		"questItems": [
			{
				"Itemgiven": 20001,
				"ItemgivenType": 1,
				"ItemgivenAmount": 1
			}
		],
		"Event": []
	}
]
```

`compile` reads every `*.json` below a format folder, rebuilds the sections from
the file names and writes `<Format>.bin` (`Model.dat` style outputs are listed by
`list-formats`). Missing section files are an error; unknown ones are reported
and ignored.

Conventions:

* **Scalars** are JSON numbers; signed fields keep their sign (the C# code reads
  e.g. a `short` into an `int`, and that sign extension is preserved).
* **Strings** are stored exactly as the game stores them: trailing NUL padding
  removed, nothing else trimmed (`\r\n` is preserved — XML would normalise it).
* **Raw byte blobs** (unknown/reserved fields) are base64 strings, matching what
  the old tool wrote into its XML.
* **Record counts** are implicit (`len(array)`) and re-emitted on compile.
* **Nested tables** use the field name from the C# code (`index`, `questItems`,
  `conditions`, …).
* A section may also be a plain list of scalars (e.g. `Quest.Event`).

## Supported formats

| format | file | sections | status |
|---|---|---|---|
| `ItemList` | `ItemList.bin` | 16 | verified against the original XML (14 907 records) |
| `Quest` | `Quest.bin` | 1 | verified against the original XML (3 270 records) |

Run `python binconv.py list-formats` for the authoritative list. Formats the old
tool has no reader for (`BattleTable`, `Cuid`, `Reward`, `Scene`, …) are skipped
with a clear message; they can be added later the same way.

## Validation

Two independent checks are used for every format:

1. **Ground truth** — decompiled JSON is compared value by value with the XML
   the old tool produced (`tools/compare_xml.py`, `tools/verify_sections.py`).
2. **Round-trip** — `decode` then `encode` must reproduce the original file
   (`tools/verify_roundtrip.py`). Recompiling `json/Quest/` yields a
   byte-identical `Quest.bin`.

`ItemList.bin` is byte-identical except for **790 bytes out of 24 005 453**: the
original file contains leftover heap pointers *after* the NUL terminator of some
fixed-size strings. The reader discards them, so they cannot be represented in
JSON; the recompiled file is still valid and the decoder reports how many bytes
were normalised.

## Differences from the old tool (bugs found in the original code)

The old program's *writers* are not symmetric with its readers, so some of its
own recompiles are broken. The Python codecs follow the **reader** (the layout
the game actually reads):

* `Buff`: `s_nBuffClass` is read as a `short` but written as a 32-bit `int`.
* `ItemExchange`: the writer emits `ItemExchangeNo` and omits `unk2`, shifting
  every record by four bytes.
* `ItemAcessorys`: the writer emits a record count that the reader does not read,
  and its XML export writes `s_nOptIdx` into the `s_nMin` element — the old XML
  therefore lost the real minimum values (`1, 2, 3, …` instead of `5, 10, 100`).
  The JSON contains the true values read from the binary.
* `AcessorysEnchant`: the XML export writes `Index_Enchant` twice, so the old
  XML never showed `Factor1`; the JSON has it.
* `Quest`: `Immediate`/`ResetQuest` are written to XML but never read from the
  binary (always `0`); they are therefore not part of the JSON schema.
* `ServerItemList.xml` is a *derived view* of `ItemList` (names stripped to
  ASCII), so it is regenerated instead of being stored in JSON
  (`binconv.formats.itemlist.server_view`).

## Development helpers

| script | purpose |
|---|---|
| `tools/extract_pdb_sources.py` | recover the embedded C# sources from the PDB |
| `tools/survey_csharp.py` | print the XML field order of the C# exporters |
| `tools/compare_xml.py` | diff a JSON section against the original XML |
| `tools/verify_sections.py` | run that diff over a whole XML folder |
| `tools/verify_roundtrip.py` | check decode → encode against `PROGRAM/DATA` |

Requirements: Python 3.10+ (tested with 3.13). Standard library only.


