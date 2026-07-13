"""WO-108: the proof-pack completeness + determinism gate.

A fleet-gate-style test over the `demos/` optimization proof packs. For
every demo it asserts:

* **completeness** -- every artifact row in `manifest.json` names a file
  that exists on disk whose bytes hash to the recorded `sha256`; each
  live demo carries at least one artifact and a `PROOF.md` naming its
  cause row.
* **determinism** -- running the demo twice yields, for every artifact
  flagged `deterministic`, the SAME content hash (two runs byte-identical
  for deterministic formats, the WO-108 rule).
* **honest gaps** -- a not-live demo records `live=False` with zero
  artifacts and a gap PROOF.md (never a fabricated artifact).

Each demo runs the REAL pipeline, so this test is heavier than a unit
test; it is the standing "is every optimization still proven" bar (the
`demos` leg of WO-106's `make health`, D219).
"""

from __future__ import annotations

import hashlib
import importlib

import pytest

from demos.harness import MANIFEST_NAME, OUT_ROOT, PROOF_NAME, Manifest
from demos.run_all import DEMOS


def _run(name: str) -> Manifest:
    module = importlib.import_module(f"demos.{name}")
    module.run()
    manifest_path = OUT_ROOT / name / MANIFEST_NAME
    return Manifest.model_validate_json(manifest_path.read_bytes())


@pytest.mark.parametrize("name", DEMOS)
def test_demo_manifest_is_complete_and_deterministic(name: str) -> None:
    first = _run(name)
    second = _run(name)

    out_dir = OUT_ROOT / name

    # Honest-gap invariant: not-live => no artifacts, gap PROOF present.
    if not first.live:
        assert first.artifacts == (), f"{name}: a not-live demo emitted artifacts"
        assert first.live == second.live
        proof = (out_dir / PROOF_NAME).read_text()
        assert "NOT LIVE" in proof, f"{name}: gap PROOF must say NOT LIVE"
        assert "GAP" in proof
        return

    # Completeness: every recorded artifact exists and hashes as claimed.
    assert first.artifacts, f"{name}: a live demo emitted no artifacts"
    for row in first.artifacts:
        path = out_dir / row.path
        assert path.is_file(), f"{name}: manifest names missing file {row.path}"
        data = path.read_bytes()
        assert len(data) == row.bytes, f"{name}: size drift on {row.path}"
        digest = "sha256:" + hashlib.sha256(data).hexdigest()
        assert digest == row.sha256, f"{name}: hash drift on {row.path}"

    # PROOF.md present and cites the cause row verbatim (the authoritative
    # pin); the manifest's cause_row is the `cause: optimize(...)` line.
    proof = (out_dir / PROOF_NAME).read_text()
    assert "cause:" in first.cause_row, f"{name}: cause_row missing the cause pin"
    assert first.cause_row in proof, f"{name}: PROOF.md must embed the cause row"

    # Determinism: for every deterministic-flagged artifact, the two runs
    # produced the SAME content hash (byte-identical output).
    first_by_path = {r.path: r for r in first.artifacts}
    second_by_path = {r.path: r for r in second.artifacts}
    assert set(first_by_path) == set(second_by_path), f"{name}: artifact set drifted"
    for path, row in first_by_path.items():
        if row.deterministic:
            assert row.sha256 == second_by_path[path].sha256, (
                f"{name}: nondeterministic output for deterministic artifact {path}"
            )
