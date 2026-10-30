"""Check that ``decode`` / ``encode`` reproduce a ``.bin`` byte for byte.

Usage:
    python tools/verify_roundtrip.py PROGRAM/DATA/ItemList.bin
    python tools/verify_roundtrip.py PROGRAM/DATA            # every supported file

Exit code is 0 when all files round-trip exactly.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from binconv import formats  # noqa: E402
from binconv.binary import FormatError  # noqa: E402
from binconv.codec import compare_roundtrip  # noqa: E402


def diff_ranges(a: bytes, b: bytes, limit: int = 12, chunk: int = 65536) -> list[tuple[int, int]]:
    """Return at most *limit* ``(start, end)`` inclusive ranges that differ.

    Compares in chunks first so multi megabyte files stay fast; only the
    differing chunks are scanned byte by byte.
    """

    ranges: list[tuple[int, int]] = []
    for base in range(0, min(len(a), len(b)), chunk):
        left_chunk = a[base : base + chunk]
        right_chunk = b[base : base + chunk]
        if left_chunk == right_chunk:
            continue
        start = end = None
        for offset in range(len(left_chunk)):
            if left_chunk[offset] != right_chunk[offset]:
                if start is None:
                    start = base + offset
                end = base + offset
            elif start is not None:
                ranges.append((start, end))
                start = end = None
                if len(ranges) >= limit:
                    return ranges
        if start is not None:
            ranges.append((start, end))
            if len(ranges) >= limit:
                return ranges
    return ranges


def count_differences(a: bytes, b: bytes, chunk: int = 65536) -> int:
    total = abs(len(a) - len(b))
    for base in range(0, min(len(a), len(b)), chunk):
        left = a[base : base + chunk]
        right = b[base : base + chunk]
        if left != right:
            total += sum(1 for x, y in zip(left, right) if x != y)
    return total


def verify(path: Path, limit: int = 6, context: int = 24) -> bool:
    codec = formats.for_filename(path.name)
    if codec is None:
        print(f"{path.name}: unsupported format")
        return False
    data = path.read_bytes()
    document = codec.decode(data, path.name)
    try:
        reencoded = codec.encode(document["sections"])
    except (FormatError, ValueError, KeyError) as error:
        print(f"{path.name}: FAIL {type(error).__name__}: {error}")
        return False

    status, differing = compare_roundtrip(data, reencoded)
    if status == "exact":
        print(f"{path.name}: OK ({len(data)} bytes, {len(document['sections'])} sections)")
        return True
    if status == "padding":
        print(
            f"{path.name}: OK ({len(data)} bytes, {differing} padding byte(s) normalised)"
        )
        return True

    print(f"{path.name}: DIFF {differing} byte(s) of {len(data)} (encoded {len(reencoded)})")
    for start, end in diff_ranges(data, reencoded, limit):
        left = start
        right = end + 1
        low = max(0, left - context)
        print(f"  offset {left}-{end} ({right - left} byte(s))")
        print(f"    file: {data[low:right + context]!r}")
        print(f"    ours: {reencoded[low:right + context]!r}")
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--limit", type=int, default=6, help="number of diff ranges to print")
    args = parser.parse_args(argv)

    files: list[Path] = []
    for path in args.paths:
        if path.is_dir():
            files.extend(sorted(p for p in path.iterdir() if p.suffix.lower() in (".bin", ".dat")))
        else:
            files.append(path)

    failures = 0
    for path in files:
        if not verify(path, args.limit):
            failures += 1
    print(f"\n{len(files) - failures}/{len(files)} file(s) round-trip exactly")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
