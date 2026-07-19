"""Cross-run nogood cache (cuprite/08 EOPEN-13, D75).

Spec: D75 -- learned nogoods are per-run solver state in v1; cross-run
reuse is sound iff the cache key includes every catalog record
revision the nogood's blame set consumed. These tests exercise the
persistence layer directly (:mod:`regolith.orchestrator.nogood_cache`)
and its wiring into `regolith.realizer.elec.binding.bind_all`: a
second run over an UNCHANGED catalog must hit the cache (observable via
`NogoodCache.stats`/logs) and skip re-deriving the nogood; mutating a
blamed record's content hash must invalidate the entry.
"""

from __future__ import annotations

from regolith.orchestrator.nogood_cache import (
    BlamedRecord,
    NogoodCache,
    nogood_cache_key,
)
from regolith.realizer.elec.binding import (
    BlockRequirement,
    Budget,
    ComponentCandidate,
    bind_all,
)


def _rigged_fixture(mcu_hungry_hash: str = "sha256:11"):
    """The WO-24 rigged-nogood fixture, parameterized on one blamed hash."""
    requirements = [
        BlockRequirement(block="mcu", min_capabilities={}),
        BlockRequirement(block="radio", min_capabilities={}),
    ]
    candidates = {
        "mcu": [
            ComponentCandidate(
                record_key="mcu/hungry@1",
                content_hash=mcu_hungry_hash,
                capabilities={"power_mw": 500},
                cost=1,
            ),
            ComponentCandidate(
                record_key="mcu/frugal@1",
                content_hash="sha256:22",
                capabilities={"power_mw": 100},
                cost=2,
            ),
        ],
        "radio": [
            ComponentCandidate(
                record_key="radio/only@1",
                content_hash="sha256:33",
                capabilities={"power_mw": 200},
                cost=1,
            ),
        ],
    }
    budgets = [Budget(capability="power_mw", limit=400)]
    return requirements, candidates, budgets


# --- key soundness ---------------------------------------------------------


# frob:tests python/regolith/orchestrator/nogood_cache.py::nogood_cache_key
def test_nogood_key_deterministic() -> None:
    blamed = (BlamedRecord(record_key="mcu/hungry@1", content_hash="sha256:11"),)
    k1 = nogood_cache_key("mcu", "mcu/hungry@1", blamed, (("power_mw", 400.0),))
    k2 = nogood_cache_key("mcu", "mcu/hungry@1", blamed, (("power_mw", 400.0),))
    assert k1 == k2


def test_nogood_key_changes_when_blamed_hash_changes() -> None:
    """A blamed record's content hash changing (new revision) is a new key.

    This IS the soundness condition (D75): the key is a pure function
    of the blame set's content, so a mutated record never collides
    with the stale key.
    """
    blamed_before = (BlamedRecord(record_key="mcu/hungry@1", content_hash="sha256:11"),)
    blamed_after = (BlamedRecord(record_key="mcu/hungry@1", content_hash="sha256:99"),)
    k1 = nogood_cache_key("mcu", "mcu/hungry@1", blamed_before, (("power_mw", 400.0),))
    k2 = nogood_cache_key("mcu", "mcu/hungry@1", blamed_after, (("power_mw", 400.0),))
    assert k1 != k2


# --- cache membership/persistence ------------------------------------------


def test_nogood_cache_hit_miss_stats() -> None:
    cache = NogoodCache()
    key = nogood_cache_key(
        "mcu",
        "mcu/hungry@1",
        (BlamedRecord(record_key="radio/only@1", content_hash="sha256:33"),),
        (("power_mw", 400.0),),
    )
    assert cache.get(key) is False
    assert cache.stats.misses == 1
    cache.put(key)
    assert cache.get(key) is True
    assert cache.stats.hits == 1


def test_nogood_cache_persist_round_trip(tmp_path) -> None:
    cache = NogoodCache()
    key = nogood_cache_key("mcu", "mcu/hungry@1", (), (("power_mw", 400.0),))
    cache.put(key)
    assert cache.save(str(tmp_path)).is_ok
    reloaded = NogoodCache.load(str(tmp_path)).danger_ok
    assert reloaded.get(key) is True


def test_nogood_cache_missing_file_is_empty(tmp_path) -> None:
    reloaded = NogoodCache.load(str(tmp_path)).danger_ok
    assert reloaded.get("blake3:nonexistent") is False


def test_nogood_cache_corrupt_file_is_err(tmp_path) -> None:
    path = NogoodCache.cache_path(str(tmp_path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not json{{{", encoding="ascii")
    result = NogoodCache.load(str(tmp_path))
    assert result.is_err
    assert result.danger_err.kind == "corrupt_cache"


# --- solver-level soundness (bind_all wired to a persisted cache) ---------


def test_bind_all_reuses_nogood_across_runs(tmp_path) -> None:
    """Run 1 derives+stores a nogood; run 2 (unchanged catalog) hits it."""
    requirements, candidates, budgets = _rigged_fixture()

    cache_run1 = NogoodCache.load(str(tmp_path)).danger_ok
    result1 = bind_all(requirements, candidates, budgets, nogood_cache=cache_run1)
    assert result1.is_ok, result1.danger_err
    assert cache_run1.stats.stores == 1
    assert cache_run1.stats.hits == 0
    assert cache_run1.save(str(tmp_path)).is_ok

    cache_run2 = NogoodCache.load(str(tmp_path)).danger_ok
    result2 = bind_all(requirements, candidates, budgets, nogood_cache=cache_run2)
    assert result2.is_ok, result2.danger_err
    # Same feasible outcome, but this time the mcu/hungry+radio/only
    # nogood was a cache HIT -- the search never re-derived it via
    # `_budget_ok` for that trial (other, non-violating trials still
    # get checked and correctly miss -- they were never nogoods).
    assert cache_run2.stats.hits == 1
    assert cache_run2.stats.stores == 0  # nothing NEW learned this run
    pins = {p.block: p.record_key for p in result2.danger_ok.pins}
    assert pins["mcu"] == "mcu/frugal@1"
    assert pins["radio"] == "radio/only@1"


def test_bind_all_invalidates_nogood_when_blamed_record_mutates(tmp_path) -> None:
    """Mutating a blamed record's content hash forces re-derivation, not a stale hit."""
    requirements, candidates, budgets = _rigged_fixture(mcu_hungry_hash="sha256:11")

    cache_run1 = NogoodCache.load(str(tmp_path)).danger_ok
    bind_all(requirements, candidates, budgets, nogood_cache=cache_run1)
    assert cache_run1.save(str(tmp_path)).is_ok

    # "mcu/hungry" gets a new revision body (new content hash) -- the
    # blamed record changed, so the stale cache entry must NOT apply.
    mutated_requirements, mutated_candidates, mutated_budgets = _rigged_fixture(
        mcu_hungry_hash="sha256:changed"
    )
    cache_run2 = NogoodCache.load(str(tmp_path)).danger_ok
    result2 = bind_all(
        mutated_requirements,
        mutated_candidates,
        mutated_budgets,
        nogood_cache=cache_run2,
    )
    assert result2.is_ok, result2.danger_err
    # A fresh derivation (a miss + a fresh store for the mutated trial),
    # never a stale hit reused from the pre-mutation catalog.
    assert cache_run2.stats.hits == 0
    assert cache_run2.stats.stores == 1
