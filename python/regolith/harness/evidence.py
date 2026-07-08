"""The margin-driven discharge rule and evidence hashing, in one place.

Regolith/07 sec. 4: a model discharges a claim iff it holds after
charging the model's worst-case error against the margin
(``value +- eps`` vs ``limit``), inside the model's validity domain.
Indeterminate is NOT violated (sec. 4): out-of-domain or short-coverage
is its own status. This module is the single implementation of that rule
so every model shares it (NO DUPLICATION), and the single producer of an
``Evidence`` value's content hash.

Determinism (INV-10): the evidence hash folds every input that could move
the value -- crucially the model's ``deterministic`` flag and, when a
model is non-deterministic, a settings/seed digest -- plus the harness
model-registry version (BE-1/INV-1), so identical inputs give a
byte-identical hash and a model upgrade invalidates cached evidence.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence

from regolith._schema.models import (
    Coverage,
    CoverageAxis,
    Evidence,
    Status1,
    Status2,
    Status3,
)
from regolith.harness.quantity import f64_to_bits


def _status(
    *, in_domain: bool, coverage: float, margin: float
) -> Status1 | Status2 | Status3:
    """Apply the discharge rule -> the evidence status (sec. 4)."""
    if not in_domain or coverage < 1.0:
        # No adequate coverage/domain: neither proven nor disproven.
        return Status3.indeterminate
    if margin >= 0.0:
        return Status1.discharged
    return Status2.violated


def evidence_hash(
    *,
    model_id: str,
    claim_kind: str,
    registry_version: str,
    deterministic: bool,
    value: float,
    eps: float,
    limit: float,
    status: str,
    coverage: float,
    coverage_axes: Sequence[CoverageAxis] = (),
    inputs_digest: str,
    settings_digest: str,
    pack_name: str = "regolith",
    pack_version: str | None = None,
    solver_version: str = "",
) -> str:
    """Content-address an evidence value (INV-1/INV-10/AD-19).

    Canonical JSON (sorted keys, no whitespace) over every hash input,
    then SHA-256. Floats are hashed as their exact ``u64`` bits so text
    formatting can never move the address. The discharging model's
    ``(pack_name, pack_version)`` is folded per AD-19 (BE-1 extended):
    built-ins carry ``("regolith", registry_version)`` -- the default
    when ``pack_version`` is ``None`` -- so upgrading ONE pack changes
    exactly its own evidence hashes. ``solver_version`` (an external
    solver binary's own version) is ALWAYS folded; empty for in-process
    models. ``coverage_axes`` (D95 structured coverage) is folded too,
    so two evidence values sharing the same scalar fraction but
    different per-axis detail never collide (INV-10).
    """
    payload = {
        "claim_kind": claim_kind,
        "coverage_bits": f64_to_bits(coverage),
        "coverage_axes": [axis.model_dump(mode="json") for axis in coverage_axes],
        "deterministic": deterministic,
        "eps_bits": f64_to_bits(eps),
        "inputs_digest": inputs_digest,
        "limit_bits": f64_to_bits(limit),
        "model_id": model_id,
        # AD-19: the discharging model's pack identity is a hash input,
        # so one pack's upgrade invalidates exactly its own evidence.
        "pack_name": pack_name,
        "pack_version": pack_version if pack_version is not None else registry_version,
        "registry_version": registry_version,
        # Non-deterministic models fold their seed/settings so two runs
        # with different settings never collide (INV-10).
        "settings_digest": settings_digest,
        # An out-of-process solver's own version is always folded
        # (AD-19); in-process models carry the empty string.
        "solver_version": solver_version,
        "status": status,
        "value_bits": f64_to_bits(value),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def build_evidence(
    *,
    model_id: str,
    claim_kind: str,
    sense_upper: bool,
    value: float,
    eps: float,
    limit: float,
    coverage: float,
    coverage_axes: Sequence[CoverageAxis] = (),
    cost: int,
    in_domain: bool,
    deterministic: bool,
    registry_version: str,
    inputs_digest: str,
    settings_digest: str = "",
    pack_name: str = "regolith",
    pack_version: str | None = None,
    solver_version: str = "",
) -> Evidence:
    """Assemble a schema ``Evidence`` value from a model's worst-case result.

    ``value`` is the model's worst-corner prediction; ``eps`` its
    worst-case error. For an upper-bound claim the error is charged
    upward (``value + eps <= limit``); for a lower-bound claim downward
    (``value - eps >= limit``). The result is honest by construction: a
    short-coverage or out-of-domain model yields ``indeterminate``, never
    a silent ``discharged``. The pack identity and solver version feed
    the evidence hash per AD-19 (see :func:`evidence_hash`).
    ``coverage_axes`` (D95) is the structured per-axis record a sweeping
    model states (grid/enumerated/analytic/monotone); ``coverage``
    remains the conservative scalar collapse.
    """
    effective = value + eps if sense_upper else value - eps
    margin = (limit - effective) if sense_upper else (effective - limit)
    status = _status(in_domain=in_domain, coverage=coverage, margin=margin)
    hash_hex = evidence_hash(
        model_id=model_id,
        claim_kind=claim_kind,
        registry_version=registry_version,
        deterministic=deterministic,
        value=value,
        eps=eps,
        limit=limit,
        status=status.value,
        coverage=coverage,
        coverage_axes=coverage_axes,
        inputs_digest=inputs_digest,
        settings_digest=settings_digest,
        pack_name=pack_name,
        pack_version=pack_version,
        solver_version=solver_version,
    )
    return Evidence(
        model_id=model_id,
        status=status,
        value_bits=f64_to_bits(value),
        eps_bits=f64_to_bits(eps),
        margin_bits=f64_to_bits(margin),
        coverage=Coverage(
            axes=list(coverage_axes), fraction_bits=f64_to_bits(coverage)
        ),
        cost=cost,
        hash=hash_hex,
    )
