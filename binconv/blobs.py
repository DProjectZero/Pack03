"""Binary tables that could not be reverse engineered and are kept as blobs.

Everything else in this repo is regenerated from JSON.  These files have no
reader in the client source, no entry in the old C# converter and no reference in
the server, and the retail ``GDMO.exe`` is Themida-packed with XIGNCODE, so the
layout cannot be recovered by either reading or disassembling.  They are shipped
verbatim — see ``docs/field-names.md`` / ``README.md`` for the discussion.

Adding one is deliberately explicit: it must be listed here, and :func:`copy_into`
verifies the size so a truncated or replaced file cannot slip into a pack.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .binary import FormatError

BLOB_DIR = "blob"


@dataclass(frozen=True)
class Blob:
    """A shipped binary table with no JSON representation."""

    name: str  # bin file name, e.g. "NewTutorial.bin"
    size: int  # exact size, verified on copy
    reason: str  # why it is a blob rather than a codec

    @property
    def path(self) -> Path:
        return Path(__file__).resolve().parent.parent / BLOB_DIR / self.name


BLOBS: tuple[Blob, ...] = (
    Blob(
        name="NewTutorial.bin",
        size=4084,
        reason=(
            "no reader anywhere: not in the DMO client, not in the original converter, not in "
            "the server; GDMO.exe is packed so it cannot be disassembled"
        ),
    ),
)


def copy_into(destination: Path) -> list[Path]:
    """Copy every blob into *destination* (creating it), verifying each size."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    written = []
    for blob in BLOBS:
        if not blob.path.exists():
            raise FormatError(f"missing blob {blob.path}")
        data = blob.path.read_bytes()
        if len(data) != blob.size:
            raise FormatError(
                f"{blob.path}: expected {blob.size} bytes, found {len(data)}")
        target = destination / blob.name
        target.write_bytes(data)
        written.append(target)
    return written
