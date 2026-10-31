"""Compare a rebuilt ``Pack03.pf`` / ``.hf`` with a reference pair.

    python tools/verify_pack.py bin_out PROGRAM_DATA_DIR

Checks, in order: same entry set, same name hashes, same sizes, same internal
paths, same physical order and offsets; then that every payload difference is a
byte ``binconv`` wrote as ``0x00`` (padding / string-tail normalisation); then
whether the two files are byte identical.

Byte identity is *expected* to fail, for reasons that are properties of the retail
build rather than of this tool (see ``binconv/pack.py``):

* every 268-byte chunk tail holds ``rand()`` output the retail packer generated,
* the index is written in a hash-table iteration order,
* 25 of the 49 bins hold leftover bytes in unused string/struct padding, which
  this repo's codecs normalise to zero on purpose (see ``README.md``).
"""

from __future__ import annotations

import filecmp
import mmap
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from binconv.pack import CHUNK_SIZE, PATH_XOR, read_index  # noqa: E402

BLOCK = 1 << 20


def _load(path: Path) -> mmap.mmap:
    handle = path.open("rb")
    return mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ)


def _entries(pf_path: Path, hf_path: Path) -> list[tuple[str, int, int, int]]:
    """``(name, offset, size, hash)`` per index entry."""
    pack = _load(pf_path)
    try:
        rows = []
        for entry in read_index(hf_path):
            start = entry.offset - CHUNK_SIZE
            name_len = int.from_bytes(pack[start + 264:start + 268], "little", signed=True)
            name = bytes(b ^ PATH_XOR for b in pack[start:start + name_len]).decode("latin-1")
            rows.append((name, entry.offset, entry.size, entry.hash))
        return rows
    finally:
        pack.close()


def _scan(ours: mmap.mmap, theirs: mmap.mmap, offset: int, size: int) -> tuple[int, int]:
    """Differing bytes in a payload, and how many of them we wrote as ``0x00``."""
    differing = zeroed = 0
    for start in range(offset, offset + size, BLOCK):
        end = min(start + BLOCK, offset + size)
        left, right = ours[start:end], theirs[start:end]
        if left == right:
            continue
        for mine, ref in zip(left, right):
            if mine != ref:
                differing += 1
                if mine == 0:
                    zeroed += 1
    return differing, zeroed


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    pack_dir, reference_dir = Path(argv[1]), Path(argv[2])
    ours_pf, ours_hf = pack_dir / "Pack03.pf", pack_dir / "Pack03.hf"
    ref_pf, ref_hf = reference_dir / "Pack03.pf", reference_dir / "Pack03.hf"
    for path in (ours_pf, ours_hf, ref_pf, ref_hf):
        if not path.exists():
            print(f"missing: {path}")
            return 2

    ours = _entries(ours_pf, ours_hf)
    ref = _entries(ref_pf, ref_hf)
    ours_by = {row[0]: row for row in ours}
    ref_by = {row[0]: row for row in ref}
    shared = sorted(set(ours_by) & set(ref_by))

    print(f"ours:      {len(ours)} entries  .pf {ours_pf.stat().st_size} B  "
          f".hf {ours_hf.stat().st_size} B  ({pack_dir})")
    print(f"reference: {len(ref)} entries  .pf {ref_pf.stat().st_size} B  "
          f".hf {ref_hf.stat().st_size} B  ({reference_dir})")
    print()

    missing = sorted(set(ref_by) - set(ours_by))
    extra = sorted(set(ours_by) - set(ref_by))

    ours_pack, ref_pack = _load(ours_pf), _load(ref_pf)
    try:
        identical, padding_only, real = [], [], []
        total_diff = total_zeroed = 0
        for name in shared:
            _, offset, size, _ = ours_by[name]
            if ours_pack[offset:offset + size] == ref_pack[offset:offset + size]:
                identical.append(name)
                continue
            differing, zeroed = _scan(ours_pack, ref_pack, offset, size)
            total_diff += differing
            total_zeroed += zeroed
            (padding_only if differing == zeroed else real).append(name)
    finally:
        ours_pack.close()
        ref_pack.close()

    hashes_ok = all(ours_by[name][3] == ref_by[name][3] for name in shared)
    sizes_ok = all(ours_by[name][2] == ref_by[name][2] for name in shared)
    offsets_ok = all(ours_by[name][1] == ref_by[name][1] for name in shared)
    order_ok = ([row[0] for row in sorted(ours, key=lambda row: row[1])]
                == [row[0] for row in sorted(ref, key=lambda row: row[1])])
    paths_ok = set(ours_by) == set(ref_by)

    print(f"same internal paths : {paths_ok}"
          + (f"   missing={','.join(missing)}" if missing else "")
          + (f"   extra={','.join(extra)}" if extra else ""))
    print(f"same name hashes    : {hashes_ok}")
    print(f"same sizes          : {sizes_ok}")
    print(f"same offsets        : {offsets_ok}")
    print(f"same physical order : {order_ok}")
    print(f"identical payloads  : {len(identical)}/{len(shared)}")
    print(f"padding-only diffs  : {len(padding_only)} file(s), {total_diff} byte(s), "
          f"all written as 0x00 ({total_zeroed} confirmed)")
    if real:
        print(f"REAL differences    : {', '.join(real)}")
    print()
    return _files(ours_pf, ours_hf, ref_pf, ref_hf,
                  paths_ok and hashes_ok and sizes_ok and offsets_ok and order_ok and not real)


def _files(ours_pf: Path, ours_hf: Path, ref_pf: Path, ref_hf: Path, structural: bool) -> int:
    """Byte comparison of the two files, then the verdict."""
    for label, left, right in ((".pf", ours_pf, ref_pf), (".hf", ours_hf, ref_hf)):
        if filecmp.cmp(left, right, shallow=False):
            print(f"{label} byte identical  : True")
            continue
        a, b = _load(left), _load(right)
        limit = min(len(a), len(b))
        first, count = -1, 0
        for start in range(0, limit, BLOCK):
            chunk_a = a[start:min(start + BLOCK, limit)]
            chunk_b = b[start:min(start + BLOCK, limit)]
            if chunk_a == chunk_b:
                continue
            if first < 0:
                first = start + next(i for i in range(len(chunk_a)) if chunk_a[i] != chunk_b[i])
            count += sum(1 for x, y in zip(chunk_a, chunk_b) if x != y)
        a.close()
        b.close()
        print(f"{label} byte identical  : False  (first diff at {first}, "
              f"{count} of {limit} B)")

    print(f"\nstructurally identical, data identical up to normalised padding: "
          f"{'YES' if structural else 'NO'}")
    return 0 if structural else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
