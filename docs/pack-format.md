# The pack files

How `Pack03.pf` and `Pack03.hf` are laid out, and what a rebuilt pair matches in the retail data.

## How a build writes the pair

`python binconv.py` (or `build`) does the whole chain:

1. compile every format folder in `json/` into
   `bin_out/Pack03/Data/Bin/English/<Name>.bin` (the retail tree, so the folder
   name in the pack comes out right),
2. copy the blobs from `blob/` in beside them (one file, see below),
3. write `bin_out/Pack03.pf` and `bin_out/Pack03.hf` from that folder.

`pack` does step 3 for an existing tree, `pack-extract` reads a pair back.
The formats are transcribed in `binconv/pack.py`: a `FPHeader`/`FHHeader` of
`{u32 version = 0x10, u32/i32 flag|count}`, then in `.pf` one 268-byte
`sCHUNK { char path[260]; u32 flag; i32 nameLen; }` per file followed by the raw
bytes, and in `.hf` one 24-byte `sINFO { flag, size, alloc, hash, u64 offset }`
per file. The path in a chunk is stored XOR `0xD0`, `offset` points *after* the
chunk, and `flag` is `1` (`PG_TYPE_DATA`).

The name hash is djb2 (`h * 33 + ch`, `32` bit wrap) over the lowercased file name
with `.` and `\` skipped, seeded with **958121186 (`0x391BC4E2`)**; with that seed
all 49 shipped names match the retail `.hf` (`Talk.bin` → `0x515bd0e7`,
`NewTutorial.bin` → `0xabe373b9`, …). That constant is the bare-name hash of the
folder prefix, so a loader that hashes the whole internal path with `5381` (what
`FPHeader.cpp` does) computes the same value — there is one hash per file, not one
per client build. See [hash variants](#hash-variants).

`tools/verify_pack.py bin_out <retail-data>` compares a rebuilt pair with the
retail one. The current build lands on:

| check | result |
|---|---|
| internal paths, name hashes, sizes, offsets | **identical** (49/49) |
| physical order in `.pf` | **identical** (`Achieve`, `AddExp`, … `WorldMap`) |
| payload bytes | 24/49 identical; the other 25 differ only in **3 343 340** bytes that we write as `0x00` (the padding normalisation described under [Validation](#validation)) |
| `.pf` / `.hf` byte identity | no — see below |

Three things in the retail pair cannot be reproduced, and none of them is format
data:

* every chunk is padded after `nameLen` with `rand() % 256`; the retail tails
  match no MSVC `rand()` seed we could find, so they are written as zeros (the
  client only reads the first `nameLen` bytes),
* the retail `.hf` is in hash-table iteration order: not sorted by hash, name,
  size, offset or `hash % n`, and not the `.pf` order. We emit it sorted by name
  hash, which is what `CsFileHash::SaveFile` itself does,
* the 3.3 MB of padding above lives in the bins themselves (leftovers behind
  `TCHAR` terminators), so it would have to be carried through JSON to survive.

Byte identity therefore holds for a pair extracted from our own pack, and the
rebuilt pair is a drop-in replacement for the retail one.

### The one shipped blob

`NewTutorial.bin` (4 084 bytes) is the only binary in the pack that is **not**
reverse engineered: no reader exists in the client (`11.Tutorial` is XML-script
driven), in the old C# converter or in the server, and the retail `GDMO.exe` is
Themida-packed with XIGNCODE, so static analysis is not an option either. It is
committed as `blob/NewTutorial.bin` and copied into every build by
`binconv/blobs.py`, which also pins the expected size. `build` refuses to pack if
the tree does not hold exactly `len(formats) + len(blobs)` bins. If the layout is
ever recovered, write a codec for it, delete the entry from `BLOBS` and the file
from `blob/` — nothing else has to change.

## The pack file (`Data/Pack03.pf` + `Pack03.hf`)

The client mounts its data through `CsFPS::CsFPSystem`. The layout, verified
against the shipped files:

* `Pack03.hf` = `FHHeader { DWORD version (16), int fileCount }` followed by
  `fileCount` entries of 24 bytes:
  `{ u32 flag, u32 size, u32 allocSize, u32 nameHash, u64 offset }`.
* `Pack03.pf` = `FPHeader { DWORD version (16), DWORD flag }`, then per file a
  268-byte `sCHUNK { char path[260]; u32 flag; i32 nameLen }` whose path is
  stored XOR `0xD0` over the first `nameLen` bytes, immediately followed by the
  file contents **uncompressed**.  `offset` in the index points *after* the
  chunk, and `flag` is `1` (`PG_TYPE_DATA`).  The total is therefore
  `8 + Σ(268 + size)`, which matches the retail `73 715 577` byte file exactly.
* The stored paths are the retail tree with a lowercased folder part,
  `data\bin\english\Talk.bin`.
* The name hash is computed over the **bare file name**, not the path
  (`sCHUNK::GetFilePath` splits the two): a djb2 variant over the lowercased name
  with `.` and `\` stripped (`CsFPS::GetHashCode` in `FPHeader.cpp`):
  `h = h*33 + ch`, 32-bit wrap.  **The shipped pack uses seed 958121186
  (`0x391BC4E2`)**, which is simply the bare-name hash of the `data\bin\english\`
  prefix: a loader hashing the entire internal path from `5381` (the constant in
  the source snapshot) walks the same polynomial and lands on the same number, so
  both descriptions of the format agree and no pack or client needs a seed change.
  Verified two ways: inverting the polynomial over the 47 entries whose sizes
  identify them uniquely gives that seed and then matches **47/47**, and
  recomputing the hash of all 49 retail chunk paths with `5381` matches too.
  `NewTutorial.bin` hashes to `0xabe373b9`, which *is* in `Pack03.hf` — so all 49
  shipped bins are in the retail pack.
* The order files were added is the order `FindFirstFile` returned them, i.e.
  NTFS `$I30` (upper-cased comparison: `DigimonParcel` < `Digimon_Book` <
  `DMBase`).  Sorting a folder that way reproduces the retail offsets exactly.
* Two things in the retail pair come from the tool, not the format: the chunk
  tails hold `rand() % 256` output (no MSVC seed reproduces them) and the index is
  written in a hash-table iteration order — not sorted by hash, name, size, offset
  or `hash % n`, and not the `.pf` order.  `binconv/pack.py` writes zeros for the
  tails and sorts the index by name hash (what `CsFileHash::SaveFile` itself does).

Extracting every entry by its `(offset, size)` gives files byte identical to the
bins in the retail install (all 49 entries, verified).

## Patching an existing pack

`pack --base <dir>` (or `build --base <dir>`) reads `<dir>/Pack03.pf` + `.hf` and
rebuilds the pair, replacing only the files you pass in:

* an entry you do not supply is copied **byte for byte**, chunk tail included, and
  keeps its index record — base order and base hashes survive, only the offsets of
  later entries move if a replaced file changed size,
* an entry you supply is replaced in place, with `allocSize` kept at the larger of
  the old and new size (what the client's own `CsFilePack::_EditFile` does),
* a name that is not in the base pack is appended at the end, like
  `CsFilePack::_AddFile`.

Because untouched bytes are *copied* rather than regenerated, feeding the retail
files back through `--base` reproduces the retail `Pack03.pf` **and** `Pack03.hf`
byte for byte (73 715 577 B and 1 184 B). That is the strongest check the writer
has: the chunk tails and the index order that no build can compute are preserved
from the base file.

## Hash variants

There is one hash per file, and the defaults already produce it — **no seed change
is required for a stock build** (v487 included; the defaults mount correctly and a
`5381`/bare-name combination is what fails). The knobs exist for packs whose
internal prefix is not `data\bin\english\`:

| option | effect |
|---|---|
| `--hash-seed N` | djb2 start value (default `958121186`, the retail pack) — pass the bare-name equivalent of your prefix |
| `--hash-path` | hash the whole internal path instead of the bare file name; together with `--hash-seed 5381` that is the `FPHeader.cpp` model, which yields exactly the default hashes for the standard prefix |
| `--dual-index` | also store the path-model record for every file, both pointing at the same payload; with the standard prefix the two records coincide, so the index is unchanged |

`--dual-index` is a safety belt, not a requirement: it only adds a second record
when the path-model hash of an entry differs from the configured one (i.e. when the
prefix is non-standard), and `read_pack` still reports one file per entry.

