# Pack03 — DMO v487

> [!NOTE]
> The majority of this repo was written by DeepSeek. I will maintain it, but expect some verbosity.

A decompilation of **Pack03** from DMO v487. No files are required from the user; new tools build `Pack03.pf` / `Pack03.hf` from scratch. All 49 shipped tables are supported: 48 are stored in JSON, and 1 is copied verbatim. This leaves the repo with a **99.9%** complete decompilation.

This tool should also be able to dump other regional packs (Pack04, Pack05 etc), however that is outside the scope of this project.

## What you need

* Python 3.10 or newer (tested with 3.13), standard library only.

## Quickstart

```powershell
python binconv.py            # json/ -> bins -> bin_out/Pack03.pf + Pack03.hf
python binconv.py decompile  # bins -> json/<Format>/<Section>.json
python binconv.py compile    # json/<Format>/*.json -> bin_out/Pack03/Data/Bin/English/*.bin
```

## Usage

```powershell
# from your retail pack to JSON, then back to a pack
python binconv.py pack-extract --src <retail-data> --out bin --pack-name Pack03
python binconv.py decompile --src bin --out json
python binconv.py                                   # json -> bins -> pack

# rebuild one table only
python binconv.py decompile --only ItemList --overwrite
python binconv.py compile --only ItemList

# ship a minimal mod: patch your retail pack instead of rebuilding it
python binconv.py pack --src <changed-bins> --base <retail-data> --out dist
```

| command | meaning |
|---|---|
| *(none)* / `build` | compile every format, copy the blobs, write `<out>/<pack-name>.pf` + `.hf` |
| `compile` | `json/<Format>/*.json` → `<out>/[tree/]*.bin` (no packing) |
| `pack` | an existing bin tree → `.pf` + `.hf` (with `--base`: patch an existing pair) |
| `pack-extract` | `.pf` + `.hf` → bin files (`--only Name.bin` for a subset) |
| `decompile` | `.bin` → `json/<Format>/<Section>.json` |
| `list-formats` | print the supported tables, and the one shipped blob |

| option | meaning |
|---|---|
| `--src` / `--out` | input / output folder — the default depends on the command (`bin`, `json`, `bin_out`) |
| `--only` | comma separated format names, e.g. `--only Buff,Ride` |
| `--overwrite` | replace existing output files |
| `--compact` | single line JSON instead of the default tab indented output |
| `--no-recursive` | decompile only: do not descend into sub folders of `--src` |
| `--tree` | `compile`/`build`: sub path under `--out` for the bins (default `Pack03/Data/Bin/English`) |
| `--pack-name`, `--pack-prefix` | pack base name (default `Pack03`) and the folder stored inside it (default `data\bin\english\`) |
| `--base DIR` | `build`/`pack`: rebuild a pack from an existing `DIR/<pack-name>.pf` + `.hf`, copying every file you did not supply |
| `--hash-seed`, `--hash-path`, `--dual-index` | index hash variants for packs with a non-standard internal prefix — the defaults already match the retail pack, see [the pack files](docs/pack-format.md) |

Every file is reported as `OK`, `WARN`, `SKIP` (unsupported table) or `FAIL` (with
the reason). Decompiling also verifies itself: the document is re-encoded in memory
and compared with the input.

## Folder layout

| path | contents |
|---|---|
| `json/<Format>/` | decompiled tables, one file per section |
| `binconv/` | the converter (`binary.py`, `codec.py`, `pack.py`, `formats/`, …) |
| `blob/` | binaries with no codec, shipped verbatim (currently `NewTutorial.bin`) |
| `bin/` | input bins (git-ignored) |
| `bin_out/` | rebuilt `Pack03.pf`/`Pack03.hf` and `Pack03/Data/Bin/English/*.bin` (git-ignored) |
| `docs/` | everything else: [documentation index](docs/README.md) |

## Documentation

| page | contents |
|---|---|
| [Getting started](docs/getting-started.md) | the workflow end to end, with the exact numbers of a verified build |
| [Supported formats](docs/formats.md) | every table, its record layout and its quirks |
| [JSON layout](docs/json-schema.md) | how a table becomes one folder of section files |
| [The pack files](docs/pack-format.md) | `.pf`/`.hf` structure, the name hash, the blob policy |
| [Validation](docs/validation.md) | how a build is checked, and what is exact versus equivalent |
| [Modding](docs/modding.md) | is this repo usable for mods, and how do you prove the client accepts a pack |
| [What the DMO client expects](docs/client-notes.md) | where each layout comes from, which manager reads which file |
| [Naming](docs/naming.md) | the JSON key policy |
| [The original converter](docs/legacy-converter.md) | provenance, and the bugs it had |
| [Development helpers](docs/tools.md) | the verification scripts |

## Status

`python binconv.py` followed by `python tools/verify_pack.py bin_out <retail-data>`
reports: same 49 paths, hashes, sizes, offsets and physical order; 24 payloads byte
identical, the other 25 differing only in padding the game never reads. See
[validation](docs/validation.md) for the full table and for the three things in the
retail pair that cannot be reproduced.
