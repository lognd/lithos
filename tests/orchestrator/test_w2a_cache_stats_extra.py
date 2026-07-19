"""Direct unit coverage for the pure counter-advance methods on the
orchestrator's two content-addressed caches (`EvidenceStore`/`CacheStats`
in `cache.py`, `NogoodStats` in `nogood_cache.py`). The wiring-level tests
(`test_orchestrator.py`, `test_nogood_cache.py`) exercise these
transitively through real cache hits/misses; this file isolates the
frozen-copy arithmetic itself (W2a frob-adoption sweep, TEST001).
"""

from __future__ import annotations

from regolith.orchestrator.cache import CacheStats, EvidenceStore
from regolith.orchestrator.nogood_cache import NogoodStats


# frob:tests python/regolith/orchestrator/cache.py::CacheStats.with_hit
def test_cache_stats_with_hit_advances_only_hits() -> None:
    """A copy from `with_hit()` bumps hits and leaves misses/the original alone."""
    stats = CacheStats(hits=1, misses=2)
    advanced = stats.with_hit()
    assert advanced.hits == 2
    assert advanced.misses == 2
    # frozen: the original is untouched
    assert stats.hits == 1


# frob:tests python/regolith/orchestrator/cache.py::CacheStats.with_miss
def test_cache_stats_with_miss_advances_only_misses() -> None:
    """A copy from `with_miss()` bumps misses and leaves hits alone."""
    stats = CacheStats(hits=1, misses=2)
    advanced = stats.with_miss()
    assert advanced.hits == 1
    assert advanced.misses == 3


# frob:tests python/regolith/orchestrator/cache.py::EvidenceStore.as_dict
def test_evidence_store_as_dict_is_sorted_key_snapshot() -> None:
    """`as_dict()` returns entries sorted by key, a deterministic snapshot."""
    store = EvidenceStore(entries={"b": "evidence-b", "a": "evidence-a"})  # type: ignore[arg-type]
    snapshot = store.as_dict()
    assert list(snapshot.keys()) == ["a", "b"]
    assert snapshot == {"a": "evidence-a", "b": "evidence-b"}


# frob:tests python/regolith/orchestrator/nogood_cache.py::NogoodStats.with_hit
# frob:tests python/regolith/orchestrator/nogood_cache.py::NogoodStats.with_miss
# frob:tests python/regolith/orchestrator/nogood_cache.py::NogoodStats.with_store
def test_nogood_stats_with_hit_miss_store_are_independent() -> None:
    """Each `with_*` advances exactly its own counter, off a shared base."""
    stats = NogoodStats()
    hit = stats.with_hit()
    miss = stats.with_miss()
    stored = stats.with_store()
    assert (hit.hits, hit.misses, hit.stores) == (1, 0, 0)
    assert (miss.hits, miss.misses, miss.stores) == (0, 1, 0)
    assert (stored.hits, stored.misses, stored.stores) == (0, 0, 1)
