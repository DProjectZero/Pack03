"""Print the exit code of every documented XML check (debug helper)."""

import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import compare_xml as c  # noqa: E402

root = Path(__file__).resolve().parents[1]
for name in c.check_names():
    for check in c.CHECKS[name]:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            folder = root / "json" / (check.folder or name)
            if check.section is None:
                code = c.scan(
                    folder, root / check.path, 10, check.nested, check.ignore,
                    check.alias, check.exclude,
                )
            else:
                code = c.compare(
                    folder, root / check.path, check.section, None, 10,
                    check.nested, check.ignore, check.alias,
                )
        print(f"{name:14} {check.path:46} rc={code} known={bool(check.known)}")
