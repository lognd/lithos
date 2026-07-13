"""Derived-BOM corpus golden (WO-101 residual, F124 bundle): the derived
BOM rows for three flagship corpora -- cnc_router_r1, timber_pavilion,
espresso_machine -- frozen as data.

Each corpus is built at the tier it actually builds today
(`compiler.check`, the fast structural tier the deferral golden also uses):
its real `FramePayload`/`FlownetPayload` off the build payload feeds
`derive_bom_rows`, so the golden locks the DERIVATION over the real design
graph (frame members + flownet fittings), not a synthetic fixture. Mech
part rows (which need realized geometry, a heavier tier) are honestly
absent at this tier -- the row set here is exactly what the check-tier
graph yields, and a change to it (more rows, a lost row, a changed
identity) is a reviewed golden diff.

Regeneration: never hand-edit. Run
`REGOLITH_UPDATE_GOLDEN=1 pytest tests/golden/test_bom_corpus.py`
and diff-review the change like any other generated artifact.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from regolith import compiler
from regolith._schema.models import FlownetPayload, FramePayload
from regolith.backends.artifacts import NativeArtifactStore
from regolith.backends.bom import derive_bom_rows
from regolith.backends.framework import BackendInputs
from regolith.orchestrator.lockfile import Lockfile

_DATA_DIR = Path(__file__).parent / "data"

_CORPUS: dict[str, str] = {
    "cnc_router_r1": "examples/flagships/cnc_router_r1",
    "timber_pavilion": "examples/flagships/timber_pavilion",
    "espresso_machine": "examples/flagships/espresso_machine",
}


def _golden_path(name: str) -> Path:
    return _DATA_DIR / f"bom_{name}.json"


def _bom_projection(path: str, tmp_root: Path) -> list[dict[str, object]]:
    """Derive the BOM for one corpus and project each row to its stable
    identity fields (subject/kind/quantity/sourced), sorted."""
    result = compiler.check((path,))
    assert result.is_ok, f"check({path!r}) failed: {result}"
    payload = json.loads(result.danger_ok.payload_json)
    frames = {
        name: FramePayload.model_validate(raw)
        for name, raw in (payload.get("frames") or {}).items()
    }
    flownets = {
        name: FlownetPayload.model_validate(raw)
        for name, raw in (payload.get("flownets") or {}).items()
    }
    inputs = BackendInputs(
        lockfile=Lockfile(tool_version="0.1.0"),
        evidence={},
        geometry={},
        layouts={},
        native=NativeArtifactStore(str(tmp_root)),
        frames=frames,
        flownets=flownets,
    )
    model = derive_bom_rows(inputs)
    rows = [
        {
            "subject": row.subject,
            "kind": row.kind,
            "quantity": row.quantity,
            "unsourced": row.unsourced,
        }
        for row in model.rows
    ]
    rows.sort(key=lambda r: (str(r["kind"]), str(r["subject"])))
    return rows


@pytest.mark.parametrize("name", sorted(_CORPUS))
def test_bom_corpus(name: str, tmp_path) -> None:
    """The derived BOM row set for one corpus matches its golden."""
    snapshot = _bom_projection(_CORPUS[name], tmp_path)
    golden_path = _golden_path(name)

    if os.environ.get("REGOLITH_UPDATE_GOLDEN") == "1":
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
        pytest.skip(f"REGOLITH_UPDATE_GOLDEN=1: rewrote {golden_path}")

    assert golden_path.exists(), (
        f"no golden at {golden_path}; regenerate with REGOLITH_UPDATE_GOLDEN=1"
    )
    expected = json.loads(golden_path.read_text())
    assert snapshot == expected, (
        f"BOM-derivation drift for {name!r} -- if intended, regenerate with "
        "REGOLITH_UPDATE_GOLDEN=1 and review the diff"
    )
