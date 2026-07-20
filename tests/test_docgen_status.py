"""Tests for `regolith.docgen.status.claim_statuses` (T-0036 backfill):
every early-return branch (no `.regolith/`, unreadable evidence cache,
failing `compiler.check`), the per-obligation skip branches (unnamed
claim, cache miss), and the happy path that formats a cached hit as
`"status (margin=...)"`. Also covers the pure `_bits_to_float` helper
directly.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from regolith import compiler
from regolith._schema.models import Coverage, Evidence, Obligation, Status1
from regolith.docgen import status as status_mod
from regolith.errors import OrchestratorError
from regolith.harness import MODEL_REGISTRY_VERSION
from regolith.harness.quantity import bits_to_f64, f64_to_bits
from regolith.orchestrator.cache import EvidenceStore, obligation_cache_key
from typani.result import Err

_FIXTURE = (
    Path(__file__).parent
    / "orchestrator"
    / "data"
    / "wo109_cantilever_deflection_fixture.hema"
)


# frob:ticket T-0036
def _obligations() -> list[Obligation]:
    """Real, compiler-derived obligations from the shared WO-109 fixture."""
    result = compiler.check((str(_FIXTURE),))
    assert result.is_ok, f"check({_FIXTURE!r}) returned Err: {result}"
    import json

    payload = json.loads(result.danger_ok.payload_json)
    return [Obligation.model_validate(raw) for raw in payload["obligations"]]


# frob:ticket T-0036
def _evidence(status: object = Status1.discharged, *, margin: float = 2.5) -> Evidence:
    """A minimal, otherwise-inert `Evidence` row for cache round-trips."""
    return Evidence(
        cost=0,
        coverage=Coverage(fraction_bits=f64_to_bits(1.0), axes=[]),
        eps_bits=0,
        hash="blake3:test-evidence",
        margin_bits=f64_to_bits(margin),
        model_id="test.model",
        status=status,
        value_bits=0,
    )


# frob:tests python/regolith/docgen/status.py::claim_statuses kind="unit"
# frob:ticket T-0036
def test_claim_statuses_empty_when_no_regolith_dir(tmp_path: Path) -> None:
    """No `.regolith/` at all renders every claim `(unbuilt)` (no error)."""
    assert status_mod.claim_statuses(str(tmp_path), (str(_FIXTURE),)) == {}


# frob:tests python/regolith/docgen/status.py::claim_statuses kind="unit"
# frob:ticket T-0036
def test_claim_statuses_empty_when_evidence_cache_unreadable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A corrupt/unreadable evidence cache is an `Err` -> empty, not raised."""
    (tmp_path / ".regolith").mkdir()

    def _fake_load(_project_root: str) -> object:
        return Err(OrchestratorError(kind="corrupt_cache", message="boom"))

    monkeypatch.setattr(
        EvidenceStore, "load", classmethod(lambda cls, root: _fake_load(root))
    )
    assert status_mod.claim_statuses(str(tmp_path), (str(_FIXTURE),)) == {}


# frob:tests python/regolith/docgen/status.py::claim_statuses kind="unit"
# frob:ticket T-0036
def test_claim_statuses_empty_when_compiler_check_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failing `compiler.check` (CoreFailure `Err`) renders `{}`, not raised."""
    (tmp_path / ".regolith").mkdir()

    class _FakeFailure:
        message = "simulated compiler failure"

    def _fake_check(*_args: object, **_kwargs: object) -> object:
        return Err(_FakeFailure())

    monkeypatch.setattr(status_mod.compiler, "check", _fake_check)
    assert status_mod.claim_statuses(str(tmp_path), (str(_FIXTURE),)) == {}


# frob:tests python/regolith/docgen/status.py::claim_statuses kind="unit"
# frob:ticket T-0036
def test_claim_statuses_happy_path_formats_cached_hit(tmp_path: Path) -> None:
    """A cached hit for a named claim renders `"status (margin=...)"`; an
    unnamed claim and a cache miss are silently skipped (not errors)."""
    (tmp_path / ".regolith").mkdir()

    obligations = _obligations()
    named = [o for o in obligations if o.claim.name]
    assert named, "fixture must carry at least one named claim"

    # Cache a hit for exactly the first named obligation; leave every
    # other named obligation as a deliberate cache MISS (skip branch).
    target = named[0]
    key = obligation_cache_key(target, MODEL_REGISTRY_VERSION)
    evidence = _evidence(Status1.discharged, margin=1.25)
    store = EvidenceStore()
    store.put(key, evidence)
    save_result = store.save(str(tmp_path))
    assert save_result.is_ok, save_result

    statuses = status_mod.claim_statuses(str(tmp_path), (str(_FIXTURE),))

    assert target.claim.name in statuses
    expected_margin = bits_to_f64(evidence.margin_bits)
    assert statuses[target.claim.name] == f"discharged (margin={expected_margin:.3g})"
    # Any other named-but-uncached claim never appears (cache-miss skip).
    for other in named[1:]:
        assert other.claim.name is not None
        if other.claim.name != target.claim.name:
            assert other.claim.name not in statuses


# frob:tests python/regolith/docgen/status.py::claim_statuses kind="unit"
# frob:ticket T-0036
def test_claim_statuses_skips_unnamed_claim(tmp_path: Path) -> None:
    """An obligation whose claim has no `name` is skipped even when a
    cache entry exists for every key the real obligations would use --
    the loop only ever looks up NAMED obligations."""
    (tmp_path / ".regolith").mkdir()

    obligations = _obligations()
    unnamed = [o for o in obligations if not o.claim.name]
    if not unnamed:
        pytest.skip("fixture carries no unnamed claim to exercise the skip branch")

    store = EvidenceStore()
    for obligation in obligations:
        key = obligation_cache_key(obligation, MODEL_REGISTRY_VERSION)
        store.put(key, _evidence(Status1.discharged, margin=9.0))
    save_result = store.save(str(tmp_path))
    assert save_result.is_ok, save_result

    statuses = status_mod.claim_statuses(str(tmp_path), (str(_FIXTURE),))
    # Only named claims can ever appear as dict keys -- "" is never a key.
    assert "" not in statuses
    assert None not in statuses


# frob:tests python/regolith/docgen/status.py::_bits_to_float kind="unit"
# frob:ticket T-0036
def test_bits_to_float_round_trips_f64_to_bits() -> None:
    """`_bits_to_float` inverts `f64_to_bits` bit-for-bit (little-endian)."""
    for value in (0.0, 1.0, -2.5, 3.14159, 1e-9, -1e12):
        assert status_mod._bits_to_float(f64_to_bits(value)) == value
