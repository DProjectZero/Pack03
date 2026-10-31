"""Reader and writer for the client's pack pair (``Pack03.pf`` + ``Pack03.hf``).

Spec
----
Transcribed from ``dmz-client/LibProj/CsFilePack`` (``CsFilePack.cpp``,
``CsFileHash.cpp``, ``FPHeader.cpp``) and then *verified against the retail
``Data/Pack03.pf`` / ``.hf``* shipped with the client:

``.hf`` (the index, `CsFileHash`) — 8 + 24 × n bytes::

    FHHeader { u32 version = 0x10; i32 fileCount; }
    n × sINFO { u32 flag = 1 (PG_TYPE_DATA); i32 dataSize; i32 allocSize;
                u32 nameHash; u64 offset; }            // #pragma pack(4), x86

``.pf`` (the payload, `CsFilePack`) — 8 + Σ(268 + size) bytes::

    FPHeader { u32 version = 0x10; u32 flag = 0; }
    per file, in the order the packer added them:
        sCHUNK { char path[260]; u32 flag; i32 nameLen; }   // 268 bytes
        raw file bytes                                      // `offset` points here

The first ``nameLen`` bytes of ``path`` are the internal path XOR ``0xD0``
(``FP_XOR_VALUE``); the rest is unspecified.  ``offset`` is the position *after*
the 268-byte chunk, i.e. ``chunk_start + 268``.

Name hash
---------
``CsFPS::GetHashCode`` is djb2 — ``h = h * 33 + ch`` over the lowercased string
with ``.`` and ``\\`` skipped, 32-bit wrap — but the build that produced the retail
packs starts from **seed 958121186 (0x391B4F62)**, not the ``5381`` in the source
snapshot.  The value is computed over the *bare file name*
(``sCHUNK::GetFilePath`` splits path and name); with that seed all 47 Pack03
entries whose sizes identify them uniquely match, so the formula is exact.

What cannot be reproduced
-------------------------
Two things in the retail files are artefacts of the tool, not of the format:

* **Chunk tails.** The packer fills ``path[nameLen:]`` with ``rand() % 256``
  (``CsFilePack.cpp``).  The retail tails match neither MSVC ``rand()`` seed 0
  nor 1, so they are unreproducible; this writer pads with zeros (the client only
  XORs/reads the first ``nameLen`` bytes, so this is invisible to it).
* **Index order.** The retail ``.hf`` is not sorted by hash, by name, by size or
  by offset — it is a hash-table iteration order.  This writer emits the entries
  **sorted by name hash**, which is deterministic and what ``CsFileHash::SaveFile``
  itself does.

Consequently a rebuilt pack is *functionally* identical — same entries, same name
hashes, same sizes, same internal paths, and the same physical order and offsets
as the retail pack — but not byte-identical to it: only the chunk tails and the
index order differ, plus any padding this repo's codecs normalise to zero (see
``README.md``).  ``tools/verify_pack.py`` reports all of that, entry by entry.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from .binary import FormatError

PACK_VERSION = 0x10
HASH_VERSION = 0x10
HASH_SEED = 958121186
PAYLOAD_FLAG = 1  # CsFileHash::ePLAG::PG_TYPE_DATA
CHUNK_SIZE = 268
PATH_SIZE = 260
PATH_XOR = 0xD0
ENTRY_SIZE = 24
HEADER_SIZE = 8


def name_hash(name: str) -> int:
    """``CsFPS::GetHashCode`` over the bare file name (see the module docstring)."""
    if not name:
        return 0
    bare = name.replace("/", "\\").rsplit("\\", 1)[-1]
    value = HASH_SEED
    for char in bare.lower():
        if char in ".\\":
            continue
        value = ((value << 5) + value + ord(char)) & 0xFFFFFFFF
    return value


@dataclass(frozen=True)
class PackEntry:
    """One ``.hf`` record."""

    path: str  # internal path from the chunk header, e.g. "data\\bin\\english\\Talk.bin"
    size: int
    offset: int
    flag: int = PAYLOAD_FLAG
    alloc_size: int = 0

    @property
    def name(self) -> str:
        return self.path.replace("/", "\\").rsplit("\\", 1)[-1]

    @property
    def hash(self) -> int:
        return name_hash(self.name)


def _read_chunk_name(pack: bytes, chunk_offset: int) -> tuple[str, int]:
    if chunk_offset < 0 or chunk_offset + CHUNK_SIZE > len(pack):
        raise FormatError(f"chunk at {chunk_offset} lies outside the pack")
    raw = pack[chunk_offset:chunk_offset + PATH_SIZE]
    name_len = int.from_bytes(
        pack[chunk_offset + PATH_SIZE + 4:chunk_offset + CHUNK_SIZE], "little", signed=True)
    if not 0 < name_len <= PATH_SIZE:
        raise FormatError(f"chunk at {chunk_offset}: implausible name length {name_len}")
    name = bytes(b ^ PATH_XOR for b in raw[:name_len]).decode("latin-1")
    return name, name_len


def read_index(hf_path: Path) -> list[PackEntry]:
    """Parse a ``.hf`` into entries, in file order (the retail order is not sorted)."""
    data = Path(hf_path).read_bytes()
    if len(data) < HEADER_SIZE:
        raise FormatError(f"{hf_path}: shorter than the 8-byte header")
    version = int.from_bytes(data[0:4], "little")
    count = int.from_bytes(data[4:8], "little", signed=True)
    if version != HASH_VERSION:
        raise FormatError(f"{hf_path}: unsupported hash version 0x{version:x}")
    if count < 0 or HEADER_SIZE + count * ENTRY_SIZE > len(data):
        raise FormatError(f"{hf_path}: {count} entries do not fit in {len(data)} bytes")
    entries = []
    for index in range(count):
        base = HEADER_SIZE + index * ENTRY_SIZE
        entries.append(PackEntry(
            path="",
            size=int.from_bytes(data[base + 4:base + 8], "little", signed=True),
            offset=int.from_bytes(data[base + 16:base + 24], "little"),
            flag=int.from_bytes(data[base:base + 4], "little"),
            alloc_size=int.from_bytes(data[base + 8:base + 12], "little", signed=True),
        ))
    return entries


def read_pack(pf_path: Path, hf_path: Path) -> list[tuple[PackEntry, bytes]]:
    """Return ``(entry, payload)`` pairs with the internal path filled in."""
    pack = Path(pf_path).read_bytes()
    if len(pack) < HEADER_SIZE:
        raise FormatError(f"{pf_path}: shorter than the 8-byte header")
    version = int.from_bytes(pack[0:4], "little")
    if version != PACK_VERSION:
        raise FormatError(f"{pf_path}: unsupported pack version 0x{version:x}")

    result = []
    for entry in read_index(hf_path):
        name, _ = _read_chunk_name(pack, entry.offset - CHUNK_SIZE)
        payload = pack[entry.offset:entry.offset + entry.size]
        if len(payload) != entry.size:
            raise FormatError(f"{pf_path}: entry {name!r} runs past the end of the pack")
        result.append((PackEntry(path=name, size=entry.size, offset=entry.offset,
                                 flag=entry.flag, alloc_size=entry.alloc_size), payload))
    return result


def write_pack(files: Iterable[tuple[str, bytes]], pf_path: Path, hf_path: Path) -> list[PackEntry]:
    """Write a ``.pf``/``.hf`` pair from ``(internal_path, data)`` pairs.

    Files are laid out in the order given; the index is sorted by name hash (what
    ``CsFileHash::SaveFile`` does).  *internal_path* uses backslashes and should be
    lowercase to mirror the retail layout (``data\\bin\\english\\Talk.bin``).
    """
    items = [(path, bytes(data)) for path, data in files]
    if not items:
        raise FormatError("refusing to write an empty pack")

    seen: set[int] = set()
    for path, _ in items:
        digest = name_hash(path)
        if digest in seen:
            raise FormatError(f"duplicate name hash for {path!r}")
        seen.add(digest)

    pf_path, hf_path = Path(pf_path), Path(hf_path)
    pf_path.parent.mkdir(parents=True, exist_ok=True)
    hf_path.parent.mkdir(parents=True, exist_ok=True)

    entries: list[PackEntry] = []
    payload = bytearray(PACK_VERSION.to_bytes(4, "little") + bytes(4))
    for path, data in items:
        payload += _chunk(path)
        entries.append(PackEntry(path=path, size=len(data), offset=len(payload),
                                 flag=PAYLOAD_FLAG, alloc_size=len(data)))
        payload += data

    index = bytearray(HASH_VERSION.to_bytes(4, "little")
                      + len(entries).to_bytes(4, "little", signed=True))
    for entry in sorted(entries, key=lambda item: item.hash):
        index += entry.flag.to_bytes(4, "little")
        index += entry.size.to_bytes(4, "little", signed=True)
        index += entry.alloc_size.to_bytes(4, "little", signed=True)
        index += entry.hash.to_bytes(4, "little")
        index += entry.offset.to_bytes(8, "little")

    pf_path.write_bytes(bytes(payload))
    hf_path.write_bytes(bytes(index))
    return entries


def collect(folder: Path, suffix: str = ".bin", prefix: str = "") -> list[tuple[str, bytes]]:
    """Every ``suffix`` file under *folder* as ``(internal path, data)`` pairs."""
    folder = Path(folder)
    if not folder.is_dir():
        raise FormatError(f"not a folder: {folder}")
    files = []
    # The retail packer adds files in the order the filesystem returns them
    # (NTFS $I30 order: upper-cased comparison, so 'DigimonParcel' <
    # 'Digimon_Book' < 'DMBase').  Sorting the same way makes the rebuilt pack
    # land on identical offsets.
    for path in sorted(folder.rglob(f"*{suffix}"), key=lambda item: item.name.upper()):
        if not path.is_file():
            continue
        parts = list(path.relative_to(folder).parts)
        # The retail pack stores "data\bin\english\<Name>.bin": folders lowercase,
        # file name keeps its original spelling.
        folded = [part.lower() for part in parts[:-1]] + [parts[-1]]
        files.append((prefix + "\\".join(folded), path.read_bytes()))
    if not files:
        raise FormatError(f"no {suffix} files under {folder}")
    return files


def extract(pack_dir: Path, destination: Path, names: Sequence[str] | None = None) -> list[Path]:
    """Unpack the ``.pf``/``.hf`` pair found in *pack_dir* into *destination*."""
    pack_dir = Path(pack_dir)
    packs = sorted(pack_dir.glob("*.pf"))
    if not packs:
        raise FormatError(f"no .pf file in {pack_dir}")
    pf_path = packs[0]
    hf_path = pf_path.with_suffix(".hf")
    if not hf_path.exists():
        raise FormatError(f"missing index: {hf_path}")

    wanted = {name.lower() for name in names} if names else None
    written: list[Path] = []
    for entry, payload in read_pack(pf_path, hf_path):
        if wanted is not None and entry.name.lower() not in wanted:
            continue
        target = Path(destination) / entry.name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        written.append(target)
    if wanted is not None and len(written) != len(wanted):
        found = {path.name.lower() for path in written}
        raise FormatError(f"not in pack: {', '.join(sorted(wanted - found))}")
    return written


def _chunk(path: str) -> bytes:
    encoded = path.encode("latin-1")
    if not encoded or len(encoded) > PATH_SIZE:
        raise FormatError(f"internal path must be 1..{PATH_SIZE} bytes: {path!r}")
    body = bytes(b ^ PATH_XOR for b in encoded) + bytes(PATH_SIZE - len(encoded))
    return body + (0).to_bytes(4, "little") + len(encoded).to_bytes(4, "little", signed=True)

