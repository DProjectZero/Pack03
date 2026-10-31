# Getting started

This page walks the whole workflow once: retail pack → JSON → edit → rebuilt pack →
verified. All commands run from the repository root.

## 1. Take the tables out of your own install

The client ships its tables inside `Data/Pack03.pf` (10 GB `Pack01.pf` holds models,
textures and sound; `Pack03.pf` holds the 49 table files). Copy the pair you need
somewhere writable and unpack it:

```powershell
python binconv.py pack-extract --src "<game>\Data" --out bin --pack-name Pack03
```

You get 49 `.bin` files named like the client's internal paths
(`Talk.bin`, `ItemList.bin`, …, `NewTutorial.bin`). If your install also has loose
`Data\Bin\English\*.bin` files you can use those directly and skip this step.

## 2. Turn them into JSON

```powershell
python binconv.py decompile --src bin --out json
```

One folder per table, one JSON file per section:

```
json/
  ItemList/            Buff/
    ItemList.json        Buff.json
    ItemExchange.json
  Event/
    Event.json
    AttendenceTime.json
    ...
```

Every file is reported as `OK`, `WARN`, `SKIP` or `FAIL`; decompiling re-encodes
its own output in memory, so `OK` means the JSON reproduces the input bytes and
`OK (N padding byte(s) normalised)` means it differs only in unused bytes the game
never reads ([validation](validation.md)).

`NewTutorial.bin` is reported as `SKIP unsupported format`; the file is copied
through unchanged instead.

## 3. Edit the JSON

The JSON is the source of truth, and the schema is regular: numbers are numbers,
fixed-size strings are strings, nested tables are lists of objects
([JSON layout](json-schema.md)). Fixed-size string fields have a hard limit (the
game reads them as C strings out of a fixed buffer), so keep text shorter than the
buffer or it will be truncated on compile.

## 4. Build a pack

```powershell
python binconv.py                # json -> bin_out/Pack03/Data/Bin/English + Pack03.pf/.hf
```

The bins are written into the retail folder tree so the pack stores the same
internal paths the client expects, and the pack is written next to them
(`bin_out/Pack03.pf`, `bin_out/Pack03.hf`). If you only changed a few tables, see
[modding](modding.md) for the much smaller `--base` route.

## 5. Check the result

```powershell
python tools/verify_pack.py bin_out "<game>\Data"
```

A healthy build reports the same 49 paths, name hashes, sizes, offsets and
physical order as the retail pack, and payloads that differ only in padding:

```
same internal paths : True      same sizes   : True
same name hashes    : True      same offsets : True
same physical order : True
identical payloads  : 24/49
padding-only diffs  : 25 file(s), 3343340 byte(s), all written as 0x00
```

## Where things live

| path | contents |
|---|---|
| `json/` | the tracked tables — commit your edits here |
| `bin/` | unpacked retail bins (git-ignored) |
| `bin_out/` | the build output (git-ignored) |
| `blob/` | the one table that has no codec, shipped verbatim |
| `docs/` | this documentation |
