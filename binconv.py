#!/usr/bin/env python3
"""``binconv`` - convert the game's ``.bin`` tables to JSON and back.

Examples
--------
``python binconv.py decompile``
    Read every supported ``bin/*.bin`` and write ``json/<name>.json``
    (each file is verified by re-encoding it in memory).

``python binconv.py compile``
    Read every ``json/*.json`` and write ``bin_out/<name>.bin``.

``python binconv.py decompile --src PROGRAM/DATA --out json --pretty``
    Point the tool at the original data folder and indent the JSON.
"""

from __future__ import annotations

import sys

from binconv.cli import main

if __name__ == "__main__":
    sys.exit(main())
