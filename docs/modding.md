# Modding

Short answer: **yes for the tables** — item stats, drop tables, shops, quest text,
UI strings, museum/achievement data and anything else in the 49 `Data\Bin\English`
files. Not covered: models, textures, maps and audio, which live in `Pack01.pf` and
have no reader here.

## Two ways to deliver a change

The client can read tables from a **pack** or from **loose files**, and the pack
wins when both exist (`CsFPSystem::IsExist` looks in the mounted packs first and
only then on disk). So:

| route | how | good for |
|---|---|---|
| loose files | put `Data\Bin\English\<Name>.bin` next to the client and run it with table packs disabled (the `dmo.ini` debug flag `FilePack`, which the client reads into `g_bUseFilePack`) | quick tests: no packing at all, just drop the file in |
| pack | replace `Data\Pack03.pf`/`.hf` with a rebuilt pair | anything you ship, and the only option for a stock client (`Pack03` is the global/Steam table pack, `Pack02` Korean, `Pack04` Thai, `Pack06` Taiwan, `Pack07` Hong Kong) |

`python binconv.py` writes both shapes at once: `bin_out/Pack03/Data/Bin/English/`
is exactly the loose-files layout, and `bin_out/Pack03.pf`/`.hf` is the pack.

## Ship a small pack, not all 49 tables

Rebuilding every table rewrites the whole 70 MB pack, and 25 of the 49 bins will
differ from the retail bytes in padding the game never reads. For a mod you only
need to replace the tables you changed:

```powershell
python binconv.py pack --src <folder with your changed .bin files> `
                       --base "<game>\Data" --out dist
```

`--base` copies every file you did not supply **byte for byte** (chunk headers and
their random tails included), keeps the retail order and index, and appends any new
file at the end — the same thing the client's own packer does when it edits a pack.
A patched pack is therefore identical to the retail pair except for the entries you
touched, which also makes the diff easy to review. If you supply the *retail* files
back to `--base`, the result is byte-identical to the retail pair; that is exactly
how the pack writer is verified ([the pack files](pack-format.md)).

## Does the client accept it?

The pack loader is thin, and it was read end to end while this was written:

* `CsFileHash::Load` checks only the index **version** (`0x10`, or the compressed
  `0x11`/`0x12` variants) and reads `fileCount` records.
* `CsFilePack::Load` opens the payload and reads the 8-byte header. **There is no
  checksum, no signature and no size validation anywhere in the loader.**
* A file is found by hashing its path (`CsFPSystem::IsExist` → `GetHashCode`), then
  read by the `offset`/`size` in the index; `flag` is always `1` (`PG_TYPE_DATA`)
  and `allocSize` equals the size in every retail entry.

So a rebuilt pair is accepted when three things hold, and all three are checked by
`tools/verify_pack.py`:

1. **the same name hashes** — otherwise the client cannot find the files,
2. **the same internal paths, sizes and offsets** — otherwise it reads the wrong
   bytes,
3. **payloads the managers can parse** — our bins are byte-identical to retail
   except for unused padding, so this follows from (2) plus a passing
   `tools/verify_roundtrip.py`.

The one thing worth knowing: the hash **seed differs between two client builds**.
The retail pack's index is djb2 seeded with `958121186` over the *bare file name*;
the client source that circulates ships `5381` over the *whole path*. A pack built
with the default options is correct for the retail client (it reproduces the retail
index exactly); if you build the client yourself from that source, either align its
`GetHashCode` with the retail behaviour or write the pack for it with
`--hash-seed 5381`, and use `--dual-index` to make one pack readable by both.

## Things that will bite

* **The server reads the same files.** Gameplay tables (items, monsters, skills,
  drops, quests) are shared with the DMO server, which parses the same `.bin`
  files. Client-only edits desynchronise the two: apply gameplay changes on both
  sides, and use client-only tables (text, UI, visuals) for client-only mods.
* **Strings are fixed-size buffers.** The client reads them as C strings; anything
  past the buffer is truncated on compile, and text containing NULs cannot be
  represented.
* **Some tables have structural invariants** the compiler enforces: counts derived
  from the list length, `Npc` blocks that depend on `Type`, the `Achieve` tree, the
  `CashShop` document pairing, `Event`'s per-slot item tables
  ([supported formats](formats.md) lists them per table). A JSON edit that breaks
  one is refused rather than written, which is what you want.
* **The launcher and anti-cheat.** `DMLauncher`/`UpdateManager` may repair or
  re-download packs, and XIGNCODE runs next to the client. Test offline, keep a
  backup of the original pair, and expect to run the client without its launcher.
* **`NewTutorial.bin`** cannot be regenerated: it has no reader anywhere and ships
  as a blob, so a `--base`-less rebuild copies it verbatim.

## Verifying a mod before you play it

1. `python binconv.py` and then `tools/verify_roundtrip.py <bin dir>` — every table
   you changed must round-trip exactly or only normalise padding.
2. `python tools/verify_pack.py dist "<game>\Data"` for a `--base` build: it lists
   exactly which entries differ and confirms nothing else moved.
3. Drop the pair into `Data`, keep a copy of the originals, and start the client
   with table packs enabled. Any table the client cannot find produces its usual
   file-not-found popup naming the path — that is the fastest signal that a hash or
   path is wrong.
4. If you have the client source, its own `TestHF` sample program can unpack a pack
   with the real loader (`TestHF <path>\Pack03`), which is the same code path the
   game uses.
