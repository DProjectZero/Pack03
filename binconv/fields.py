"""Declarative field tables for the simple (flat) record layouts.

Most of the original records are a straight sequence of ``reader.ReadX()``
calls.  Describing them as a table keeps the Python codec readable and makes it
obvious where a layout deviates from the C# implementation.

Field specifications
--------------------
``"u32"`` / ``"i16"`` / ``"f32"`` ...  scalar numbers.
``("w", chars)``                       fixed UTF-16 buffer of *chars* characters.
``("c", encoding, size)``              fixed byte buffer (UTF-8/ASCII), NUL trimmed.
``("z", encoding, size)``              ``ReadZString`` field (NUL terminated + pad).
``("blob", size)``                     raw bytes, stored as base64 in JSON.
"""

from __future__ import annotations

from typing import Any, Sequence

from .binary import Reader, Writer, decode_blob, encode_blob, FormatError, UTF16

SCALARS = {
    "u8": (Reader.u8, Writer.u8),
    "i8": (Reader.i8, Writer.i8),
    "u16": (Reader.u16, Writer.u16),
    "i16": (Reader.i16, Writer.i16),
    "u32": (Reader.u32, Writer.u32),
    "i32": (Reader.i32, Writer.i32),
    "u64": (Reader.u64, Writer.u64),
    "i64": (Reader.i64, Writer.i64),
    "f32": (Reader.f32, Writer.f32),
    "f64": (Reader.f64, Writer.f64),
}


def read_fields(reader: Reader, fields: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    record: dict[str, Any] = {}
    for name, spec in fields:
        record[name] = _read_field(reader, spec, f"{reader.name}:{name}")
    return record


def write_fields(writer: Writer, fields: Sequence[tuple[str, Any]], record: dict[str, Any]) -> None:
    for name, spec in fields:
        if name not in record:
            raise FormatError(f"missing required field {name!r}")
        _write_field(writer, spec, record[name], name)


def _read_field(reader: Reader, spec: Any, where: str) -> Any:
    if isinstance(spec, str):
        try:
            getter, _ = SCALARS[spec]
        except KeyError:
            raise FormatError(f"{where}: unknown field type {spec!r}") from None
        return getter(reader)

    kind = spec[0]
    if kind == "w":
        return reader.wstring(spec[1])
    if kind == "c":
        return reader.cstring(spec[1], spec[2])
    if kind == "z":
        return reader.zstring(spec[1], spec[2])
    if kind == "blob":
        return encode_blob(reader.raw(spec[1]))
    raise FormatError(f"{where}: unknown field type {kind!r}")


def _write_field(writer: Writer, spec: Any, value: Any, where: str) -> None:
    if isinstance(spec, str):
        try:
            _, setter = SCALARS[spec]
        except KeyError:
            raise FormatError(f"{where}: unknown field type {spec!r}") from None
        setter(writer, value)
        return

    kind = spec[0]
    if kind == "w":
        writer.wstring(_text(value), spec[1])
    elif kind == "c":
        writer.cstring(_text(value), spec[1], spec[2])
    elif kind == "z":
        writer.zstring(_text(value), spec[1], spec[2])
    elif kind == "blob":
        writer.raw(decode_blob(value, spec[1]))
    else:
        raise FormatError(f"{where}: unknown field type {kind!r}")


def _text(value: Any) -> str:
    return value if isinstance(value, str) else str(value)


def field_size(fields: Sequence[tuple[str, Any]]) -> int | None:
    """Byte size of a field table, or ``None`` when it is not fixed size."""

    total = 0
    for _, spec in fields:
        if isinstance(spec, str):
            sizes = {"u8": 1, "i8": 1, "u16": 2, "i16": 2, "u32": 4, "i32": 4,
                     "u64": 8, "i64": 8, "f32": 4, "f64": 8}
            total += sizes[spec]
        elif spec[0] == "w":
            total += spec[1] * 2
        elif spec[0] in ("c", "z", "blob"):
            total += spec[2] if spec[0] != "blob" else spec[1]
        else:
            return None
    return total

