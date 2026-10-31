# Development helpers

Scripts that check a build against the retail data, or against XML produced by the
original converter. They are developers' tools: `binconv.py` does not need them.

| script | purpose |
|---|---|
| `tools/verify_roundtrip.py` | check decode → encode against a folder of retail bins |
| `tools/verify_pack.py` | compare a rebuilt `Pack03.pf`/`.hf` with a retail pair, entry by entry |
| `tools/compare_xml.py` | diff a JSON section against XML the original tool wrote (`--nested`, `--ignore`, `--alias`), or run every documented check with `--format all` |
| `tools/check_codes.py` | print the exit code of each documented check (triage helper) |
| `tools/verify_sections.py` | run that diff over a whole XML folder |
| `tools/verify_cashshop.py` | run that diff over the nested `CashShop` XML documents |

Requirements: Python 3.10+ (tested with 3.13), standard library only.

## Round-trip and pack checks

```powershell
python tools/verify_roundtrip.py <retail-data-dir>        # every supported file
python tools/verify_roundtrip.py <retail-data-dir>\ItemList.bin
python tools/verify_pack.py bin_out <retail-data-dir>     # rebuilt pack vs retail
```

`verify_roundtrip` prints one line per file: `OK` (byte identical), `OK (N padding
byte(s) normalised)` or a mismatch; see [validation](validation.md) for what the
padding is. `verify_pack` compares the pack structure (paths, hashes, sizes,
offsets, order) and then the payloads — it is the tool that proves a rebuilt pair
is a drop-in replacement.

## XML checks

The XML the original converter wrote is *not* part of this repository. If you have
a dump of it, point the checks at it:

```powershell
python tools/compare_xml.py --format all --xml-dir <dump-dir> --ref-dir <generated-dir>
python tools/compare_xml.py --format ItemList --xml-dir <dump-dir>
python tools/compare_xml.py json/MapObject <dump-dir>/MapObject.xml `
    --section MapObject --nested --ignore Size,FactorSize
```

`--xml-dir` holds the documents the tool wrote (`Achieve.xml`, `ItemList/…`), and
`--ref-dir` holds XML generated later from the recovered sources (`DMBase/…`).
A check whose tree you did not supply is reported as `SKIP`, never as a failure,
so the corpus can be checked piecemeal.

The recipes live in **one place** — the `CHECKS` table in `tools/compare_xml.py` —
and each entry names the document, the JSON section, and only the *documented*
divergences:

* `alias={"_pad0": "unk"}` — the client named a field the converter could not;
  `--alias OLD=NEW` does the same on the command line,
* `ignore={"Ht", "Unknow2"}` — padding the old exporter split into several elements,
* `known="…"` — a divergence recorded in [the converter notes](legacy-converter.md)
  instead of being counted as a failure.

`--ignore` otherwise only names fields *derived* from the JSON side (the count
values the exporter printed next to the array that replaces them). Strings are
compared after newline normalisation; a value counts as different only when it
differs beyond characters XML cannot carry (C0 control codes) or trailing
whitespace.

`CashShop` has no entry in `CHECKS` on purpose: its 51 reference documents are a
flattening of the six JSON sections (`AvatarInfo` + `Bottom/…`), so
`tools/verify_cashshop.py` matches those by path instead of by section name.
