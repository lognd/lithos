"""Golden corpus: WO-15 -- the compiler's structural output over
`examples/` is committed as data and must not drift silently.

Drives the facade only (`regolith.compiler.check`, AD-4/AD-11
placement), extracts the stable slice of `BuildOutcome.payload_json`
(see `_util.stable_snapshot`), and compares it to a committed JSON
file under `tests/golden/data/`. The property under test is
DETERMINISM and STABILITY -- not that the corpus is warning-free; the
WO-19 STATUS note records the pipeline as PARTIAL (resolutions=0,
~984 over-reported diagnostics on cubesat) and this suite captures
that noisy-but-deterministic state verbatim as golden.

Regeneration: never hand-edit a golden file. Run
`REGOLITH_UPDATE_GOLDEN=1 pytest tests/golden/test_golden_corpus.py`
to rewrite them from the current compiler output, then diff-review
the change like any other generated artifact (schema-drift style,
AD-11).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from regolith import compiler

from ._util import stable_snapshot

_DATA_DIR = Path(__file__).parent / "data"

# name -> paths passed to `compiler.check`. Kept small and cheap
# (AD-11: golden corpus runs in the default `make check` gate) --
# one multi-file session (cubesat) plus a couple of single-file
# examples across both languages.
_CORPUS: dict[str, tuple[str, ...]] = {
    "cubesat": ("examples/cubesat",),
    "gear_reducer": ("examples/mech/gear_reducer.hem",),
    "buck_converter": ("examples/elec/buck_converter.cupr",),
}


def _golden_path(name: str) -> Path:
    return _DATA_DIR / f"{name}.json"


def _run_snapshot(paths: tuple[str, ...]) -> dict[str, object]:
    result = compiler.check(paths)
    assert result.is_ok, f"check({paths!r}) returned Err: {result}"
    outcome = result.danger_ok
    return stable_snapshot(outcome.payload_json)


@pytest.mark.parametrize("name", sorted(_CORPUS))
def test_golden_corpus(name: str) -> None:
    """Current stable output for one corpus member matches its golden file."""
    snapshot = _run_snapshot(_CORPUS[name])
    golden_path = _golden_path(name)

    if os.environ.get("REGOLITH_UPDATE_GOLDEN") == "1":
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
        pytest.skip(f"REGOLITH_UPDATE_GOLDEN=1: rewrote {golden_path}")

    assert golden_path.exists(), (
        f"no golden file at {golden_path}; regenerate with REGOLITH_UPDATE_GOLDEN=1"
    )
    expected = json.loads(golden_path.read_text())
    assert snapshot == expected, (
        f"golden drift for {name!r} -- if this is an intended compiler "
        "change, regenerate with REGOLITH_UPDATE_GOLDEN=1 and review the diff"
    )


@pytest.mark.parametrize("name", sorted(_CORPUS))
def test_golden_corpus_is_deterministic(name: str) -> None:
    """Two independent `check()` calls over the same corpus member agree
    on the stable snapshot (a narrower, per-member INV-10 sanity check;
    the full-payload byte-identity assertion lives in
    `tests/invariants/test_inv_10_reproducibility.py`)."""
    first = _run_snapshot(_CORPUS[name])
    second = _run_snapshot(_CORPUS[name])
    assert first == second
