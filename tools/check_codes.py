"""Print the exit code of every documented XML check (debug helper).

    python tools/check_codes.py --xml-dir DMO_XML_DIR --ref-dir GENERATED_XML_DIR

Checks whose tree is not supplied are reported as ``skip``.
"""

import argparse
import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import compare_xml as c  # noqa: E402

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
parser.add_argument("--xml-dir", type=Path)
parser.add_argument("--ref-dir", type=Path)
args = parser.parse_args()
trees = {key: value for key, value in
         (("xml", args.xml_dir), ("ref", args.ref_dir)) if value is not None}

for name in c.check_names():
    for check in c.CHECKS[name]:
        tree, _, relative = check.path.partition("/")
        base = trees.get(tree)
        if base is None or not (base / relative).exists():
            print(f"{name:14} {check.path:46} skip")
            continue
        target = base / relative
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            folder = args.root / "json" / (check.folder or name)
            if check.section is None:
                code = c.scan(
                    folder, target, 10, check.nested, check.ignore,
                    check.alias, check.exclude,
                )
            else:
                code = c.compare(
                    folder, target, check.section, None, 10,
                    check.nested, check.ignore, check.alias,
                )
        print(f"{name:14} {check.path:46} rc={code} known={bool(check.known)}")
