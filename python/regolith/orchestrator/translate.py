"""Translate a serialized ``Obligation`` into a harness ``DischargeRequest``.

Extracting a numeric discharge request from a serialized obligation is
orchestrator territory (regolith/07 sec. 2 note on ``DischargeRequest``):
the obligation's quantity expressions are text until resolution pins them,
and the harness consumes only the resolved form. This module does that
lowering for the scalar-comparison claim form and reports an explicit
:class:`Deferral` for anything it cannot resolve numerically -- never a
silent drop (INV-24 totality feeds on honest deferrals).

The numeric parsing here is deliberately conservative: it reads a leading
float off a bound/load expression (unit suffixes are the resolver's job,
not re-implemented here) and defers when a value is not yet a literal.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith._schema.models import (
    ClaimForm1,
    ClaimForm2,
    ClaimForm3,
    ClaimForm4,
    ClaimForm5,
    ClaimForm6,
    Obligation,
)
from regolith.harness import DischargeRequest, Interval
from regolith.harness.models.beam_service_deflection import (
    CLAIM_KIND as _MECH_DEFLECTION_KIND,
)
from regolith.harness.models.beam_utilization import CLAIM_KIND as _CIVIL_UTIL_KIND
from regolith.harness.models.conformance import CLAIM_KIND_LOWER, CLAIM_KIND_UPPER
from regolith.harness.models.cost_common import CLAIM_KIND as _COST_KIND
from regolith.harness.models.cost_common import BomLine
from regolith.harness.models.link_budget import CLAIM_KIND as _LINK_KIND
from regolith.harness.models.link_budget import INPUTS as _LINK_INPUTS
from regolith.harness.models.workload_realization import CLAIM_KIND as _REALIZATION_KIND
from regolith.logging_setup import get_logger

if TYPE_CHECKING:
    # Runtime-lazy: `costing`/`frame_resolve` import this module's
    # `Deferral` consumers transitively through the orchestrator
    # package; the type-only import keeps the layering acyclic (the
    # `model.py` resolver precedent).
    from regolith.orchestrator.costing import CostContext
    from regolith.orchestrator.frame_resolve import FrameContext, ResolvedMember

_log = get_logger(__name__)

# The Rust lowering's structured cost-claim markers in `given.loads`
# (WO-54 deliverable 1: `push_cost_claim_obligation`). One home for the
# strings on the Python side.
_COST_SUBJECT_FIELD = "cost_subject"
_COST_PROFILE_FIELD = "cost_profile"
_COST_BOM_PREFIX = "cost_bom."

# Comparators whose claim is an upper bound (value must stay below) vs a
# lower bound (value must stay above). Containment/temporal ops defer.
_UPPER_OPS = frozenset({"<", "<=", "peak<", "peak<="})
_LOWER_OPS = frozenset({">", ">="})

# A leading signed float (optionally followed by a unit we ignore here).
_LEADING_FLOAT = re.compile(r"\s*([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)")

# The conformance refinement sense (carried in `given.loads` by the core
# when both windows resolve) -> the harness conformance model's claim kind.
_CONFORMANCE_CLAIM_KIND = {"upper": CLAIM_KIND_UPPER, "lower": CLAIM_KIND_LOWER}

# The rule-3 derived-workload cause tag the core emits in `given.loads`
# for a realization edge it auto-allocated (`realization_obligation`,
# `regolith-lower/src/claims.rs`). Prefix match: the tag's tail is the
# realized intent's name, which this module does not need to parse.
_DERIVED_CAUSE_PREFIX = "derived(intent "

# The arbitrary matching constant the derived-workload identity model
# discharges against (see `regolith.harness.models.workload_realization`
# -- there is no physical quantity here, only a structural identity).
_REALIZATION_IDENTITY_LIMIT = 1.0

# Comparator tokens the predicate `rhs` may lead with, longest first so
# `<=`/`>=` win over `<`/`>`. The core lowers a `subject: predicate`
# claim line with a fixed `op="require"` (the comparator is inside the
# predicate text, `07` sec. 4), so the orchestrator splits it back out
# here to recover the claim's SENSE (upper/lower bound).
_COMPARATORS: tuple[str, ...] = ("peak<=", "peak<", "<=", ">=", "<", ">")

# The calcite/03 sec. 5 frame-referencing claim call forms (the same
# list `regolith-lower::claims::FRAME_CLAIM_FORMS` gates a `frame`
# PayloadRef on -- kept in sync by hand, mirrored one Rust list per
# WO-48's own precedent). Only the first two have a harness model
# (WO-48 deliverable 5); the rest defer naming the missing model.
_FRAME_FORM_NAMES: tuple[str, ...] = (
    "civil.utilization",
    "mech.deflection",
    "civil.story_drift",
    "civil.bearing_pressure",
    "mech.first_mode",
)

# Frame-referencing call form -> the harness model's registered claim
# kind (NOT always string-identical to the call name: `mech.deflection`
# the corpus writes maps to `mech.beam.service_deflection`, the model's
# own registry key -- see `beam_service_deflection.py`'s module doc).
_FRAME_MODEL_KIND: dict[str, str] = {
    "civil.utilization": _CIVIL_UTIL_KIND,
    "mech.deflection": _MECH_DEFLECTION_KIND,
}

# A `mech.deflection(<member>, ...) <= <member>.span / <N>` bound (the
# corpus's L/360-style serviceability limit) -- the only deflection
# bound shape this translator resolves without a full expression
# evaluator (D97 conservatism: anything else defers by name). Matches
# from the start only (no trailing `$` anchor): a `require` group's
# trailing same-indent comment can be swallowed into a claim's lowered
# `rhs` span (a source-text artifact, verified live against
# footbridge.calx's own `deflect` obligation -- the divisor is
# unambiguous regardless of what garbage trails it, so this stays
# tolerant rather than requiring a Rust CST fix out of WO-65's scope).
_SPAN_BOUND = re.compile(r"^\s*([A-Za-z_][\w]*)\.span\s*/\s*([+-]?\d+(?:\.\d+)?)")


def _split_frame_predicate(rhs: str) -> tuple[str, str, str] | None:
    """Split a frame-referencing predicate (`civil.utilization(Bridge.
    members.all, under=combo) <= 1.0`) into `(form_name, call_args,
    bound_text)`.

    Unlike the plain scalar-bound shape :func:`_split_comparator`
    handles, a frame predicate's comparator sits AFTER a full call
    expression, not at the head of `rhs` -- this walks paren depth to
    find the matching close-paren before looking for the comparator.
    Returns `None` when `rhs` does not open with one of the
    :data:`_FRAME_FORM_NAMES` call forms.
    """
    stripped = rhs.lstrip()
    for name in _FRAME_FORM_NAMES:
        prefix = name + "("
        if not stripped.startswith(prefix):
            continue
        depth = 0
        for i, ch in enumerate(stripped):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    args = stripped[len(prefix) : i]
                    rest = stripped[i + 1 :].lstrip()
                    for comp in _COMPARATORS:
                        if rest.startswith(comp):
                            return name, args, rest[len(comp) :].strip()
                    return name, args, ""
        return name, stripped[len(prefix) :], ""
    return None


def _split_comparator(op: str, rhs: str) -> tuple[str, str] | None:
    """Recover ``(comparator, bound_text)`` from a claim's ``op``/``rhs``.

    A claim whose ``op`` is already a comparator keeps it (the bound is the
    whole ``rhs``). The lowering's placeholder ``op="require"`` instead
    carries the comparator at the head of ``rhs`` (``">= 6 dB"``); split it
    off. Returns ``None`` when no one-sided comparator is present (the
    caller defers -- a containment/equality/temporal predicate never lowers
    to a scalar bound here).
    """
    if op in _UPPER_OPS or op in _LOWER_OPS:
        return op, rhs
    if op == "require":
        head = rhs.lstrip()
        for comp in _COMPARATORS:
            if head.startswith(comp):
                return comp, head[len(comp) :]
    return None


class Deferral(BaseModel):
    """An obligation the orchestrator could not lower to a numeric request.

    Honest, greppable, and release-gated: a deferral is neither a pass nor
    a violation -- it says "no numeric obligation was formed here" and the
    release gate (INV-24) treats it as unresolved.
    """

    model_config = ConfigDict(frozen=True)

    reason: str
    detail: str


class GivenResolutionError(BaseModel):
    """D97 (sec. 8.4): a named given could not be resolved to a scalar.

    Never a guess: property-record evaluation over the environment box
    (worst corner via declared monotonicity, else the full-domain hull)
    and interface-envelope load extraction either produce a resolved
    value or this error, naming the exact given that failed -- carried
    into an INDETERMINATE discharge (never a silent drop).
    """

    model_config = ConfigDict(frozen=True)

    given: str
    detail: str

    def as_deferral(self) -> Deferral:
        """The existing :class:`Deferral` surface this error rides on."""
        return Deferral(
            reason="given_unresolved",
            detail=f"given {self.given!r} did not resolve: {self.detail}",
        )


# D97 item 4: regime tags LOWERING asserts from claim-kind construction
# (the "start with the WO-13 claim-kind table's guarantees" instruction).
# Every shipped `mech.*` closed-form claim kind is a static, linear-
# elastic model (regolith/07's WO-13 built-in models never model
# plasticity or dynamics); extend only where a kind's construction
# genuinely guarantees the tag.
_MECH_STATIC_REGIMES: tuple[str, ...] = ("linear_elastic", "static")


def _regimes_for(claim_kind: str) -> tuple[str, ...]:
    """The regime tags LOWERING asserts for ``claim_kind`` (D97 item 4)."""
    if claim_kind.startswith("mech."):
        return _MECH_STATIC_REGIMES
    return ()


def resolve_givens(
    loads: list[str],
) -> Result[dict[str, Interval], GivenResolutionError]:
    """D97 items (a)/(b): resolve ``given.loads`` lines to scalar intervals.

    Each ``name: value`` line either parses as a numeric interval (the
    worst-corner/full-domain-hull evaluation already performed upstream
    by the property-record/load-envelope extraction this orchestrator
    seam consumes) or is an honest, named resolution failure -- never a
    guess. Lines this module does not attempt to split on `:` (no colon
    present) are ignored, matching the existing `given.loads` shape.
    """
    resolved: dict[str, Interval] = {}
    for line in loads:
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        name = name.strip()
        interval = _parse_interval(value)
        if interval is None:
            return Err(
                GivenResolutionError(
                    given=name,
                    detail=(
                        f"value {value.strip()!r} is not a resolved numeric interval"
                    ),
                )
            )
        resolved[name] = interval
    return Ok(resolved)


def _parse_float(text: str) -> float | None:
    """Read a leading float off ``text`` (unit suffix ignored), or ``None``."""
    match = _LEADING_FLOAT.match(text)
    if match is None:
        return None
    return float(match.group(1))


def _parse_interval(text: str) -> Interval | None:
    """Parse ``[lo, hi]`` or a bare point value into an :class:`Interval`."""
    stripped = text.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        parts = stripped[1:-1].split(",")
        if len(parts) != 2:
            return None
        lo, hi = _parse_float(parts[0]), _parse_float(parts[1])
        if lo is None or hi is None:
            return None
        return Interval(lo=lo, hi=hi)
    point = _parse_float(stripped)
    if point is None:
        return None
    return Interval(lo=point, hi=point)


def _load_fields(loads: list[str]) -> dict[str, str]:
    """Split ``given.loads`` (``name: value`` text) into a raw string map.

    Unlike :func:`resolve_givens` this keeps non-numeric values (the
    conformance sense marker), leaving numeric parsing to the caller.
    """
    fields: dict[str, str] = {}
    for line in loads:
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        fields[name.strip()] = value.strip()
    return fields


def _translate_conformance(
    obligation: Obligation,
) -> Result[DischargeRequest, Deferral]:
    """Lower a ``conforms`` obligation to a conformance-model request.

    INV-13/26 (the implicit-``by spec`` default): the compiler emits one
    conformance obligation per ``impl``/extern/import binding. When both the
    upper contract and the lower realization carried a resolved comparator
    bound, the core threads the two refinement windows into ``given.loads``
    (``conformance_sense``/``spec_bound``/``impl_bound``); this lowers them
    into the harness conformance model's request (limit = the spec bound,
    the single ``impl_bound`` input = the realization's bound). Absent those
    windows the obligation defers HONESTLY, naming the exact missing fields
    -- the compiler never invents a window the source did not state.
    """
    fields = _load_fields(obligation.given.loads)
    sense = fields.get("conformance_sense")
    spec_text = fields.get("spec_bound")
    impl_text = fields.get("impl_bound")
    if sense is None or spec_text is None or impl_text is None:
        return Err(
            Deferral(
                reason="conformance_windows_unresolved",
                detail=(
                    "conforms obligation carries no resolved "
                    "conformance_sense/spec_bound/impl_bound windows "
                    "(refinement-bound extraction is a WO-12 cut)"
                ),
            )
        )
    claim_kind = _CONFORMANCE_CLAIM_KIND.get(sense)
    spec_bound = _parse_float(spec_text)
    impl_bound = _parse_float(impl_text)
    if claim_kind is None or spec_bound is None or impl_bound is None:
        return Err(
            Deferral(
                reason="conformance_windows_unresolved",
                detail=f"conforms windows not numeric (sense={sense!r})",
            )
        )
    _log.debug(
        "translated conforms obligation subject=%s -> %s limit=%g impl_bound=%g",
        obligation.subject_ref,
        claim_kind,
        spec_bound,
        impl_bound,
    )
    return Ok(
        DischargeRequest(
            claim_kind=claim_kind,
            limit=spec_bound,
            inputs={"impl_bound": Interval(lo=impl_bound, hi=impl_bound)},
            deterministic=True,
            regimes=_regimes_for(claim_kind),
        )
    )


def _translate_realization(
    obligation: Obligation,
) -> Result[DischargeRequest, Deferral]:
    """Lower an `implies`-form realization obligation (EOPEN-15 rules 2/3).

    Only a rule-3 DERIVED edge lowers: its `cause: derived(intent ...)`
    tag (`given.loads`) marks a workload whose demand vector was copied
    VERBATIM from the intent it realizes (cuprite/05 sec. 1 rule 3), so
    "workload implies intent" is a structural identity -- always sound,
    zero model error -- and the harness's identity model
    (`regolith.harness.models.workload_realization`) discharges it.

    A DECLARED (non-derived) edge's implication is a genuine claim over
    the intent's own rate/state/latency demands (rule 2), and those
    quantities are not threaded through the obligation today (`intents:`
    bodies are opaque islands, WO-05 cut; `docs/audit/TRIAGE.md`). Rather
    than invent a window, this defers HONESTLY: the orchestrator forms no
    numeric request, so the release gate sees an indeterminate obligation
    -- loud, never a silent pass (INV-24/26).
    """
    fields = _load_fields(obligation.given.loads)
    cause = fields.get("cause", "")
    if not cause.startswith(_DERIVED_CAUSE_PREFIX):
        return Err(
            Deferral(
                reason="realization_not_derived_unverifiable",
                detail=(
                    "a declared realization edge's demand implication "
                    "needs the intent's own rate/state/latency quantities, "
                    "which are not threaded through the obligation (WO-05 "
                    "cut); only rule-3 derived (verbatim-copy) edges "
                    "discharge today"
                ),
            )
        )
    _log.debug(
        "translated derived-realization obligation subject=%s -> %s",
        obligation.subject_ref,
        _REALIZATION_KIND,
    )
    return Ok(
        DischargeRequest(
            claim_kind=_REALIZATION_KIND,
            limit=_REALIZATION_IDENTITY_LIMIT,
            inputs={},
            deterministic=True,
            regimes=_regimes_for(_REALIZATION_KIND),
        )
    )


def _translate_cost(
    obligation: Obligation,
    fields: dict[str, str],
    bound_text: str,
    cost_context: CostContext | None,
) -> Result[DischargeRequest, Deferral]:
    """Lower an `mfg.cost` obligation (WO-54 deliverable 4): resolve the
    claim's profile set (claim `profile=` beats `--profile` beats the
    manifest default; a `forall profile in {..}` sweep selects every
    axis point, D95), resolve each profile's records (expired pricing
    is a NAMED deferral, waivable with basis), stage the estimator-
    inputs doc, and form the `mfg.cost` request. Every failure is an
    honest deferral naming exactly what is missing.
    """
    # Runtime-lazy import (see the module's TYPE_CHECKING note).
    from regolith.orchestrator import costing

    limit = _parse_float(bound_text)
    if limit is None:
        return Err(
            Deferral(
                reason="unresolved_limit",
                detail=f"cost bound {bound_text!r} not literal",
            )
        )
    if cost_context is None:
        return Err(
            Deferral(
                reason="cost_profiles_unconfigured",
                detail=(
                    "no [profiles.cost.*] configuration was resolved for this "
                    "build (magnetite.toml declares none, or this entry point "
                    "does not thread a cost context)"
                ),
            )
        )

    sweep = obligation.sweep
    if sweep is not None and sweep.axis == "profile":
        names = costing.parse_profile_sweep(sweep.domain)
        if names is None:
            return Err(
                Deferral(
                    reason="cost_profile_unresolved",
                    detail=(
                        f"forall profile sweep domain {sweep.domain!r} is not "
                        "a discrete {a, b} set"
                    ),
                )
            )
    else:
        picked = fields.get(_COST_PROFILE_FIELD) or cost_context.build_profile
        if picked is None:
            return Err(
                Deferral(
                    reason="cost_profile_unresolved",
                    detail=(
                        "claim names no profile=, no --profile was given, and "
                        "the manifest declares no [profiles.cost.default]"
                    ),
                )
            )
        names = (picked,)

    resolved_profiles = []
    for name in names:
        profile = cost_context.profiles.get(name)
        if profile is None:
            return Err(
                Deferral(
                    reason="cost_profile_unknown",
                    detail=(
                        f"profile {name!r} is not declared "
                        f"(declared: {sorted(cost_context.profiles)})"
                    ),
                )
            )
        inputs_result = costing.resolve_profile_inputs(cost_context, profile)
        if inputs_result.is_err:
            failure = inputs_result.danger_err
            _log.info(
                "obligation %s: cost profile %s did not resolve (%s: %s)",
                obligation.subject_ref,
                name,
                failure.reason,
                failure.detail,
            )
            return Err(Deferral(reason=failure.reason, detail=failure.detail))
        resolved_profiles.append(inputs_result.danger_ok)

    bom = tuple(
        BomLine(part=key[len(_COST_BOM_PREFIX) :], ref=value)
        for key, value in fields.items()
        if key.startswith(_COST_BOM_PREFIX)
    )
    doc = costing.assemble_inputs_doc(
        cost_context, fields[_COST_SUBJECT_FIELD], tuple(resolved_profiles), bom
    )
    staged = costing.stage_inputs_doc(cost_context, doc)
    if staged.is_err:
        failure = staged.danger_err
        return Err(Deferral(reason=failure.reason, detail=failure.detail))
    ports, settings_digest = staged.danger_ok
    _log.debug(
        "translated cost obligation subject=%s profiles=%s limit=%g ports=%s",
        doc.subject,
        [p.name for p in resolved_profiles],
        limit,
        sorted(ports),
    )
    return Ok(
        DischargeRequest(
            claim_kind=_COST_KIND,
            limit=limit,
            inputs={},
            deterministic=True,
            settings_digest=settings_digest,
            payloads=ports,
        )
    )


def _resolve_frame_members(
    obligation: Obligation,
    frame_context: FrameContext,
    frame: dict[str, object],
    subject: str,
) -> Result[list[ResolvedMember], Deferral]:
    """Resolve `subject`'s member(s) against `frame` (WO-48 close-out
    follow-up): a `<Structure>.members.all` subject resolves every
    declared member; a bare id resolves that one member. The FIRST
    unresolved member honestly defers the whole claim (a group
    utilization claim is only as sound as its weakest member -- no
    partial verdict is fabricated for the members that DID resolve).
    """
    from regolith.orchestrator import frame_resolve

    member_ids: list[str]
    if subject.endswith(".members.all"):
        members_raw = frame.get("members", [])
        member_ids = (
            [str(m.get("id", "")) for m in members_raw if isinstance(m, dict)]
            if isinstance(members_raw, list)
            else []
        )
    else:
        member_ids = [subject.rsplit(".", 1)[-1]]

    resolved: list[frame_resolve.ResolvedMember] = []
    for member_id in member_ids:
        result = frame_resolve.resolve_member(frame_context, frame, member_id)
        if result.is_err:
            failure = result.danger_err
            _log.info(
                "obligation %s: frame member %s unresolved (%s: %s)",
                obligation.subject_ref,
                member_id,
                failure.reason,
                failure.detail,
            )
            return Err(Deferral(reason=failure.reason, detail=failure.detail))
        resolved.append(result.danger_ok)
    return Ok(resolved)


def _translate_civil_utilization(
    obligation: Obligation,
    frame_context: FrameContext,
    frame: dict[str, object],
    subject: str,
    bound_text: str,
) -> Result[DischargeRequest, Deferral]:
    """Lower a `civil.utilization(<subject>, under=<combo>) <= <limit>`
    claim (calcite/03 sec. 5) against its frame's resolved member
    properties + directly-targeted literal load demand.

    Every member the subject names must resolve BOTH its section/
    material (:func:`frame_resolve.resolve_member`) AND its own
    demand (:func:`frame_resolve.member_udl_demand`) for this to
    discharge -- any single unresolved member (a `free` section, or a
    member whose demand arrives only through an un-modeled tributary
    transfer) defers the whole claim honestly, naming that member.
    """
    from regolith.orchestrator import frame_resolve

    limit = _parse_float(bound_text)
    if limit is None:
        return Err(
            Deferral(
                reason="unresolved_limit",
                detail=f"utilization bound {bound_text!r} not literal",
            )
        )
    members = _resolve_frame_members(obligation, frame_context, frame, subject)
    if members.is_err:
        return Err(members.danger_err)

    worst = 0.0
    for member in members.danger_ok:
        demand = frame_resolve.member_udl_demand(frame, member)
        if demand.is_err:
            failure = demand.danger_err
            _log.info(
                "obligation %s: frame member %s demand unresolved (%s: %s)",
                obligation.subject_ref,
                member.id,
                failure.reason,
                failure.detail,
            )
            return Err(Deferral(reason=failure.reason, detail=failure.detail))
        w_load = demand.danger_ok
        moment = w_load * member.length_m**2 / 8.0
        if member.s_m3 is None:
            return Err(
                Deferral(
                    reason="frame_section_incomplete",
                    detail=(
                        f"member {member.id!r}'s section carries no section "
                        "modulus (s_mm3) this resolver reduces"
                    ),
                )
            )
        utilization = abs(moment) / (member.s_m3 * member.fy_pa)
        worst = max(worst, utilization)

    _log.debug(
        "translated civil.utilization obligation subject=%s limit=%g worst=%g",
        obligation.subject_ref,
        limit,
        worst,
    )
    return Ok(
        DischargeRequest(
            claim_kind=_CIVIL_UTIL_KIND,
            limit=limit,
            inputs=_civil_utilization_inputs(worst),
            deterministic=True,
            regimes=_regimes_for(_CIVIL_UTIL_KIND),
        )
    )


def _civil_utilization_inputs(worst_utilization: float) -> dict[str, Interval]:
    """The `BeamUtilizationModel` input vector that reproduces an
    already-computed worst-case utilization exactly (moment-only,
    unit section/area/fy) -- this translator does the real per-member
    interaction arithmetic itself (multiple members, each with its own
    section/material), so it stages a normalized single-term vector
    rather than re-deriving the model's own formula in reverse.
    """
    return {
        "moment_demand": Interval(lo=worst_utilization, hi=worst_utilization),
        "axial_demand": Interval(lo=0.0, hi=0.0),
        "section_modulus": Interval(lo=1.0, hi=1.0),
        "area": Interval(lo=1.0, hi=1.0),
        "fy": Interval(lo=1.0, hi=1.0),
    }


def _translate_mech_deflection(
    obligation: Obligation,
    frame_context: FrameContext,
    frame: dict[str, object],
    subject: str,
    bound_text: str,
) -> Result[DischargeRequest, Deferral]:
    """Lower a `mech.deflection(<member>, under=<case>) <= <member>.span
    / <N>` claim (calcite/03 sec. 5, the corpus's L/360-style
    serviceability limit) against the member's resolved section/
    material properties + directly-targeted literal load demand.
    """
    from regolith.orchestrator import frame_resolve

    members = _resolve_frame_members(obligation, frame_context, frame, subject)
    if members.is_err:
        return Err(members.danger_err)
    member = members.danger_ok[0]

    span_match = _SPAN_BOUND.match(bound_text)
    if span_match is None:
        return Err(
            Deferral(
                reason="frame_deflection_bound_unresolved",
                detail=(
                    f"deflection bound {bound_text!r} is not the "
                    "`<member>.span / <N>` shape this translator resolves"
                ),
            )
        )
    divisor = float(span_match.group(2))
    if divisor <= 0.0:
        return Err(
            Deferral(
                reason="frame_deflection_bound_unresolved",
                detail=f"deflection bound divisor {divisor} is not positive",
            )
        )
    limit = member.length_m / divisor

    demand = frame_resolve.member_udl_demand(frame, member)
    if demand.is_err:
        failure = demand.danger_err
        _log.info(
            "obligation %s: frame member %s demand unresolved (%s: %s)",
            obligation.subject_ref,
            member.id,
            failure.reason,
            failure.detail,
        )
        return Err(Deferral(reason=failure.reason, detail=failure.detail))
    w_load = demand.danger_ok

    _log.debug(
        "translated mech.deflection obligation subject=%s member=%s limit=%g",
        obligation.subject_ref,
        member.id,
        limit,
    )
    return Ok(
        DischargeRequest(
            claim_kind=_MECH_DEFLECTION_KIND,
            limit=limit,
            inputs={
                "w_load": Interval(lo=w_load, hi=w_load),
                "length": Interval(lo=member.length_m, hi=member.length_m),
                "e_modulus": Interval(lo=member.e_pa, hi=member.e_pa),
                "i_area": Interval(lo=member.i_m4, hi=member.i_m4),
            },
            deterministic=True,
            regimes=_regimes_for(_MECH_DEFLECTION_KIND),
        )
    )


def _translate_frame(
    obligation: Obligation,
    split: tuple[str, str, str],
    frame_context: FrameContext | None,
) -> Result[DischargeRequest, Deferral]:
    """Lower a frame-referencing structural claim (calcite/03 sec. 5:
    `civil.utilization` / `mech.deflection` / `civil.story_drift` /
    `civil.bearing_pressure` / `mech.first_mode`) against the
    `FramePayload` its obligation's `kind: frame` `PayloadRef` names
    (WO-48 slice B/C close-out follow-up -- the frame-chain-completion
    resolution seam, `regolith.orchestrator.frame_resolve`).

    Only `civil.utilization`/`mech.deflection` have a closed-form
    harness model (WO-48 deliverable 5); the other three call forms
    honestly defer `no_frame_model`, naming the gap rather than
    fabricating a verdict.
    """
    form_name, args_text, bound_text = split
    ref = next((r for r in obligation.payloads or () if r.kind == "frame"), None)
    if ref is None:
        return Err(
            Deferral(
                reason="frame_payload_missing",
                detail="no `kind: frame` PayloadRef on this obligation",
            )
        )
    if frame_context is None:
        return Err(
            Deferral(
                reason="frame_context_unconfigured",
                detail=(
                    "no std.civil records were resolved for this build "
                    "(this entry point does not thread a frame context)"
                ),
            )
        )
    frame = frame_context.frames.get(ref.origin)
    if frame is None:
        return Err(
            Deferral(
                reason="frame_payload_unavailable",
                detail=(
                    f"structure {ref.origin!r} names no frame in this build's payload"
                ),
            )
        )
    if form_name not in _FRAME_MODEL_KIND:
        return Err(
            Deferral(
                reason="no_frame_model",
                detail=(
                    f"{form_name} has no closed-form harness model yet "
                    "(WO-48 deliverable 5 covers civil.utilization/"
                    "mech.deflection only)"
                ),
            )
        )
    subject = args_text.split(",", 1)[0].strip()
    if form_name == "civil.utilization":
        return _translate_civil_utilization(
            obligation, frame_context, frame, subject, bound_text
        )
    return _translate_mech_deflection(
        obligation, frame_context, frame, subject, bound_text
    )


# D102 REDUCTION forms (`ClaimForm2` peak, `ClaimForm4` overshoot,
# `ClaimForm5` rms) carry a typed `op`/`rhs` external comparator; the
# CONTAINMENT forms (`ClaimForm3` settles, `ClaimForm6` stays_within)
# carry none -- their own parameters are the whole acceptance.
_TEMPORAL_REDUCTION_FORMS = (ClaimForm2, ClaimForm4, ClaimForm5)
_TEMPORAL_CONTAINMENT_FORMS = (ClaimForm3, ClaimForm6)


def _parse_tolerance(text: str) -> float | None:
    """Parse a settling tolerance (``+-2%``, ``+-50mV``) to a fraction/value.

    A ``+-N%`` tolerance is a fraction (``0.02``); any other ``+-<value>``
    keeps its leading float. ``None`` when nothing numeric is present.
    """
    stripped = text.strip().removeprefix("+-").strip()
    value = _parse_float(stripped)
    if value is None:
        return None
    if stripped.rstrip().endswith("%"):
        return value / 100.0
    return value


def _translate_temporal(
    obligation: Obligation,
    form: ClaimForm2 | ClaimForm3 | ClaimForm4 | ClaimForm5 | ClaimForm6,
) -> Result[DischargeRequest, Deferral]:
    """Lower a WO-26 D102 typed temporal claim form to a request.

    REDUCTIONS (`peak`/`rms`/`overshoot`) carry a typed external
    comparator: a numeric ``rhs`` becomes the request limit and the
    claim lowers like any scalar comparison (the claim kind is the
    claim name -- a name no model pack registers is a model-absent
    indeterminate at discharge, per the WO-26 acceptance wording,
    never an ``unsupported_op`` deferral). `settles` is self-contained:
    its acceptance window duration is the limit (an upper bound on
    settling time) and its ``to=`` tolerance rides as an input.
    `stays_within` has no scalar acceptance at all (the mask IS the
    claim), so it defers with a named reason.
    """
    kind = type(form).__name__
    claim_kind = obligation.claim.name or form.signal
    if isinstance(form, _TEMPORAL_REDUCTION_FORMS):
        limit = _parse_float(form.rhs)
        if limit is None:
            return Err(
                Deferral(
                    reason="temporal_reduction_unresolved_limit",
                    detail=(
                        f"claim form {kind} bound {form.rhs!r} is not a "
                        "literal (an entity-derived bound needs D103 ref "
                        "resolution on the reduction path)"
                    ),
                )
            )
        resolved = resolve_givens(obligation.given.loads)
        if resolved.is_err:
            return Err(resolved.danger_err.as_deferral())
        _log.debug(
            "translated temporal reduction subject=%s -> claim_kind=%s limit=%g",
            obligation.subject_ref,
            claim_kind,
            limit,
        )
        return Ok(
            DischargeRequest(
                claim_kind=claim_kind,
                limit=limit,
                inputs=resolved.danger_ok,
                deterministic=True,
                regimes=_regimes_for(claim_kind),
            )
        )
    if isinstance(form, ClaimForm3):
        # `settles(x, to=tol, within d after e)`: the window duration is
        # the acceptance's upper bound on settling time (the core has
        # already resolved it to seconds through regolith-qty).
        duration = getattr(form.window, "within_after", None)
        limit = _parse_float(duration.duration) if duration is not None else None
        if limit is None:
            return Err(
                Deferral(
                    reason="temporal_containment_unresolved_window",
                    detail=(
                        f"settles claim window {form.window!r} carries no "
                        "literal bounding duration"
                    ),
                )
            )
        resolved = resolve_givens(obligation.given.loads)
        if resolved.is_err:
            return Err(resolved.danger_err.as_deferral())
        inputs = dict(resolved.danger_ok)
        tol = _parse_tolerance(form.tol)
        if tol is not None:
            inputs["tol"] = Interval(lo=tol, hi=tol)
        _log.debug(
            "translated settles containment subject=%s -> claim_kind=%s "
            "limit=%g tol=%s",
            obligation.subject_ref,
            claim_kind,
            limit,
            tol,
        )
        return Ok(
            DischargeRequest(
                claim_kind=claim_kind,
                limit=limit,
                inputs=inputs,
                deterministic=True,
                regimes=_regimes_for(claim_kind),
            )
        )
    # `stays_within`: the hash-pinned mask IS the acceptance; there is
    # no scalar limit to charge eps against, so this defers with a
    # named reason (a mask-consuming model is a payload-channel design,
    # not a scalar request).
    _log.info(
        "obligation %s: stays_within containment has no scalar acceptance; deferring",
        obligation.subject_ref,
    )
    return Err(
        Deferral(
            reason="temporal_containment_unmodeled",
            detail=(
                f"claim form {kind} lowered to a typed D102 containment, "
                "but its mask acceptance has no scalar request shape "
                "(payload-channel consumption is a recorded residual)"
            ),
        )
    )


def _signed_terms(text: str) -> list[tuple[str, str]]:
    """Split one comparison side into ``(sign, term)`` pairs (D103).

    Splits on top-level ``+``/``-`` only (bracket depth 0), after
    dropping the trailing window/quantifier clause (`` during ...``,
    `` until ...``, `` forall ...``).
    """
    for marker in (" during ", " until ", " forall "):
        idx = _find_top_level(text, marker)
        if idx is not None:
            text = text[:idx]
    terms: list[tuple[str, str]] = []
    depth = 0
    sign = "+"
    start = 0
    for i, ch in enumerate(text):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch in "+-" and depth == 0:
            piece = text[start:i].strip()
            if piece:
                terms.append((sign, piece))
                sign = ch
                start = i + 1
            elif not terms:
                # A leading sign belongs to the first term.
                sign = ch
                start = i + 1
    piece = text[start:].strip()
    if piece:
        terms.append((sign, piece))
    return terms


def _find_top_level(text: str, needle: str) -> int | None:
    """The index of ``needle`` in ``text`` at bracket depth 0, if any."""
    depth = 0
    for i, ch in enumerate(text):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif depth == 0 and text.startswith(needle, i):
            return i
    return None


def _try_link_budget(
    obligation: Obligation,
    form: ClaimForm1,
) -> Result[DischargeRequest, Deferral] | None:
    """D103: lower a link-budget-shaped general comparison, if it is one.

    The shape is exactly the ``elec.link.margin`` pack's formula
    (``margin = pa_out + gain - path_loss - sensitivity >= limit``):
    the lhs is ``+pa_out +gain -path_loss`` reference terms, the rhs is
    ``+sensitivity`` plus one positive literal margin term, matched by
    each reference's final path segment against the pack's public port
    names (one home for the strings, D97c). Returns ``None`` when the
    claim is not link-shaped (the caller's generic paths continue);
    a link-shaped claim with an unresolved reference defers naming it
    (`given_unresolved`) -- the pack is REACHABLE, the given is not.
    """
    if form.op != ">=":
        return None
    lhs_terms = _signed_terms(form.lhs)
    rhs_terms = _signed_terms(form.rhs)
    expected_signs = {
        "pa_out": "+",
        "gain": "+",
        "path_loss": "-",
        "sensitivity": "+",
    }
    ports: dict[str, str] = {}  # port name -> full reference path
    limit: float | None = None
    for sign, term in lhs_terms + rhs_terms:
        head = _parse_float(term)
        if head is not None:
            if sign != "+" or limit is not None:
                return None
            limit = head
            continue
        # A call term (`path_loss(boundary.orbit.slant_max)`) names its
        # port by its head; a dotted reference by its final segment.
        name = term.split("(", 1)[0].strip() if "(" in term else term
        port = name.rsplit(".", 1)[-1]
        if port not in expected_signs or expected_signs[port] != sign:
            return None
        ports[port] = term
    if set(ports) != set(_LINK_INPUTS) or limit is None:
        return None
    refs = {ref.root[0]: ref.root[1] for ref in (obligation.given.refs or ())}
    inputs: dict[str, Interval] = {}
    for port, path in ports.items():
        value_text = refs.get(path)
        value = _parse_float(value_text) if value_text is not None else None
        if value is None:
            _log.info(
                "obligation %s: link-budget reference %r unresolved; deferring",
                obligation.subject_ref,
                path,
            )
            return Err(
                Deferral(
                    reason="given_unresolved",
                    detail=(
                        f"link-budget reference {path!r} (port {port!r}) did "
                        "not resolve to a value through the entity DB"
                    ),
                )
            )
        inputs[port] = Interval(lo=value, hi=value)
    _log.debug(
        "translated link-budget claim subject=%s -> %s limit=%g inputs=%s",
        obligation.subject_ref,
        _LINK_KIND,
        limit,
        sorted(inputs),
    )
    return Ok(
        DischargeRequest(
            claim_kind=_LINK_KIND,
            limit=limit,
            inputs=inputs,
            deterministic=True,
            regimes=_regimes_for(_LINK_KIND),
        )
    )


def translate(
    obligation: Obligation,
    *,
    cost_context: CostContext | None = None,
    frame_context: FrameContext | None = None,
) -> Result[DischargeRequest, Deferral]:
    """Lower ``obligation`` to a :class:`DischargeRequest`, or a deferral.

    Only the scalar-comparison claim form (``lhs op rhs``) lowers; the
    claim kind is the claim name if present, else the ``lhs`` text. A
    non-scalar form, an unknown comparator, or a non-literal bound each
    yields an explicit :class:`Deferral` the caller surfaces (never a
    silent pass). ``cost_context`` (WO-54 deliverable 4) is the build's
    cost-profile resolution state; an `mfg.cost` obligation (marked by
    the lowering's ``cost_subject`` given field) lowers through
    :func:`_translate_cost` against it. ``frame_context`` (WO-48 close-out
    follow-up) is the build's std.civil section/material resolution
    state; a calcite structural claim carrying a `kind: frame`
    `PayloadRef` (calcite/03 sec. 5) lowers through :func:`_translate_frame`
    against it.
    """
    form = obligation.claim.form
    if isinstance(form, ClaimForm1) and form.op == "conforms":
        return _translate_conformance(obligation)
    if isinstance(form, ClaimForm1) and form.op == "implies":
        return _translate_realization(obligation)
    if isinstance(form, (ClaimForm2, ClaimForm3, ClaimForm4, ClaimForm5, ClaimForm6)):
        return _translate_temporal(obligation, form)
    if not isinstance(form, ClaimForm1):
        return Err(
            Deferral(
                reason="non_scalar_claim",
                detail=f"claim form {type(form).__name__} is not a scalar comparison",
            )
        )
    # A frame-referencing structural predicate (calcite/03 sec. 5) hides
    # its comparator AFTER a full call expression, not at `rhs`'s head --
    # `_split_comparator` cannot see it, so this is checked first. Gated
    # on an ACTUAL `kind: frame` PayloadRef (not just a matching call
    # name): a non-calcite `mech.deflection(...)`-shaped claim with no
    # frame payload (e.g. a hematite beam-sag check) must keep falling
    # through to the ordinary path, preserving its existing `unsupported_
    # op` deferral rather than a frame-specific one it does not earn.
    has_frame_ref = any(r.kind == "frame" for r in obligation.payloads or ())
    if form.op == "require" and has_frame_ref:
        frame_split = _split_frame_predicate(form.rhs)
        if frame_split is not None:
            return _translate_frame(obligation, frame_split, frame_context)
    # The claim's sense (upper/lower) is the model signature's to declare
    # (regolith/07 sec. 4); here we only reject comparators that do not
    # lower to a one-sided scalar bound the harness can charge eps against.
    # The comparator may sit in `op` OR at the head of `rhs` (the core's
    # `op="require"` placeholder form) -- recover it either way.
    split = _split_comparator(form.op, form.rhs)
    if split is None:
        return Err(
            Deferral(reason="unsupported_op", detail=f"comparator {form.op!r} defers")
        )
    comparator, bound_text = split
    cost_fields = _load_fields(obligation.given.loads)
    if _COST_SUBJECT_FIELD in cost_fields:
        return _translate_cost(obligation, cost_fields, bound_text, cost_context)
    limit = _parse_float(bound_text)
    if limit is None:
        # D103: a general comparison whose bound is not a bare literal
        # may still be the link-budget shape, whose reference terms the
        # core resolved into `given.refs` (the Kestrel downlink). Only
        # when it is NOT link-shaped does the honest unresolved-limit
        # deferral stand.
        link = _try_link_budget(obligation, form)
        if link is not None:
            return link
        return Err(
            Deferral(
                reason="unresolved_limit", detail=f"bound {bound_text!r} not literal"
            )
        )
    claim_kind = obligation.claim.name or form.lhs
    # D97 (sec. 8.4): resolve every named given honestly -- a load line
    # that never became a numeric interval defers naming the given,
    # never a silent drop.
    resolved = resolve_givens(obligation.given.loads)
    if resolved.is_err:
        given_error = resolved.danger_err
        _log.info(
            "obligation %s: given %r unresolved (%s)",
            obligation.subject_ref,
            given_error.given,
            given_error.detail,
        )
        return Err(given_error.as_deferral())
    inputs = resolved.danger_ok
    regimes = _regimes_for(claim_kind)
    _log.debug(
        "translated obligation subject=%s -> claim_kind=%s limit=%g op=%s "
        "inputs=%s regimes=%s",
        obligation.subject_ref,
        claim_kind,
        limit,
        comparator,
        sorted(inputs),
        regimes,
    )
    return Ok(
        DischargeRequest(
            claim_kind=claim_kind,
            limit=limit,
            inputs=inputs,
            deterministic=True,
            regimes=regimes,
        )
    )
