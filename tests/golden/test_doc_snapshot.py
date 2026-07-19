"""`regolith doc` snapshot: WO-41 deliverable 2 -- rendered markdown
over the cubesat corpus package is committed as data and must not
drift silently.

Regeneration: never hand-edit. Run
`REGOLITH_UPDATE_GOLDEN=1 pytest tests/golden/test_doc_snapshot.py`
to rewrite it from the current renderer, then diff-review like any
other generated artifact (schema-drift style, AD-11).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from regolith.docgen import extract_package, render_markdown

_GOLDEN_PATH = Path(__file__).parent / "data" / "doc_cubesat.md"


def _render() -> str:
    extracted = extract_package(("examples/flagships/cubesat",))
    assert extracted.is_ok, f"extract_package returned Err: {extracted}"
    # No `.regolith/` for this package in the repo (build artifacts are
    # gitignored), so every claim renders "(unbuilt)" -- the acceptance
    # criterion's no-error-on-missing-artifacts path, exercised as the
    # committed golden.
    return render_markdown(extracted.danger_ok)


# frob:tests python/regolith/docgen/extract.py::extract_package
def test_doc_snapshot_matches_golden() -> None:
    rendered = _render()

    if os.environ.get("REGOLITH_UPDATE_GOLDEN") == "1":
        _GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        _GOLDEN_PATH.write_text(rendered)
        pytest.skip(f"REGOLITH_UPDATE_GOLDEN=1: rewrote {_GOLDEN_PATH}")

    assert _GOLDEN_PATH.exists(), (
        f"no golden file at {_GOLDEN_PATH}; regenerate with REGOLITH_UPDATE_GOLDEN=1"
    )
    expected = _GOLDEN_PATH.read_text()
    assert rendered == expected, (
        "doc snapshot drift for cubesat -- if this is an intended docgen "
        "change, regenerate with REGOLITH_UPDATE_GOLDEN=1 and review the diff"
    )


def test_doc_rendering_is_byte_identical_across_runs() -> None:
    assert _render() == _render()
