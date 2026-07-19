"""Shared helpers for the golden-corpus suite (WO-15/WO-17 wiring).

Extracts the STABLE, meaningful slice of a `BuildOutcome.payload_json`
for golden comparison: obligation content-derived keys, snapshot
hashes, and the diagnostic-code multiset. Deliberately excludes
anything that varies by machine or is not yet semantically meaningful
per the WO-19 STATUS note (absolute paths, resolutions/evidence while
they are still empty=0 across the corpus).

The property under test is DETERMINISM/STABILITY of the pipeline's
structural output, not "the diagnostics are clean" -- WO-19 is
recorded PARTIAL (over-reporting diagnostics, resolutions=0) and that
noise is captured verbatim as golden, not filtered to look nicer.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any


def _obligation_key(obligation: dict[str, Any]) -> str:
    """A stable content-derived key for one obligation record.

    Not the Rust `Obligation::content_hash` (that hash is not exposed
    in the JSON payload, WO-19 STATUS: schema surface does not carry
    it yet) -- a sha256 over the obligation's own canonical (sorted
    keys) JSON encoding. Stable across runs given identical input;
    that is all the golden/INV-10 tests need.
    """
    encoded = json.dumps(obligation, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(encoded.encode("ascii")).hexdigest()


def obligation_keys(payload: dict[str, Any]) -> list[str]:
    """Sorted list of stable obligation keys for a parsed payload dict."""
    return sorted(_obligation_key(ob) for ob in payload["obligations"])


def snapshot_hashes(payload: dict[str, Any]) -> list[str]:
    """Sorted list of entity-snapshot content hashes."""
    return sorted(record["hash"] for record in payload["snapshots"])


# frob:waive PERF004 reason="one-shot sort of a small set, never re-sorted"
def diagnostic_multiset(payload: dict[str, Any]) -> list[list[Any]]:
    """Sorted `[code, severity, count]` triples -- the diagnostic-code
    multiset. Spans/messages carry file paths and are excluded (would
    make goldens machine/checkout-path sensitive); the code+severity
    shape is the stable, meaningful part per AD-7 (diagnostics are
    data)."""
    counter: Counter[tuple[str, str]] = Counter()
    for diag in payload["diagnostics"]:
        code = diag["code"]
        label = f"{code['family']}:{code['offset']:04d}"
        counter[(label, diag["severity"])] += 1
    return sorted(
        [code, severity, count] for (code, severity), count in counter.items()
    )


def _flownet_digest(payload_value: dict[str, Any]) -> str:
    """A stable content-derived digest for one flownet payload record
    (WO-32 D6: the payload JSON does not carry the Rust-side
    `content_digest()` value, so this mirrors `_obligation_key`'s
    sha256-over-canonical-JSON approach for the same determinism
    property)."""
    encoded = json.dumps(payload_value, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(encoded.encode("ascii")).hexdigest()


def flownet_digests(payload: dict[str, Any]) -> dict[str, str]:
    """Sorted `flownet name -> content digest` map for a parsed payload
    dict (WO-32 D6: exercises the flownet payload determinism property
    fluorite/03 sec. 5 requires -- same source, same digests)."""
    flownets = payload.get("flownets", {})
    return {name: _flownet_digest(value) for name, value in sorted(flownets.items())}


def stable_snapshot(payload_json: bytes) -> dict[str, Any]:
    """The full stable golden snapshot for one `payload_json` blob."""
    payload = json.loads(payload_json)
    return {
        "obligation_keys": obligation_keys(payload),
        "obligation_count": len(payload["obligations"]),
        "snapshot_hashes": snapshot_hashes(payload),
        "snapshot_count": len(payload["snapshots"]),
        "resolution_count": len(payload["resolutions"]),
        "evidence_count": len(payload["evidence"]),
        "diagnostic_multiset": diagnostic_multiset(payload),
        "flownet_digests": flownet_digests(payload),
    }
