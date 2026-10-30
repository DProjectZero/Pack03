"""Binary helpers mirroring the semantics of the original C# converter.

The original tool reads/writes with ``BinaryReader``/``BinaryWriter`` plus a
small ``BitReader`` wrapper (see ``reference/csharp/BitReader.cs``).  All values
are little endian, strings live in *fixed size* buffers and a few helpers
reproduce C# quirks on purpose so the byte layout stays identical.
"""

from __future__ import annotations

import base64
import struct

UTF16 = "utf-16-le"


class FormatError(ValueError):
    """Raised when a buffer does not match the expected layout."""


class Reader:
    """Sequential little endian reader over an in-memory buffer."""

    __slots__ = ("data", "pos", "name")

    def __init__(self, data: bytes, name: str = "<buffer>"):
        self.data = data
        self.pos = 0
        self.name = name

    # -- primitives -----------------------------------------------------
    def _take(self, count: int) -> bytes:
        end = self.pos + count
        if count < 0 or end > len(self.data):
            raise FormatError(
                f"{self.name}: unexpected end of data at offset {self.pos} "
                f"(wanted {count} byte(s), {len(self.data) - self.pos} left)"
            )
        chunk = self.data[self.pos : end]
        self.pos = end
        return chunk

    def skip(self, count: int) -> None:
        self._take(count)

    def u8(self) -> int:
        return self._take(1)[0]

    def i8(self) -> int:
        return struct.unpack("<b", self._take(1))[0]

    def u16(self) -> int:
        return struct.unpack("<H", self._take(2))[0]

    def i16(self) -> int:
        return struct.unpack("<h", self._take(2))[0]

    def u32(self) -> int:
        return struct.unpack("<I", self._take(4))[0]

    def i32(self) -> int:
        return struct.unpack("<i", self._take(4))[0]

    def u64(self) -> int:
        return struct.unpack("<Q", self._take(8))[0]

    def i64(self) -> int:
        return struct.unpack("<q", self._take(8))[0]

    def f32(self) -> float:
        return struct.unpack("<f", self._take(4))[0]

    def f64(self) -> float:
        return struct.unpack("<d", self._take(8))[0]

    def raw(self, count: int) -> bytes:
        return self._take(count)

    # -- strings --------------------------------------------------------
    def cstring(self, encoding: str, size: int) -> str:
        """Fixed size buffer, truncated at the first NUL (C# ``CleanString``)."""

        text = self._take(size).decode(encoding, "replace")
        index = text.find("\0")
        return text if index < 0 else text[:index]

    def wstring(self, chars: int) -> str:
        """Fixed UTF-16 buffer of *chars* characters, truncated at first NUL."""

        return self.cstring(UTF16, chars * 2)

    def zstring(self, encoding: str, size: int | None = None) -> str:
        """Port of ``BitReader.ReadZString(encoding, size)``.

        Reads until the terminating NUL run (1 byte for ASCII, 3 bytes for
        UTF-16), then advances to *size* bytes from the start of the field when
        the string was shorter.  All NULs are stripped from the result.
        """

        start = self.pos
        terminator = b"\0\0\0" if encoding == UTF16 else b"\0"
        index = self.data.find(terminator, start)
        if index < 0:
            raise FormatError(f"{self.name}: unterminated string at offset {start}")
        self.pos = index + len(terminator)

        buffer = self.data[start : self.pos]
        if size is not None and self.pos - start < size:
            # C# ReadBytes() silently returns fewer bytes at end of stream.
            self.pos = min(start + size, len(self.data))
        if len(buffer) % 2:
            buffer += b"\0"
        return buffer.decode(encoding, "replace").replace("\0", "")


class Writer:
    """Sequential little endian writer producing a ``bytearray``."""

    __slots__ = ("buffer",)

    def __init__(self, buffer: bytearray | None = None):
        self.buffer = bytearray() if buffer is None else buffer

    def __len__(self) -> int:
        return len(self.buffer)

    def getvalue(self) -> bytes:
        return bytes(self.buffer)

    # -- primitives -----------------------------------------------------
    def u8(self, value: int) -> None:
        self.buffer += struct.pack("<B", value & 0xFF)

    def i8(self, value: int) -> None:
        self.buffer += struct.pack("<b", _signed(value, 8))

    def u16(self, value: int) -> None:
        self.buffer += struct.pack("<H", value & 0xFFFF)

    def i16(self, value: int) -> None:
        self.buffer += struct.pack("<h", _signed(value, 16))

    def u32(self, value: int) -> None:
        self.buffer += struct.pack("<I", value & 0xFFFFFFFF)

    def i32(self, value: int) -> None:
        self.buffer += struct.pack("<i", _signed(value, 32))

    def u64(self, value: int) -> None:
        self.buffer += struct.pack("<Q", value & 0xFFFFFFFFFFFFFFFF)

    def i64(self, value: int) -> None:
        self.buffer += struct.pack("<q", _signed(value, 64))

    def f32(self, value: float) -> None:
        self.buffer += struct.pack("<f", value)

    def f64(self, value: float) -> None:
        self.buffer += struct.pack("<d", value)

    def raw(self, data: bytes) -> None:
        self.buffer += data

    # -- strings --------------------------------------------------------
    def cstring(self, value: str, encoding: str, size: int) -> None:
        """Encode into a fixed size buffer, truncating or zero padding."""

        encoded = value.encode(encoding, "replace")
        if len(encoded) < size:
            encoded += b"\0" * (size - len(encoded))
        self.buffer += encoded[:size]

    def wstring(self, value: str, chars: int) -> None:
        self.cstring(value, UTF16, chars * 2)

    def zstring(self, value: str, encoding: str, size: int) -> None:
        """Encode a ``ReadZString`` field (NUL terminated, padded to *size*)."""

        encoded = value.encode(encoding, "replace") + b"\0" * (4 if encoding == UTF16 else 2)
        if len(encoded) < size:
            encoded += b"\0" * (size - len(encoded))
        self.buffer += encoded[:size]


def _signed(value: int, bits: int) -> int:
    mask = 1 << bits
    value &= mask - 1
    return value - mask if value >= (mask >> 1) else value


def encode_blob(data: bytes) -> str:
    """Raw byte fields are stored as base64, like the original XML converter."""

    return base64.b64encode(data).decode("ascii")


def decode_blob(text: str, size: int | None = None) -> bytes:
    data = base64.b64decode(text or "")
    if size is not None:
        if len(data) < size:
            data += b"\0" * (size - len(data))
        data = data[:size]
    return data


def encode_count(value: int) -> int:
    """Validate a record count read from the file."""

    if value < 0:
        raise FormatError(f"negative record count ({value})")
    return value

