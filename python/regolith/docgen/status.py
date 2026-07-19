"""Claim build status for ``regolith doc`` (WO-41): reads-only, never
runs the harness. When ``<project_root>/.regolith/`` is absent every
claim renders ``(unbuilt)`` (no error); when present, a fresh static
``compiler.check`` re-derives the (deterministic, content-addressed)
obligation list and each named obligation is looked up in the
persisted evidence cache (a previous ``regolith build --persist`` run)
-- no live discharge, no solver invocation.

Matching is by the claim's own optional ``name`` (the claim line's
subject, e.g. ``rail_stress:``); a package that reuses one claim name
across multiple declarations gets the same status text on each -- a
documented best-effort simplification (see design-log D127), not a
full per-declaration obligation graph.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

from regolith import compiler
from regolith._schema.models import Obligation
from regolith.harness import MODEL_REGISTRY_VERSION
from regolith.logging_setup import get_logger
from regolith.orchestrator.cache import EvidenceStore, obligation_cache_key

_log = get_logger(__name__)

# frob:doc docs/modules/py-docgen.md#status
UNBUILT = "(unbuilt)"


def _bits_to_float(bits: int) -> float:
    """Decode an ``Evidence`` f64-as-bits field back to a float."""
    return struct.unpack("<d", struct.pack("<Q", bits))[0]


# frob:doc docs/modules/py-docgen.md#status
# frob:waive TEST001 reason="docgen helper, tested transitively via render tests"
def claim_statuses(project_root: str, paths: tuple[str, ...]) -> dict[str, str]:
    """Map claim name -> rendered ``"status (margin=...)"`` for every
    named, cached obligation; empty when unbuilt or on any failure
    (never raises -- a missing/corrupt cache just means "(unbuilt)")."""
    regolith_dir = Path(project_root) / ".regolith"
    if not regolith_dir.is_dir():
        _log.info("doc: no .regolith/ at %s; claims render (unbuilt)", project_root)
        return {}

    store_result = EvidenceStore.load(project_root)
    if store_result.is_err:
        _log.warning(
            "doc: evidence cache unreadable at %s: %s; claims render (unbuilt)",
            project_root,
            store_result.danger_err.message,
        )
        return {}
    store = store_result.danger_ok

    outcome = compiler.check(paths)
    if outcome.is_err:
        _log.warning(
            "doc: check failed while resolving claim status: %s",
            outcome.danger_err.message,
        )
        return {}
    payload = json.loads(outcome.danger_ok.payload_json)
    obligations = [Obligation.model_validate(o) for o in payload.get("obligations", [])]

    statuses: dict[str, str] = {}
    for obligation in obligations:
        name = obligation.claim.name
        if not name:
            continue
        key = obligation_cache_key(obligation, MODEL_REGISTRY_VERSION)
        evidence = store.get(key)
        if evidence is None:
            continue
        margin = _bits_to_float(evidence.margin_bits)
        statuses[name] = f"{evidence.status} (margin={margin:.3g})"
    _log.info("doc: resolved %d claim status(es)", len(statuses))
    return statuses
