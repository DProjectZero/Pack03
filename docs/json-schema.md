# JSON layout

How a compiled table is stored as JSON: one folder per format, one file per section.

## Layout

**One JSON file per section**, in a folder named after the input binary — the
same split as the original tool's XML tree:

```
bin/ItemList.bin      ->  json/ItemList/ItemList.json
                          json/ItemList/ItemTap.json
                          json/ItemList/ItemAcessorys.json
                          ... (16 sections)
bin/Quest.bin         ->  json/Quest/Quest.json
bin/Event.bin         ->  json/Event/AttendenceTime.json
                          json/Event/Event.json
                          json/Event/MensalEvent.json
                          json/Event/MonthlyEvent.json
                          json/Event/TimeEvent.json
                          json/Event/Event100Days.json
bin/DMBase.bin        ->  json/DMBase/TamerBaseInfo.json
                          json/DMBase/DigimonBaseInfo.json
                          ... (12 sections)
bin/CashShop.bin      ->  json/CashShop/Main.json
                          json/CashShop/TamerInfo.json
                          json/CashShop/DigimonInfo.json
                          json/CashShop/AvatarInfo.json
                          json/CashShop/PackageInfo.json
                          json/CashShop/WebData.json
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
  `conditions`, `EventItems`, `MensalItems`, …).
* A section may also be a plain list of scalars (e.g. `Quest.Event`).
