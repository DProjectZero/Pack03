"""Reader and writer for the client's pack pair (``Pack03.pf`` + ``Pack03.hf``).

Spec
----
Transcribed from the DMO client (``CsFilePack.cpp``, ``CsFileHash.cpp``,
``FPHeader.cpp``) and then *verified against the retail ``Data/Pack03.pf`` / ``.hf``*
shipped with the client:

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
#: The seed the client source ships with (``FPHeader.cpp``).  Packs written with
#: it are only readable by a client built from that source; see ``--hash-seed``.
LEGACY_SEED = 5381
PAYLOAD_FLAG = 1  # CsFileHash::ePLAG::PG_TYPE_DATA
CHUNK_SIZE = 268
PATH_SIZE = 260
PATH_XOR = 0xD0
ENTRY_SIZE = 24
HEADER_SIZE = 8


def name_hash(name: str, seed: int = HASH_SEED, full_path: bool = False) -> int:
    """``CsFPS::GetHashCode`` for *name* (see the module docstring).

    *seed* picks the djb2 start value and *full_path* keeps the folder part of the
    string instead of hashing the bare file name, which is how the client source
    computes it.
    """
    if not name:
        return 0
    text = name.replace("/", "\\")
    if not full_path:
        text = text.rsplit("\\", 1)[-1]
    value = seed
    for char in text.lower():
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
    hashes: tuple[int, ...] = ()  # exactly what the index stores (empty: compute)

    @property
    def name(self) -> str:
        return self.path.replace("/", "\\").rsplit("\\", 1)[-1]

    @property
    def hash(self) -> int:
        return self.hashes[0] if self.hashes else name_hash(self.name)


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
            hashes=(int.from_bytes(data[base + 12:base + 16], "little"),),
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
    seen_offsets = set()
    for entry in read_index(hf_path):
        if entry.offset in seen_offsets:
            continue  # a dual-index pack stores two hashes for one payload
        seen_offsets.add(entry.offset)
        name, _ = _read_chunk_name(pack, entry.offset - CHUNK_SIZE)
        payload = pack[entry.offset:entry.offset + entry.size]
        if len(payload) != entry.size:
            raise FormatError(f"{pf_path}: entry {name!r} runs past the end of the pack")
        result.append((PackEntry(path=name, size=entry.size, offset=entry.offset,
                                 flag=entry.flag, alloc_size=entry.alloc_size,
                                 hashes=entry.hashes), payload))
    return result


def _index_hashes(path: str, seed: int, full_path: bool, dual: bool) -> tuple[int, ...]:
    primary = name_hash(path, seed, full_path)
    if not dual:
        return (primary,)
    legacy = name_hash(path, LEGACY_SEED, full_path)
    return (primary,) if legacy == primary else (primary, legacy)


def _record(entry: PackEntry, digest: int) -> bytes:
    return b"".join((
        entry.flag.to_bytes(4, "little"),
        entry.size.to_bytes(4, "little", signed=True),
        entry.alloc_size.to_bytes(4, "little", signed=True),
        digest.to_bytes(4, "little"),
        entry.offset.to_bytes(8, "little"),
    ))


def _index_bytes(records: list[tuple[PackEntry, int]], declared: int,
                 sort: bool = True) -> bytes:
    body = bytearray(HASH_VERSION.to_bytes(4, "little") + declared.to_bytes(4, "little", signed=True))
    order = sorted(records, key=lambda item: item[1]) if sort else list(records)
    for entry, digest in order:
        body += _record(entry, digest)
    return bytes(body)


def write_pack(files: Iterable[tuple[str, bytes]], pf_path: Path, hf_path: Path, *,
               seed: int = HASH_SEED, full_path: bool = False,
               dual: bool = False) -> list[PackEntry]:
    """Write a ``.pf``/``.hf`` pair from ``(internal_path, data)`` pairs.

    Files are laid out in the order given; the index is sorted by name hash (what
    ``CsFileHash::SaveFile`` does).  *internal_path* uses backslashes and should be
    lowercase to mirror the retail layout (``data\\bin\\english\\Talk.bin``).

    ``seed``/``full_path`` select the hash variant (see :func:`name_hash`), and
    ``dual`` stores both the retail and the client-source hash for every entry, so
    one pack is readable by either client build.
    """
    items = [(path, bytes(data)) for path, data in files]
    if not items:
        raise FormatError("refusing to write an empty pack")

    seen: set[int] = set()
    for path, _ in items:
        for digest in _index_hashes(path, seed, full_path, dual):
            if digest in seen:
                raise FormatError(f"duplicate name hash for {path!r}")
            seen.add(digest)

    pf_path, hf_path = Path(pf_path), Path(hf_path)
    pf_path.parent.mkdir(parents=True, exist_ok=True)
    hf_path.parent.mkdir(parents=True, exist_ok=True)

    entries: list[PackEntry] = []
    records: list[tuple[PackEntry, int]] = []
    payload = bytearray(PACK_VERSION.to_bytes(4, "little") + bytes(4))
    for path, data in items:
        payload += _chunk(path)
        entry = PackEntry(path=path, size=len(data), offset=len(payload),
                          flag=PAYLOAD_FLAG, alloc_size=len(data),
                          hashes=_index_hashes(path, seed, full_path, dual))
        entries.append(entry)
        records.extend((entry, digest) for digest in entry.hashes)
        payload += data

    pf_path.write_bytes(bytes(payload))
    hf_path.write_bytes(_index_bytes(records, len(records)))
    return entries


def patch_pack(base_pf: Path, base_hf: Path, updates: Iterable[tuple[str, bytes]],
               pf_path: Path, hf_path: Path, *, seed: int = HASH_SEED,
               full_path: bool = False, dual: bool = False) -> dict[str, list[str]]:
    """Rebuild a pack from an existing one, replacing/adding only *updates*.

    Untouched entries are copied byte for byte — chunk tail included — so the
    result is identical to the base pack except where a file was replaced, and the
    base pack's order is preserved; new files are appended, which is what the
    client's own ``CsFilePack::_AddFile`` does.

    Returns ``{"replaced": [...], "added": [...], "kept": [...]}`` (file names).
    """
    base_pf, base_hf = Path(base_pf), Path(base_hf)
    pack = base_pf.read_bytes()
    entries = read_pack(base_pf, base_hf)

    wanted: dict[str, bytes] = {}
    paths: dict[str, str] = {}
    for path, data in updates:
        name = path.replace("/", "\\").rsplit("\\", 1)[-1]
        wanted[name] = bytes(data)
        paths[name] = path
    known = {entry.name for entry, _ in entries}
    replaced = sorted(name for name in wanted if name in known)
    added = sorted(name for name in wanted if name not in known)

    # Records keep their stored hash, so untouched entries stay index-identical.
    records: list[tuple[PackEntry, int]] = [(entry, entry.hash) for entry, _ in entries]

    pf_path, hf_path = Path(pf_path), Path(hf_path)
    pf_path.parent.mkdir(parents=True, exist_ok=True)
    hf_path.parent.mkdir(parents=True, exist_ok=True)

    out = bytearray(pack[:HEADER_SIZE])
    moved: dict[str, PackEntry] = {}
    for entry, _ in sorted(entries, key=lambda item: item[0].offset):
        chunk_start = entry.offset - CHUNK_SIZE
        chunk = pack[chunk_start:entry.offset]
        new_offset = len(out) + CHUNK_SIZE
        if entry.name not in wanted:
            out += chunk
            out += pack[entry.offset:entry.offset + entry.size]
            moved[entry.name] = PackEntry(
                path=entry.path, size=entry.size, offset=new_offset, flag=entry.flag,
                alloc_size=entry.alloc_size, hashes=entry.hashes)
            continue
        data = wanted[entry.name]
        out += chunk
        out += data
        # ``_EditFile`` keeps the allocation when the new data still fits.
        moved[entry.name] = PackEntry(
            path=entry.path, size=len(data), offset=new_offset, flag=entry.flag,
            alloc_size=max(len(data), entry.alloc_size), hashes=entry.hashes)

    records = [(moved[entry.name], digest) for entry, digest in records]

    for name in added:
        data = wanted[name]
        out += _chunk(paths[name])
        offset = len(out)
        out += data
        entry = PackEntry(path=paths[name], size=len(data), offset=offset,
                          flag=PAYLOAD_FLAG, alloc_size=len(data),
                          hashes=_index_hashes(paths[name], seed, full_path, dual))
        records.extend((entry, digest) for digest in entry.hashes)

    pf_path.write_bytes(bytes(out))
    hf_path.write_bytes(_index_bytes(records, len(records), sort=False))
    return {
        "replaced": replaced,
        "added": added,
        "kept": sorted(name for name in known if name not in wanted),
    }


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


def extract(pack_dir: Path, destination: Path, names: Sequence[str] | None = None,
            pack_name: str | None = None) -> list[Path]:
    """Unpack the ``<pack_name>.pf``/``.hf`` pair found in *pack_dir*.

    Without *pack_name* the folder must hold exactly one ``.pf``, so a data folder
    with several packs (``Pack01``, ``Pack03``, ...) cannot be unpacked by accident.
    """
    pack_dir = Path(pack_dir)
    if pack_name:
        pf_path = pack_dir / f"{pack_name}.pf"
        if not pf_path.exists():
            raise FormatError(f"no {pf_path.name} in {pack_dir}")
    else:
        packs = sorted(pack_dir.glob("*.pf"))
        if not packs:
            raise FormatError(f"no .pf file in {pack_dir}")
        if len(packs) > 1:
            names_ = ", ".join(path.stem for path in packs)
            raise FormatError(f"{pack_dir} holds several packs ({names_}); pass --pack-name")
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

