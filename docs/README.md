# Documentation

`binconv` converts the DMO client's binary tables to JSON and back, and rebuilds
the `Pack03` pack. The [README](../README.md) has the commands; the pages here
explain how it works and why it is built that way.

## If you want to change game data

1. [Getting started](getting-started.md) — get from a retail install to a rebuilt pack.
2. [Modding](modding.md) — what can be changed, what to watch out for, and how to
   prove the client accepts the result.

## If you want to understand or extend a table

1. [JSON layout](json-schema.md) — one folder per table, one file per section.
2. [Supported formats](formats.md) — the table list with layouts and quirks.
3. [What the DMO client expects](client-notes.md) — which manager reads which file,
   and how a layout is read out of the client code.
4. [Naming](naming.md) — how JSON keys are chosen.

## If you want to know how much to trust it

* [Validation](validation.md) — the round-trip and pack checks, per file numbers.
* [The pack files](pack-format.md) — the `.pf`/`.hf` format, including the three
  things in the retail pair that cannot be reproduced.
* [Development helpers](tools.md) — the scripts that do the checking.
* [The original converter](legacy-converter.md) — where the format knowledge came
  from and which of its bugs are worked around.

## Terminology

| term | meaning |
|---|---|
| **retail install** | your own copy of the game; this repo stores no game data |
| **table** / **format** | one `.bin` file, e.g. `ItemList`, and its codec |
| **section** | one logical list inside a table, stored as one JSON file |
| **codec** | the Python class that reads and writes one table (`binconv/formats/`) |
| **pack** | `Pack03.pf` (payload) + `Pack03.hf` (index) — how the client ships tables |
| **blob** | a table with no codec, copied verbatim (`blob/NewTutorial.bin`) |
