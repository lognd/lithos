"""Override target resolution + the D246 claims/evidence boundary
(charter 42 secs. 1a/2, WO-129A deliverable 2).

A target resolves against the SAME surfaces the census and the
optimizer read from a compiled ``BuildPayload`` (the ``payload`` dict
:func:`regolith.compiler.compile`/``check`` produce, ``json.loads``d):

- ``payload["choice_points"]`` keys -- component/record selects and
  ``by select(...)`` choice points/section-search family selections
  (the SAME surface :func:`regolith.orchestrator.optimize.domains_from_choice_points`
  reads).
- ``payload["resolutions"][i]["cause"]["ref"]`` -- every non-literal
  resolved value's dotted slot path (dimensions, bounded/minimize
  slots, sketch dimensions, placements all funnel through this WO-04
  ``Resolution`` surface, the same one :mod:`regolith.orchestrator.lockfile`
  renders).

An unresolvable target is a constructive diagnostic naming the nearest
valid paths (E1003) -- never a silent no-op.

D246 (charter 42 sec. 1a): the claim/evidence vocabulary (regolith/07's
mantra table) is SOURCE-ONLY. A target whose dotted path names a claim-
semantics or evidence-ladder keyword is REFUSED (E1002) BEFORE
resolution is even attempted -- this is what lets INV-33 be proved by
UNREACHABILITY rather than by review (an override literally cannot name
``model=``, ``sf=``, a trust floor, or a waiver, so it cannot reach one).
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Mapping

from typani.result import Err, Ok, Result

from regolith.errors import OrchestratorError
from regolith.logging_setup import get_logger

_log = get_logger(__name__)

# TODO(WO-131): replace with the generated E10xx constants once landed
# on this branch (WO-131 reserved E1002 for the D246 boundary refusal
# and E1003 for an unresolvable target). Bare strings per the WO-129A
# dispatch note -- do not invent a second code registry.
E1002_SOURCE_ONLY_TARGET = "E1002"
E1003_UNRESOLVABLE_TARGET = "E1003"

# Charter 42 sec. 1a, verbatim: claim SEMANTICS -- what is being
# promised. A target naming any of these path segments is source-only.
_CLAIM_SEMANTICS_TOKENS: frozenset[str] = frozenset(
    {
        "require",
        "forall",
        "all",
        "during",
        "within",
        "until",
        "event",
        "mask",
        "peak",
        "settles",
        "overshoot",
        "rms",
        "stays_within",
        "equilibrium",
        "manufacturable",
        "mfg",
    }
)

# Charter 42 sec. 1a, verbatim: EVIDENCE PROVENANCE -- how a promise is
# proved -- plus the safety multipliers. `model=<impl>` "cannot forge a
# pass" BY CONSTRUCTION only if this token is unreachable; a lower
# `sf=`/`scatter_factor=` would launder a claim by weakening it without
# touching verdict machinery, so both are refused the same way.
_EVIDENCE_LADDER_TOKENS: frozenset[str] = frozenset(
    {
        "trust",
        "analysis",
        "catalog",
        "test",
        "model",
        "assume",
        "todo",
        "waive",
        "sf",
        "scatter_factor",
    }
)

BANNED_TARGET_TOKENS: frozenset[str] = _CLAIM_SEMANTICS_TOKENS | _EVIDENCE_LADDER_TOKENS

_PATH_SEGMENT_RE = re.compile(r"[A-Za-z0-9_]+")


def _segments(target: str) -> list[str]:
    """Split a dotted/bracketed target into lowercase word segments
    (``"Strength.trust_floor"`` -> ``["strength", "trust_floor"]``, and
    critically ``"widget.trust"`` -> ``["widget", "trust"]`` matches the
    banned token ``trust`` as a WHOLE segment, never a substring hit
    inside an unrelated identifier like ``"distrust_sensor"``)."""
    return [seg.lower() for seg in _PATH_SEGMENT_RE.findall(target)]


def boundary_violation(target: str) -> str | None:
    """The banned charter-42-sec.-1a token ``target`` names, if any.

    Matched whole-segment (split on ``.``/non-word chars), never a
    substring: a part legitimately named ``model_shop.Widget`` is not
    blocked by the ``model`` token, but ``design.claim.model`` naming
    the evidence ladder's ``model=`` IS. ``None`` means the target names
    no source-only vocabulary and target resolution may proceed."""
    for segment in _segments(target):
        if segment in BANNED_TARGET_TOKENS:
            return segment
    return None


def injectable_targets(payload: Mapping[str, object]) -> frozenset[str]:
    """Every resolvable override target in a compiled ``BuildPayload``:
    the union of ``choice_points`` subject ids and every ``resolutions``
    entry's ``cause.ref`` -- the two REAL Python-readable surfaces a
    dotted target can name (module docstring)."""
    targets: set[str] = set()

    choice_points = payload.get("choice_points")
    if isinstance(choice_points, Mapping):
        targets.update(str(k) for k in choice_points)

    resolutions = payload.get("resolutions")
    if isinstance(resolutions, list):
        for res in resolutions:
            if not isinstance(res, Mapping):
                continue
            cause = res.get("cause")
            if isinstance(cause, Mapping):
                ref = cause.get("ref")
                if isinstance(ref, str) and ref:
                    targets.add(ref)

    return frozenset(targets)


def resolve_target(
    target: str, payload: Mapping[str, object]
) -> Result[str, OrchestratorError]:
    """Resolve ``target`` against ``payload``'s injectable surfaces.

    Order matters: the D246 boundary check runs FIRST and unconditionally
    (a claim-semantics/evidence-ladder target is refused regardless of
    whether some coincidentally-named resolution or choice point exists),
    then real resolution against :func:`injectable_targets`. An
    unresolvable target names its nearest valid paths (``difflib``) so
    the refusal is constructive, never a bare "not found"."""
    violation = boundary_violation(target)
    if violation is not None:
        _log.warning(
            "override target %r refused: source-only token %r", target, violation
        )
        return Err(
            OrchestratorError(
                kind=E1002_SOURCE_ONLY_TARGET,
                message=(
                    f"override target {target!r} names {violation!r}, which is "
                    "claim semantics or evidence provenance (charter 42 sec. 1a) "
                    "-- this is SOURCE-ONLY, never an injection surface. Edit "
                    "the .hema/.cupr/.fluo/.calx source directly instead."
                ),
            )
        )

    targets = injectable_targets(payload)
    if target in targets:
        _log.debug("override target %r resolved", target)
        return Ok(target)

    near = difflib.get_close_matches(target, sorted(targets), n=3, cutoff=0.4)
    _log.warning("override target %r unresolvable; near matches=%s", target, near)
    detail = (
        f" nearest valid targets: {near}" if near else " no injectable targets found"
    )
    return Err(
        OrchestratorError(
            kind=E1003_UNRESOLVABLE_TARGET,
            message=f"override target {target!r} does not resolve against any "
            f"choice point, bounded/minimize slot, sketch dimension, section "
            f"select, or placement in this build.{detail}",
        )
    )
