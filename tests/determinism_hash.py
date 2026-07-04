"""Emit ONE hash over the golden corpus build output (AD-6 CI job).

The 3-OS determinism matrix runs this on linux/macos/windows and asserts
the printed hash is byte-identical everywhere: same source + same
lockfile rows + same obligation keys => same bytes, or the build is red
(INV-10/INV-21/INV-22). It reuses the golden suite's `stable_snapshot`
so "what is hashed" stays single-sourced with the golden tests.

stdout is data (the hash line); this is a CI helper, not a test.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from regolith import compiler  # noqa: E402

from tests.golden._util import stable_snapshot  # noqa: E402

# The same corpus the golden suite pins; a multi-file session plus one
# file per language exercises cross-file resolution and both front-ends.
_CORPUS: dict[str, tuple[str, ...]] = {
    "cubesat": ("examples/cubesat",),
    "gear_reducer": ("examples/mech/gear_reducer.hem",),
    "buck_converter": ("examples/elec/buck_converter.cupr",),
}


def main() -> int:
    """Print a single deterministic hash over the whole corpus snapshot."""
    combined: dict[str, object] = {}
    for name in sorted(_CORPUS):
        result = compiler.check(_CORPUS[name])
        if not result.is_ok:
            print(f"ERROR check({name}) returned Err: {result}", file=sys.stderr)
            return 1
        combined[name] = stable_snapshot(result.danger_ok.payload_json)

    encoded = json.dumps(combined, sort_keys=True, ensure_ascii=True).encode("ascii")
    print(hashlib.sha256(encoded).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
