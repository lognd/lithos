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
from collections.abc import Mapping
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
    PayloadRef,
)
from regolith.harness import DischargeRequest, Interval
from regolith.harness.models.beam_bending import CLAIM_KIND as _CANTILEVER_KIND
from regolith.harness.models.beam_bending import INPUTS as _CANTILEVER_INPUTS
from regolith.harness.models.beam_service_deflection import (
    CLAIM_KIND as _MECH_DEFLECTION_KIND,
)
from regolith.harness.models.beam_utilization import CLAIM_KIND as _CIVIL_UTIL_KIND
from regolith.harness.models.bearing_life import CLAIM_KIND as _BEARING_L10_KIND
from regolith.harness.models.bearing_life import INPUTS as _BEARING_L10_INPUTS
from regolith.harness.models.bearing_pressure import CLAIM_KIND as _CIVIL_BEARING_KIND
from regolith.harness.models.bolted_joint import CLAIM_KIND as _BOLT_JOINT_KIND
from regolith.harness.models.bolted_joint import INPUTS as _BOLT_JOINT_INPUTS
from regolith.harness.models.cam.models import (
    CLAIM_COLLISION as _CAM_COLLISION_KIND,
)
from regolith.harness.models.cam.models import CLAIM_COVERAGE as _CAM_COVERAGE_KIND
from regolith.harness.models.cam.models import CLAIM_ENVELOPE as _CAM_ENVELOPE_KIND
from regolith.harness.models.cam.models import CLAIM_PARSE as _CAM_PARSE_KIND
from regolith.harness.models.cam.models import CLAIM_REMOVAL as _CAM_REMOVAL_KIND
from regolith.harness.models.cam.models import (
    MACHINE_PORT as _CAM_MACHINE_PORT,
)
from regolith.harness.models.cam.models import PLAN_KIND as _CAM_PLAN_KIND
from regolith.harness.models.cam.models import PLAN_PORT as _CAM_PLAN_PORT
from regolith.harness.models.cam.models import TABLE_KIND as _CAM_TABLE_KIND
from regolith.harness.models.cam.models import TARGET_PORT as _CAM_TARGET_PORT
from regolith.harness.models.cam.models import (
    TOOLING_PORT as _CAM_TOOLING_PORT,
)
from regolith.harness.models.cam.records import MachineRecord, StockTarget, ToolRecord
from regolith.harness.models.conformance import CLAIM_KIND_LOWER, CLAIM_KIND_UPPER
from regolith.harness.models.cost_common import CLAIM_KIND as _COST_KIND
from regolith.harness.models.cost_common import BomLine
from regolith.harness.models.dfm.models import (
    CLAIM_KIND as _MANUFACTURABLE_KIND,
)
from regolith.harness.models.dfm.models import (
    MACHINE_PORT as _DFM_MACHINE_PORT,
)
from regolith.harness.models.dfm.models import (
    PART_PORT as _DFM_PART_PORT,
)
from regolith.harness.models.dfm.models import (
    TABLE_KIND as _DFM_TABLE_KIND,
)
from regolith.harness.models.dfm.models import (
    TOOLS_PORT as _DFM_TOOLS_PORT,
)
from regolith.harness.models.dfm.records import MILL_FAMILY as _DFM_MILL_FAMILY
from regolith.harness.models.dfm.records import DfmToolSet
from regolith.harness.models.fluid_pressure_drop import CLAIM_KIND as _FLUID_DP_KIND
from regolith.harness.models.fluid_pressure_drop import INPUTS as _FLUID_DP_INPUTS
from regolith.harness.models.hdl.models import CLAIM_BUILD as _HDL_BUILD_KIND
from regolith.harness.models.hdl.models import (
    CLAIM_EQUIV_DIRECTED as _HDL_EQUIV_DIRECTED_KIND,
)
from regolith.harness.models.hdl.models import CLAIM_SIM_ASSERT as _HDL_SIM_ASSERT_KIND
from regolith.harness.models.hdl.models import SRC_KIND as _HDL_SRC_KIND
from regolith.harness.models.hdl.models import SRC_PORT as _HDL_SRC_PORT
from regolith.harness.models.link_budget import CLAIM_KIND as _LINK_KIND
from regolith.harness.models.link_budget import INPUTS as _LINK_INPUTS
from regolith.harness.models.lumped_thermal import CLAIM_KIND as _THERMO_KIND
from regolith.harness.models.lumped_thermal import INPUTS as _THERMO_INPUTS
from regolith.harness.models.post_embedment import CLAIM_KIND as _CIVIL_EMBEDMENT_KIND
from regolith.harness.models.workload_realization import CLAIM_KIND as _REALIZATION_KIND
from regolith.logging_setup import get_logger
from regolith.orchestrator.dfm_staging import (
    CLAIM_TOKEN_FAMILIES as _DFM_TOKEN_FAMILIES,
)
from regolith.orchestrator.dfm_staging import (
    GROUNDED_FAMILIES as _DFM_GROUNDED_FAMILIES,
)
from regolith.orchestrator.dfm_staging import derive_part_facts
from regolith.orchestrator.plan_staging import resolve_plan_bytes, stage_record

if TYPE_CHECKING:
    # Runtime-lazy: `costing`/`frame_resolve`/`plan_staging` import this
    # module's `Deferral` consumers transitively through the
    # orchestrator package; the type-only import keeps the layering
    # acyclic (the `model.py` resolver precedent).
    from regolith.orchestrator.costing import CostContext
    from regolith.orchestrator.dfm_staging import DfmContext
    from regolith.orchestrator.frame_resolve import (
        FrameClaimBounds,
        FrameContext,
        ResolvedMember,
    )
    from regolith.orchestrator.plan_staging import PlanContext
    from regolith.orchestrator.si_stackups import SiContext

_log = get_logger(__name__)

# The Rust lowering's structured cost-claim markers in `given.loads`
# (WO-54 deliverable 1: `push_cost_claim_obligation`). One home for the
# strings on the Python side.
_COST_SUBJECT_FIELD = "cost_subject"
_COST_PROFILE_FIELD = "cost_profile"

# WO-69: the `push_plan_obligations`/`plan_obligation` Rust lowering's
# structured `given.loads` markers (`crates/regolith-lower/src/
# claims.rs`) -- one home for the strings on the Python side, same
# split as the cost fields above.
_PLAN_REF_FIELD = "plan_ref"
_PLAN_DIALECT_FIELD = "plan_dialect"
_CAM_MACHINE_REF_FIELD = "cam_machine_ref"
_CAM_TOOLING_REF_FIELD = "cam_tooling_ref"
_RESOLUTION_MM_FIELD = "resolution_mm"

# The five `cam.*` claim kinds `push_plan_obligations` emits (WO-67's
# landed `std.cam` pack; verbatim match to `regolith.harness.models.
# cam.models`'s registered `ModelSignature.claim_kind`s) -> the payload
# ports/kinds each needs (mirrors each model's own `_payload_kinds()`,
# ONE home here so a port drifting out of sync with the pack is a
# single edit, not five).
_CAM_CLAIM_KINDS = frozenset(
    {
        _CAM_PARSE_KIND,
        _CAM_ENVELOPE_KIND,
        _CAM_COLLISION_KIND,
        _CAM_REMOVAL_KIND,
        _CAM_COVERAGE_KIND,
    }
)
# WO-82: the `hdl.*` claim kinds' forward-looking `given.loads` marker
# names (NO Rust-side lowering emits these yet -- see this WO's ledger:
# building the obligation-emission half for `impl ... by extern(ref,
# <regime>)` -> `hdl.*` obligations is Rust work in `regolith-lower`
# outside this WO's `Language: Python` header, exactly the WO-67/WO-69
# precedent this mirrors. `_translate_hdl` is wired NOW so that
# whichever future WO adds the emission only has to match these two
# field names -- never invented as part of this dispatch's own scope).
_HDL_SRC_REF_FIELD = "hdl_src_ref"
_HDL_REGIME_FIELD = "hdl_regime"
_HDL_CLAIM_KINDS = frozenset(
    {_HDL_BUILD_KIND, _HDL_SIM_ASSERT_KIND, _HDL_EQUIV_DIRECTED_KIND}
)

_CAM_NEEDS_MACHINE = frozenset({_CAM_ENVELOPE_KIND})
_CAM_NEEDS_TARGET = frozenset(
    {_CAM_COLLISION_KIND, _CAM_REMOVAL_KIND, _CAM_COVERAGE_KIND}
)
_CAM_NEEDS_TOOLING = frozenset({_CAM_ENVELOPE_KIND, _CAM_REMOVAL_KIND})
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
# WO-48's own precedent). Forms absent from `_FRAME_MODEL_KIND` below
# defer naming the missing model.
_FRAME_FORM_NAMES: tuple[str, ...] = (
    "civil.utilization",
    "mech.deflection",
    "civil.story_drift",
    "civil.bearing_pressure",
    "mech.first_mode",
    # WO-85/D194: declared embedment depth vs the governing bound.
    "civil.embedment",
)

# Frame-referencing call form -> the harness model's registered claim
# kind (NOT always string-identical to the call name: `mech.deflection`
# the corpus writes maps to `mech.beam.service_deflection`, the model's
# own registry key -- see `beam_service_deflection.py`'s module doc).
_FRAME_MODEL_KIND: dict[str, str] = {
    "civil.utilization": _CIVIL_UTIL_KIND,
    "mech.deflection": _MECH_DEFLECTION_KIND,
    "civil.embedment": _CIVIL_EMBEDMENT_KIND,
    # Cycle 33/D196: reaction/area vs the soil allowable.
    "civil.bearing_pressure": _CIVIL_BEARING_KIND,
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


# The `mech.bolt.joint_separation`/`mech.bearing.l10_hours` call forms
# (WO-72 coordinator wiring dispatch): a NON-frame `op="require"` call
# predicate whose comparator also sits after the full call expression.
# Kept as a SEPARATE list/split (not folded into `_FRAME_FORM_NAMES`)
# because these claims carry no `kind: frame` PayloadRef -- gating them
# on `has_frame_ref` the way `_split_frame_predicate` is gated would
# wrongly defer them.
_BOLT_JOINT_FORM_NAMES: tuple[str, ...] = (_BOLT_JOINT_KIND,)
_BEARING_L10_FORM_NAMES: tuple[str, ...] = (_BEARING_L10_KIND,)
# WO-94 (D196.1): the fluorite `fluids.dp(...)` single-segment
# Darcy-Weisbach call form -- same non-frame call-form shape as the
# bolt/bearing pair above, matched by the same `_split_named_call_
# predicate`/`_match_call_lhs` pair.
_FLUID_DP_FORM_NAMES: tuple[str, ...] = (_FLUID_DP_KIND,)
# WO-86: `mech.cg(members=[...])` -- the uav_talon CG/moment-budget
# ask (F112). NOT a stdlib/grammar addition (`path-or-call` already
# accepts any dotted name, grammar.ebnf) and NOT a registered harness
# `CLAIM_KIND` (no model discharges it in v1): the keystone finding
# (WO-86 deliverable 1) is that `mech.mass(all)` -- the "landed
# precedent" the WO cites -- has no numeric contribution wiring
# either (`close_budget` is called with an empty contributions slice
# in every `budget` block, `regolith-lower/src/contracts.rs`; no
# evaluator anywhere resolves `mech.mass(...)` to a literal), and part
# positions are DECLARED nowhere in the corpus (mounts carry geometry
# constructors -- `origin: spar.axis & spar.root_face` -- never a
# scalar offset). A weighted-sum CG closure has nothing to sum. This
# form is matched here ONLY so the claim forms a real obligation and
# defers with that exact named-input reason (`_translate_cg_moment`)
# instead of falling through to the generic `unsupported_op` deferral,
# which would not name the missing input. Reopens per WO-70's W2
# criterion (a location/moment budget-math `kind=` lands, D49
# extension) AND once declared part-position data exists.
_CG_MOMENT_KIND = "mech.cg"
_CG_MOMENT_FORM_NAMES: tuple[str, ...] = (_CG_MOMENT_KIND,)
# WO-93 dispatch-note follow-up: the `thermo.temperature(<subject>)`
# call form (cubesat `fpga_ceiling`-style claims) whose SOURCE call
# name ("thermo.temperature") differs from the registered model's
# `CLAIM_KIND` ("thermo.junction_temperature", D94's WHAT-is-claimed
# name) -- unlike the bolt/bearing/fluid_dp triples above, this call
# form is matched by its own name, then translated UNDER the model's
# claim kind, never the source form name or the claim's own label
# (the bug this fixes: `translate()`'s generic fallback used to read
# `obligation.claim.name` -- the corpus label `fpga_ceiling` -- as the
# claim kind, so the claim never reached `thermo_lumped_steady@1`).
_THERMO_FORM_NAMES: tuple[str, ...] = ("thermo.temperature",)

# WO-109 (F130 Class B / F126.1 general half): a `mech.deflection(...)`
# call with NO `kind: frame` payload (a machined-part cantilever tip
# claim over realized geometry -- printer_k1/arm_a6's `payload_ok`/
# `payload_deflection`/`housing_deflection`, distinct from the frame-
# referencing case `_FRAME_MODEL_KIND` already routes) is the
# `mech.beam.cantilever_deflection` claim kind (`beam_bending.py`) --
# the SAME call form the WO-97/D209 optimizer coupling
# (`optimize_sketch.CANTILEVER_CALL_FORM`) already recognizes for its
# bounded-slot search, landed here for the ORDINARY (non-optimized)
# obligation path this WO closes. Matched by the same non-frame
# after-the-call comparator shape as bolt/bearing/fluid_dp/thermo
# above (checked unconditionally on `op == "require"`, since the frame
# check earlier in `translate()` already returned for any claim that
# DOES carry a frame payload).
_CANTILEVER_FORM_NAMES: tuple[str, ...] = ("mech.deflection",)

# WO-109: the corpus's bare `mfg.unit_cost(qty=...)` call form (no
# `given cost_subject=` marker) -- one home for the string, mirrors
# every other call-form-names constant above.
_COST_CALL_FORM_NAMES: tuple[str, ...] = ("mfg.unit_cost",)

# WO-78 (charter 35 sec. 1.2-1.3): the SI claim call forms. The claim
# kinds and model input ports below are feldspar's WO-25 pack-exposure
# strings VERBATIM (`feldspar.pack.models`); feldspar is an OPTIONAL
# pack regolith never imports (AD-19), so the strings are spelled here
# -- ONE Python-side home, pinned against the installed pack's
# registered keys by `tests/orchestrator/test_translate_si.py`.
_SI_IMPEDANCE_FORM_NAMES: tuple[str, ...] = ("elec.impedance",)
_SI_TERMINATION_FORM_NAMES: tuple[str, ...] = ("elec.termination",)
_SI_MICROSTRIP_KINDS = {
    "lo": "elec.si.microstrip_z0.lo",
    "hi": "elec.si.microstrip_z0.hi",
}
_SI_STRIPLINE_KINDS = {
    "lo": "elec.si.stripline_z0.lo",
    "hi": "elec.si.stripline_z0.hi",
}
_SI_MICROSTRIP_PORTS = {
    "w": "elec.si.microstrip.w",
    "h": "elec.si.microstrip.h",
    "t": "elec.si.microstrip.t",
    "er": "elec.si.microstrip.er",
}
_SI_STRIPLINE_PORTS = {
    "w": "elec.si.stripline.w",
    "b": "elec.si.stripline.b",
    "er": "elec.si.stripline.er",
}
# Termination scheme -> (claim kind, kwarg -> model port). Thevenin has
# two sized legs and ac_shunt two sized parts; each claim names its leg/
# part explicitly (one obligation per sized value -- the `within` halves'
# own one-model-instance-per-obligation posture).
_SI_TERMINATION_ROUTES: dict[tuple[str, str], tuple[str, dict[str, str]]] = {
    ("series", ""): (
        "elec.si.series_termination.rs",
        {
            "z0": "elec.si.series_termination.z0",
            "ro": "elec.si.series_termination.ro",
        },
    ),
    ("thevenin", "r1"): (
        "elec.si.thevenin_termination.r1",
        {
            "z0": "elec.si.thevenin_termination.z0",
            "vcc": "elec.si.thevenin_termination.vcc",
            "vbias": "elec.si.thevenin_termination.vbias",
        },
    ),
    ("thevenin", "r2"): (
        "elec.si.thevenin_termination.r2",
        {
            "z0": "elec.si.thevenin_termination.z0",
            "vcc": "elec.si.thevenin_termination.vcc",
            "vbias": "elec.si.thevenin_termination.vbias",
        },
    ),
    ("ac_shunt", "r"): (
        "elec.si.ac_shunt.r",
        {"z0": "elec.si.ac_shunt.z0"},
    ),
    ("ac_shunt", "c"): (
        "elec.si.ac_shunt.c",
        {
            "rise_time": "elec.si.ac_shunt.rise_time",
            "r": "elec.si.ac_shunt.r",
        },
    ),
}


def _split_named_call_predicate(
    rhs: str, names: tuple[str, ...]
) -> tuple[str, str, str] | None:
    """Split a `<call_name>(<args>) <comparator> <bound>` predicate into
    `(call_name, args_text, bound_text)` -- the non-frame analog of
    :func:`_split_frame_predicate`'s paren-walk, over an arbitrary
    `names` list. Returns `None` (an honest non-match, never a guess)
    when `rhs` does not open with one of `names` OR the call's `(`
    never closes within `rhs` (the WO-65-noted single-source-line `rhs`
    truncation for a claim whose args wrap onto a later line -- the
    caller falls through to the existing `unsupported_op` deferral,
    unchanged from before this call form had a model).
    """
    stripped = rhs.lstrip()
    for name in names:
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
        return None
    return None


def _match_call_lhs(lhs: str, names: tuple[str, ...]) -> tuple[str, str] | None:
    """Match a fully-resolved `<call_name>(<args>)` LHS (the shape
    `form.lhs` already has once the core's `split_general_comparison`
    cleanly finds one top-level comparator -- `regolith-lower::claims::
    split_general_comparison`) against one of `names`, returning
    `(call_name, args_text)`. Returns `None` when `lhs` is not exactly
    one whole call to a name in `names` (a substring match would wrongly
    fire on an expression that merely CONTAINS the call, e.g. `2 *
    mech.bolt.joint_separation(...)`, which this claim shape does not
    support anyway).
    """
    stripped = lhs.strip()
    for name in names:
        prefix = name + "("
        if stripped.startswith(prefix) and stripped.endswith(")"):
            return name, stripped[len(prefix) : -1]
    return None


# WO-110 (F130 census item 4, D232.2): the bare `manufacturable(
# <token>)` predicate -- the ONE undotted call form with a registered
# discharge channel (`mfg.manufacturable`). Matched in the
# `op == "require"` branch BEFORE the unmatched-call naming below (it
# would not match `_DOTTED_CALL` anyway; this keeps it off
# `unsupported_op`, its pre-WO-110 grave).
_MANUFACTURABLE_CALL = re.compile(r"^manufacturable\(\s*([a-z_]+)\s*\)\s*$")

# WO-109 deliverable 4: a whole `<dotted.path>(<args>)` call expression,
# ANY dotted path (at least one `.`, so a bare predicate name like
# `manufacturable(...)` never matches -- that shape stays on its
# existing deferral). Used by `translate()`'s generic fallback to route
# a label-named claim by its CALL PATH instead of its label, and by the
# `op == "require"` branch to NAME an unmatched call path instead of
# folding it into `unsupported_op`. DOTALL: a multi-line predicate's
# args may span source lines.
_DOTTED_CALL = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+)\((.*)\)$",
    re.DOTALL,
)


def _match_dotted_call(text: str) -> str | None:
    """The dotted call path when ``text`` is exactly one whole
    ``<dotted.path>(...)`` call expression, else ``None`` (an expression
    that merely CONTAINS a call -- ``2 * mech.f(x)`` -- never matches,
    same posture as :func:`_match_call_lhs`)."""
    match = _DOTTED_CALL.match(text.strip())
    return match.group(1) if match is not None else None


# The prefix analog: `<dotted.path>(` at the head of a predicate whose
# comparator trails the call (`op == "require"`'s shape).
_DOTTED_CALL_HEAD = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+)\("
)


def _leading_dotted_call(text: str) -> str | None:
    """The dotted call path when ``text`` OPENS with a
    ``<dotted.path>(...)`` call whose paren closes within ``text``
    (:func:`_split_named_call_predicate`'s paren-walk, generalized to
    any dotted name), else ``None``."""
    stripped = text.lstrip()
    match = _DOTTED_CALL_HEAD.match(stripped)
    if match is None:
        return None
    depth = 0
    for ch in stripped:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return match.group(1)
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


def frame_claim_bounds(build_payload: Mapping[str, object]) -> FrameClaimBounds:
    """Extract every frame-referencing claim bound the section search
    must satisfy (WO-65) from `build_payload`'s obligations, keyed the
    way `frame_resolve.search_free_section` consumes them.

    Lives HERE (not in `frame_resolve`) because this module is the ONE
    home of claim-form parsing (`_split_frame_predicate`/`_SPAN_BOUND`/
    `_parse_float`) -- the search and the discharge path must read the
    SAME bound from the same text or their verdicts drift. Only the two
    modeled forms contribute (a `civil.story_drift` claim cannot gate a
    search it could never discharge):

    - `mech.deflection(<member>, ...) <= <member>.span / <N>` ->
      `deflection_divisors[(frame, member)] = N` (the TIGHTEST -- max
      `N` -- when several claims bound one member).
    - `civil.utilization(<X>.members.all | <member>, ...) <= <limit>`
      -> `utilization_limit_all[frame]` / `utilization_limits[(frame,
      member)]` (the TIGHTEST -- min limit -- when several apply).

    A bound this parser cannot reduce contributes nothing (the claim
    itself still defers by name at translate time -- no silent gate,
    no invented one).
    """
    from regolith.orchestrator.frame_resolve import FrameClaimBounds

    deflection: dict[tuple[str, str], float] = {}
    util_all: dict[str, float] = {}
    util_member: dict[tuple[str, str], float] = {}
    obligations = build_payload.get("obligations")
    if not isinstance(obligations, list):
        obligations = []
    for raw in obligations:
        if not isinstance(raw, dict):
            continue
        claim = raw.get("claim")
        if not isinstance(claim, dict):
            continue
        form = claim.get("form")
        if not isinstance(form, dict):
            continue
        rhs = form.get("rhs")
        if not isinstance(rhs, str):
            continue
        payloads = raw.get("payloads")
        if not isinstance(payloads, list):
            payloads = []
        frame_name = next(
            (
                p.get("origin")
                for p in payloads
                if isinstance(p, dict) and p.get("kind") == "frame"
            ),
            None,
        )
        if not isinstance(frame_name, str) or not frame_name:
            continue
        split = _split_frame_predicate(rhs)
        if split is None:
            continue
        form_name, args_text, bound_text = split
        subject = args_text.split(",", 1)[0].strip()
        if form_name == "mech.deflection":
            span_match = _SPAN_BOUND.match(bound_text)
            if span_match is None:
                continue
            divisor = float(span_match.group(2))
            if divisor <= 0.0:
                continue
            key = (frame_name, subject)
            deflection[key] = max(deflection.get(key, 0.0), divisor)
        elif form_name == "civil.utilization":
            limit = _parse_float(bound_text)
            if limit is None:
                continue
            if subject.endswith(".members.all"):
                util_all[frame_name] = min(
                    util_all.get(frame_name, float("inf")), limit
                )
            else:
                key = (frame_name, subject.rsplit(".", 1)[-1])
                util_member[key] = min(util_member.get(key, float("inf")), limit)
    bounds = FrameClaimBounds(
        deflection_divisors=deflection,
        utilization_limit_all=util_all,
        utilization_limits=util_member,
    )
    _log.debug(
        "frame claim bounds: %d deflection divisor(s), %d members.all "
        "utilization limit(s), %d per-member utilization limit(s)",
        len(deflection),
        len(util_all),
        len(util_member),
    )
    return bounds


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


def _pin_model(
    result: Result[DischargeRequest, Deferral], model_pin: str | None
) -> Result[DischargeRequest, Deferral]:
    """Thread a claim's rung-5 ``model=<ident>`` pin (WO-80 deliverable
    2; ``regolith/12`` sec. 2 rung 5) onto a successfully translated
    request, in ONE place -- every claim-form path in :func:`translate`
    routes its `Ok(DischargeRequest)` through this instead of each
    threading `model_pin` through its own constructor, so a future
    translator inherits pin-honoring for free (NO DUPLICATION). A
    `Deferral` (`Err`) or an un-pinned claim (`model_pin is None`)
    passes through unchanged.
    """
    if result.is_err or model_pin is None:
        return result
    return Ok(result.danger_ok.model_copy(update={"model_pin": model_pin}))


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
    the single ``impl_bound`` input = the realization's bound).

    D195 (WO-92): when only the SPEC side resolved (a literal promise, or a
    parametric promise closed by the impl header's generic pin), the core
    threads ``conformance_sense``/``spec_bound``/``conformance_field``
    WITHOUT an ``impl_bound``; that one-sided shape defers with the distinct
    TEACHING reason ``conformance_impl_bound_missing`` naming the resolved
    spec bound, the field, and the two honest paths to discharge. Bindings
    with no scalar window on either side keep the blanket
    ``conformance_windows_unresolved`` -- the compiler never invents a
    window the source did not state.
    """
    fields = _load_fields(obligation.given.loads)
    sense = fields.get("conformance_sense")
    spec_text = fields.get("spec_bound")
    impl_text = fields.get("impl_bound")
    field_name = fields.get("conformance_field")
    if sense is not None and spec_text is not None and impl_text is None:
        comparator = {"upper": "<=", "lower": ">="}.get(sense, sense)
        field = field_name or "<field>"
        _log.info(
            "conforms obligation subject=%s defers: spec side resolved "
            "(%s %s %s) but the impl asserts no bound",
            obligation.subject_ref,
            field,
            comparator,
            spec_text,
        )
        return Err(
            Deferral(
                reason="conformance_impl_bound_missing",
                detail=(
                    f"the spec side resolved ({field} {comparator} {spec_text}) "
                    "but the impl asserts no matching bound; to discharge, "
                    f"either declare a `{field}:` comparator bound in the impl "
                    "body, or realize the quantity through the realized-fact "
                    "channel (D195)"
                ),
            )
        )
    if sense is None or spec_text is None or impl_text is None:
        return Err(
            Deferral(
                reason="conformance_windows_unresolved",
                detail=(
                    "conforms obligation carries no resolved "
                    "conformance_sense/spec_bound/impl_bound windows "
                    "(no scalar bound on either side, D195)"
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


def _translate_cg_moment(
    obligation: Obligation,
) -> Result[DischargeRequest, Deferral]:
    """Lower a `mech.cg(members=[...])` claim (WO-86, F112's uav CG/
    moment-budget ask): sum(m_i * x_i) over declared part masses and
    positions, compared against a declared envelope -- mass-budget
    arithmetic with a position weight (the WO's own framing).

    This ALWAYS defers in v1: the WO's deliverable-1 keystone finding is
    that neither half of that sum is available from declared data today.
    `mech.mass(all)` -- the budget arithmetic this claim would extend --
    has no numeric contribution wiring (`close_budget` in
    `regolith-lower/src/contracts.rs` runs every `budget` block's check
    against an EMPTY contributions slice; nothing resolves `mech.mass
    (...)`  to a literal anywhere in the pipeline), so there is no
    landed mass arithmetic to add a position weight to. And part
    positions are declared nowhere in this corpus: every mount/mating
    `origin:` is a geometry constructor (`spar.axis & spar.root_face`),
    never a scalar offset a weighted sum could consume -- the WO is
    explicit that realized geometry is out of scope for v1 (that is the
    future realized-fact channel's job).

    Per AD-22 (no invented `kind=` budget-math syntax) and the WO's own
    instruction to escalate rather than invent, this stays a translate-
    layer-only obligation that defers HONESTLY, naming both missing
    inputs, rather than silently passing or inventing a numeric model
    over undeclared data (INV-24 totality).
    """
    _log.debug(
        "translated cg-moment obligation subject=%s -> honest defer "
        "(no mass-budget contribution wiring, no declared part positions)",
        obligation.subject_ref,
    )
    return Err(
        Deferral(
            reason="cg_moment_no_declared_position_data",
            detail=(
                "mech.cg(...) needs per-part mass AND position to form "
                "sum(m_i * x_i): mech.mass(...) is not yet wired to any "
                "numeric contribution (close_budget always checks an "
                "empty contributions list, regolith-lower/src/"
                "contracts.rs), and no declared part position/placement "
                "offset exists in this corpus (mounts carry geometry "
                "constructors, not scalar offsets); WO-86 keeps this "
                "claim honestly deferred rather than inventing either "
                "input (WO-70 W2 reopen criterion: a location/moment "
                "budget-math kind lands, D49 extension, AND declared "
                "part-position data exists)"
            ),
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
    properties + resolved gravity demand (line + stationed point loads
    + column axial via `frame_resolve.member_demand`, WO-85/D194).

    Every member the subject names must resolve BOTH its section/
    material (:func:`frame_resolve.resolve_member`) AND its own
    demand for this to discharge -- any single unresolved member (a
    `free` section, or a member with no resolvable demand source)
    defers the whole claim honestly, naming that member. (Since
    D194's per-member obligation expansion at Rust lowering, a
    `.members.all` group reaches this translator as N single-member
    obligations, so "the whole claim" IS one member's claim -- one
    indeterminate member no longer defers its siblings.)
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

    worst_bending = 0.0
    worst_axial = 0.0
    worst = 0.0
    for member in members.danger_ok:
        demand = frame_resolve.member_demand(frame, member)
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
        resolved = demand.danger_ok
        moment = resolved.moment_nm(member.length_m)
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
        bending_util = abs(moment) / (member.s_m3 * member.fy_pa)
        # WO-85 deliverable 3: the axial interaction term is REAL now
        # (column gravity load paths) -- the old "axial pinned at 0"
        # normalization is dead.
        axial_util = abs(resolved.axial_n) / (member.area_m2 * member.fy_pa)
        if bending_util + axial_util > worst:
            worst = bending_util + axial_util
            worst_bending = bending_util
            worst_axial = axial_util
    _log.debug(
        "translated civil.utilization obligation subject=%s limit=%g "
        "worst=%g (bending=%g axial=%g)",
        obligation.subject_ref,
        limit,
        worst,
        worst_bending,
        worst_axial,
    )
    return Ok(
        DischargeRequest(
            claim_kind=_CIVIL_UTIL_KIND,
            limit=limit,
            inputs=_civil_utilization_inputs(worst_bending, worst_axial),
            deterministic=True,
            regimes=_regimes_for(_CIVIL_UTIL_KIND),
        )
    )


def _civil_utilization_inputs(
    bending_util: float, axial_util: float
) -> dict[str, Interval]:
    """The `BeamUtilizationModel` input vector that reproduces an
    already-computed interaction pair exactly (unit section/area/fy,
    so the model's `|M|/(Z*Fy) + |P|/(A*Fy)` evaluates to
    `bending_util + axial_util`) -- this translator does the real
    per-member interaction arithmetic itself (each member has its own
    section/material), so it stages a normalized vector rather than
    re-deriving the model's formula in reverse."""
    return {
        "moment_demand": Interval(lo=bending_util, hi=bending_util),
        "axial_demand": Interval(lo=axial_util, hi=axial_util),
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
    material properties + resolved gravity demand. Stationed point
    loads (WO-85/D194) fold into the model's UDL input through the
    exact (conservatively summed) equivalence --
    :meth:`frame_resolve.MemberDemand.deflection_w_equiv`.
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

    demand = frame_resolve.member_demand(frame, member)
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
    w_load = demand.danger_ok.deflection_w_equiv(member.length_m)

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


def _translate_civil_embedment(
    obligation: Obligation,
    frame: dict[str, object],
    subject: str,
    bound_text: str,
) -> Result[DischargeRequest, Deferral]:
    """Lower a `civil.embedment(<post>) >= <depth>` claim (WO-85/D194,
    the `civil.bearing_pressure` reaction-based closed-form pattern):
    the post's DECLARED embedment depth (its `EmbeddedPost(depth=...)`
    transfer, `FrameTransfer.depth`) against the GOVERNING lower bound
    -- the written bound (already SI-resolved by the Rust lowering's
    site-datum substitution, so `bound_text` is bare metres) folded
    with the code-required depth from lateral demand at grade.

    Required-depth honesty (v1): the load vocabulary is gravity-only
    (`FrameLoad.direction`), so the resolvable lateral demand at grade
    is exactly zero and the IBC 1807.3-family nonconstrained-earth
    closed form (`d = A/2 * (1 + sqrt(1 + 4.36*h/A))`, `A` demand-
    proportional) degenerates to a required depth of 0 -- carried as a
    real model input so the evidence names it, not silently omitted.
    When a lateral vocabulary lands, this translator computes the full
    form without touching the model.
    """
    limit = _parse_float(bound_text)
    if limit is None:
        return Err(
            Deferral(
                reason="unresolved_limit",
                detail=(
                    f"embedment bound {bound_text!r} not literal (an "
                    "unresolved/ambiguous site datum stays symbolic at "
                    "lowering -- see claims.rs's resolve_embedment_site_bound)"
                ),
            )
        )
    member_id = subject.rsplit(".", 1)[-1]
    from regolith.orchestrator import frame_resolve

    declared_m = frame_resolve.declared_embedment_m(frame, member_id)
    if declared_m is None:
        return Err(
            Deferral(
                reason="frame_embedment_undeclared",
                detail=(
                    f"member {member_id!r} has no transfer carrying a "
                    "declared embedment depth (`EmbeddedPost(depth=...)`) "
                    "in this frame's `transfers` -- nothing to check the "
                    "bound against, not fabricated"
                ),
            )
        )
    # Gravity-only vocabulary -> zero resolvable lateral demand ->
    # required-from-demand degenerates to 0 (see the docstring).
    required_m = 0.0
    effective_limit = max(limit, required_m)
    _log.debug(
        "translated civil.embedment obligation subject=%s declared=%gm "
        "bound=%gm required=%gm",
        obligation.subject_ref,
        declared_m,
        limit,
        required_m,
    )
    return Ok(
        DischargeRequest(
            claim_kind=_CIVIL_EMBEDMENT_KIND,
            limit=effective_limit,
            inputs={
                "declared_depth": Interval(lo=declared_m, hi=declared_m),
                "required_depth": Interval(lo=required_m, hi=required_m),
            },
            deterministic=True,
            regimes=_regimes_for(_CIVIL_EMBEDMENT_KIND),
        )
    )


def _translate_civil_bearing(
    obligation: Obligation,
    frame: dict[str, object],
    subject: str,
    bound_text: str,
) -> Result[DischargeRequest, Deferral]:
    """Lower a `civil.bearing_pressure(<footing>) <= <soil allowable>`
    claim (cycle 33/D196, the `civil.embedment`/`post_embedment.py`
    reaction-based closed-form pattern): the footing's resolved
    gravity reaction (`frame_resolve.reaction_into_n`, WO-85
    deliverable 3's axial-reaction machinery generalized to any
    transfer target, not only column-role members) divided by its
    declared bearing area (`frame_resolve.declared_footing_area_m2`)
    against the claim's own comparator bound.

    Two honest, named deferrals this v1 translator can still hit (see
    `bearing_pressure.py`'s module doc for the full rationale) when the
    design supplies neither piece of data:

    - `unresolved_limit`: the `site.soil.bearing`/`<structure>.soil.
      bearing` comparator did not literalize. Since WO-96's bearing
      close-out the Rust lowering DOES substitute it -- `claims.rs`'s
      `resolve_embedment_site_bound` now resolves a `civil.bearing_
      pressure` bound to the conservative endpoint of the tested-
      capacity interval datum (`[150kPa, 210kPa]` -> `150kPa` for a
      `<=` allowable) -- so this deferral now only fires when no site
      declares that soil datum (or it is ambiguous), never for the
      ordinary corpus shape.
    - `footing_area_undeclared`: no transfer into the footing declares
      an area-unit bearing value. `std.civil`'s `BasePlate<anchors,
      bearing: area>` now carries an optional `bearing=` plate area
      (WO-96), threaded onto the generic `FrameTransfer.tributary`
      field; this deferral fires only when a design leaves it at the
      `0m2` default.
    """
    limit = _parse_float(bound_text)
    if limit is None:
        return Err(
            Deferral(
                reason="unresolved_limit",
                detail=(
                    f"bearing bound {bound_text!r} not literal (a "
                    "site.<path>/<structure>.soil.<path> comparator stays "
                    "symbolic at lowering for civil.bearing_pressure -- "
                    "Rust's site-datum substitution (claims.rs's "
                    "resolve_embedment_site_bound) only literalizes "
                    "civil.embedment bounds today)"
                ),
            )
        )
    footing_id = subject.rsplit(".", 1)[-1]
    from regolith.orchestrator import frame_resolve

    reaction_n, hit = frame_resolve.reaction_into_n(frame, footing_id)
    if not hit:
        return Err(
            Deferral(
                reason="frame_reaction_unresolved",
                detail=(
                    f"footing {footing_id!r} has no resolvable incoming "
                    "gravity load path in this frame's transfers "
                    "(Pinned/Moment/BasePlate) -- not fabricated"
                ),
            )
        )
    area_m2 = frame_resolve.declared_footing_area_m2(frame, footing_id)
    if area_m2 is None:
        return Err(
            Deferral(
                reason="footing_area_undeclared",
                detail=(
                    f"footing {footing_id!r} has no incoming transfer "
                    "declaring an area-unit `tributary` value (the generic "
                    "FrameTransfer.tributary field) -- std.civil's "
                    "BasePlate<anchors: string> connection class (every "
                    "corpus design's column-to-footing transfer) carries "
                    "no bearing-area parameter yet; not fabricated"
                ),
            )
        )
    _log.debug(
        "translated civil.bearing_pressure obligation subject=%s "
        "reaction=%gN area=%gm2 bound=%gPa",
        obligation.subject_ref,
        reaction_n,
        area_m2,
        limit,
    )
    return Ok(
        DischargeRequest(
            claim_kind=_CIVIL_BEARING_KIND,
            limit=limit,
            inputs={
                "reaction_n": Interval(lo=reaction_n, hi=reaction_n),
                "area_m2": Interval(lo=area_m2, hi=area_m2),
            },
            deterministic=True,
            regimes=_regimes_for(_CIVIL_BEARING_KIND),
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

    `civil.utilization`/`mech.deflection` (WO-48 deliverable 5),
    `civil.embedment` (WO-85/D194), and `civil.bearing_pressure`
    (cycle 33/D196) have a closed-form harness model; the other call
    forms honestly defer `no_frame_model`, naming the gap rather than
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
                    "(covered forms: civil.utilization/mech.deflection "
                    "(WO-48 deliverable 5), civil.embedment (WO-85/D194), "
                    "civil.bearing_pressure (cycle 33/D196))"
                ),
            )
        )
    subject = args_text.split(",", 1)[0].strip()
    if form_name == "civil.utilization":
        return _translate_civil_utilization(
            obligation, frame_context, frame, subject, bound_text
        )
    if form_name == "civil.embedment":
        return _translate_civil_embedment(obligation, frame, subject, bound_text)
    if form_name == "civil.bearing_pressure":
        return _translate_civil_bearing(obligation, frame, subject, bound_text)
    return _translate_mech_deflection(
        obligation, frame_context, frame, subject, bound_text
    )


def _split_top_level_args(args_text: str) -> list[str]:
    """Split a call's argument text on TOP-LEVEL commas (depth-aware, so
    a nested call in one argument -- ``under=p_cyl(95bar)`` -- does not
    fracture that argument in two)."""
    parts: list[str] = []
    depth = 0
    start = 0
    for i, ch in enumerate(args_text):
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(args_text[start:i])
            start = i + 1
    parts.append(args_text[start:])
    return [p.strip() for p in parts if p.strip()]


def _parse_call_kwargs(args_text: str) -> dict[str, Interval]:
    """Read every ``name=<literal>`` keyword argument off a call's
    argument text into a ``name -> Interval`` map (unit suffixes
    ignored, same convention as :func:`_parse_float` everywhere else in
    this module). A bare positional argument (the call's subject, e.g.
    a mating reference) or a non-literal keyword value (``under=
    p_cyl(95bar)``) is silently skipped here -- the caller decides
    which of its required names are still missing.
    """
    kwargs: dict[str, Interval] = {}
    for part in _split_top_level_args(args_text):
        if "=" not in part:
            continue
        name, value = part.split("=", 1)
        name = name.strip()
        interval = _parse_interval(value)
        if interval is not None:
            kwargs[name] = interval
    return kwargs


def _translate_call_kwargs_claim(
    obligation: Obligation,
    *,
    claim_kind: str,
    inputs_needed: tuple[str, ...],
    subject: str,
    args_text: str,
    bound_text: str,
) -> Result[DischargeRequest, Deferral]:
    """Lower a non-frame call-form claim (`mech.bolt.joint_separation`,
    `mech.bearing.l10_hours`) whose comparator hides after a full call
    expression (:func:`_split_named_call_predicate`).

    The model's own required input names (`inputs_needed`, each
    model's own `INPUTS`) are read as literal `name=value` KEYWORD
    ARGUMENTS on the call itself (`_parse_call_kwargs`). `given.loads`
    is consulted as a SECOND, lower-priority source: the ordinary
    part-level `loads:` BLOCK (D97 sec. 8.4), and -- since WO-94
    escalation 1 -- the inline claim-suffix `given x = y` form the
    fluorite corpus uses (`crates/regolith-lower/src/claims.rs`'s
    `split_claim_suffix_givens` threads each binding into `given.loads`
    for fluid obligations). An inline keyword argument on the call
    always wins over a `given.loads` entry of the same name.
    """
    limit = _parse_float(bound_text)
    if limit is None:
        return Err(
            Deferral(
                reason="unresolved_limit",
                detail=f"{claim_kind} bound {bound_text!r} not literal",
            )
        )
    inline = _parse_call_kwargs(args_text)
    given_resolved = resolve_givens(obligation.given.loads)
    given_inputs = given_resolved.danger_ok if given_resolved.is_ok else {}
    inputs = {**given_inputs, **inline}
    missing = sorted(name for name in inputs_needed if name not in inputs)
    if missing:
        return Err(
            Deferral(
                reason=f"{claim_kind}_inputs_missing",
                detail=(
                    f"{subject!r} is missing inputs {missing} (need "
                    f"{inputs_needed}; checked call kwargs and given.loads)"
                ),
            )
        )
    _log.debug(
        "translated %s obligation subject=%s member=%s limit=%g",
        claim_kind,
        obligation.subject_ref,
        subject,
        limit,
    )
    return Ok(
        DischargeRequest(
            claim_kind=claim_kind,
            limit=limit,
            inputs={name: inputs[name] for name in inputs_needed},
            deterministic=True,
            regimes=_regimes_for(claim_kind),
        )
    )


def _translate_bolted_joint(
    obligation: Obligation, split: tuple[str, str, str]
) -> Result[DischargeRequest, Deferral]:
    """Lower a `mech.bolt.joint_separation(<joint>, ...) >= <F_Kreq>`
    claim (the VDI 2230 residual-clamp lower bound `BoltedJointModel`
    discharges -- see `bolted_joint.py`'s module doc) against the
    joint's `given.loads` inputs (`f_preload`/`f_external`/`k_bolt`/
    `k_clamp`, the model's own `INPUTS`). The call's subject (a mating
    reference, e.g. a `BoltedFlange`/`BoltedPattern` mating such as
    `cnc_router`'s `BeamJoint`) is not itself resolved here -- no frame/
    geometry lookup for this claim shape, unlike `mech.deflection`.
    """
    _, args_text, bound_text = split
    subject = args_text.split(",", 1)[0].strip()
    return _translate_call_kwargs_claim(
        obligation,
        claim_kind=_BOLT_JOINT_KIND,
        inputs_needed=_BOLT_JOINT_INPUTS,
        subject=subject,
        args_text=args_text,
        bound_text=bound_text,
    )


def _translate_bearing_l10(
    obligation: Obligation, split: tuple[str, str, str]
) -> Result[DischargeRequest, Deferral]:
    """Lower a `mech.bearing.l10_hours(<pair>, ...) >= <hours>` claim
    (the ISO 281:2007 basic-L10 lower bound `BearingL10HoursModel`
    discharges -- see `bearing_life.py`'s module doc) against the
    bearing's `given.loads` inputs (`c_rating`/`p_load`/`speed_rpm`/
    `p_exponent`, the model's own `INPUTS`).
    """
    _, args_text, bound_text = split
    subject = args_text.split(",", 1)[0].strip()
    return _translate_call_kwargs_claim(
        obligation,
        claim_kind=_BEARING_L10_KIND,
        inputs_needed=_BEARING_L10_INPUTS,
        subject=subject,
        args_text=args_text,
        bound_text=bound_text,
    )


def _translate_cantilever_deflection(
    obligation: Obligation, split: tuple[str, str, str]
) -> Result[DischargeRequest, Deferral]:
    """Lower a non-frame `mech.deflection(<blank>, under=<F>) < <limit>`
    claim (WO-109/F130 Class B: the machined-part cantilever-tip case
    -- printer_k1 `payload_ok`, arm_a6 `payload_deflection`/
    `housing_deflection` -- distinct from the calcite frame-referencing
    `mech.deflection` claim `_translate_frame` already routes) against
    `beam_bending.py`'s `mech.beam.cantilever_deflection` model (the
    SAME kind the WO-97/D209 optimizer coupling drives directly for a
    bounded slot search, `optimize_sketch.py`). The claim's `under=<F>`
    load and the blank's `length`/`e_modulus`/`i_area` are almost never
    literal call kwargs in the corpus (`under=6.87N at mill.elbow_bore`,
    `under=interface_envelope(...)`) -- this v1 reads only literal
    kwargs plus `given.loads` (D97 sec. 8.4), same conservative posture
    as the bolt/bearing pair, so a claim whose inputs are not yet
    DECLARED honestly defers `mech.beam.cantilever_deflection_
    inputs_missing` naming exactly what is absent, never a fabricated
    value.
    """
    _, args_text, bound_text = split
    subject = args_text.split(",", 1)[0].strip()
    return _translate_call_kwargs_claim(
        obligation,
        claim_kind=_CANTILEVER_KIND,
        inputs_needed=_CANTILEVER_INPUTS,
        subject=subject,
        args_text=args_text,
        bound_text=bound_text,
    )


def _translate_fluid_dp(
    obligation: Obligation, split: tuple[str, str, str]
) -> Result[DischargeRequest, Deferral]:
    """Lower a `fluids.dp(<edge or edge span>) <= <limit>` claim (the
    single-segment Darcy-Weisbach upper bound `FluidPressureDropModel`
    discharges -- see `fluid_pressure_drop.py`'s module doc) against
    the edge's `given.loads` inputs (`friction_factor`/`length_m`/
    `diameter_m`/`density_kgm3`/`velocity_ms`, the model's own
    `INPUTS`). The call's subject (a flownet node pair, e.g.
    `riser_top -> group_in`) is not itself resolved here -- no
    realized-geometry lookup for this claim shape, same posture as
    `mech.bolt.joint_separation`.
    """
    _, args_text, bound_text = split
    subject = args_text.split(",", 1)[0].strip()
    return _translate_call_kwargs_claim(
        obligation,
        claim_kind=_FLUID_DP_KIND,
        inputs_needed=_FLUID_DP_INPUTS,
        subject=subject,
        args_text=args_text,
        bound_text=bound_text,
    )


def _translate_thermo(
    obligation: Obligation, split: tuple[str, str, str]
) -> Result[DischargeRequest, Deferral]:
    """Lower a `thermo.temperature(<subject>) <= <limit>` claim (the
    steady lumped-junction upper bound `LumpedThermalModel` discharges
    -- see `lumped_thermal.py`'s module doc) against the subject's
    `given.loads` inputs (`ambient`/`power`/`r_theta`, the model's own
    `INPUTS`). The call's subject (e.g. `payload.u_fpga.junction`) is
    not itself resolved here -- no frame/geometry lookup for this claim
    shape, same posture as `mech.bolt.joint_separation`/`fluids.dp`.
    """
    _, args_text, bound_text = split
    subject = args_text.split(",", 1)[0].strip()
    return _translate_call_kwargs_claim(
        obligation,
        claim_kind=_THERMO_KIND,
        inputs_needed=_THERMO_INPUTS,
        subject=subject,
        args_text=args_text,
        bound_text=bound_text,
    )


def _parse_call_symbol_kwargs(args_text: str) -> dict[str, str]:
    """Read every ``name=<bare word>`` keyword argument off a call's
    argument text (``role=microstrip``, ``stackup=jlc04161h_7628``) --
    the symbolic complement of :func:`_parse_call_kwargs`, which only
    keeps numeric-literal values. A value that parses as a number is
    skipped here (it belongs to the numeric map)."""
    kwargs: dict[str, str] = {}
    for part in _split_top_level_args(args_text):
        if "=" not in part:
            continue
        name, value = part.split("=", 1)
        value = value.strip()
        if _parse_float(value) is None and value:
            kwargs[name.strip()] = value
    return kwargs


def _si_half_of(obligation: Obligation, comparator: str) -> str:
    """Which window half an impedance obligation is: the Rust lowering
    names the halves ``<subject>.lo``/``.hi`` (WO-78's
    ``push_impedance_window_obligations``); a comparator-shaped
    impedance claim (the D103 fall-through) maps ``>=`` to the floor
    half and ``<=`` to the ceiling half."""
    name = obligation.claim.name or ""
    if name.endswith(".lo"):
        return "lo"
    if name.endswith(".hi"):
        return "hi"
    return "lo" if comparator in _LOWER_OPS else "hi"


def _translate_si_impedance(
    obligation: Obligation,
    args_text: str,
    comparator: str,
    bound_text: str,
    si_context: SiContext | None,
) -> Result[DischargeRequest, Deferral]:
    """Lower one `elec.impedance(<net>, ...)` window half (charter 35
    sec. 1.2) to the matching feldspar WO-25 impedance model request.

    Geometry sources, in the record-first order the charter demands:
    ``stackup=<key>`` resolves h/er/t from the loaded fab-published
    record (microstrip/outer only -- the record file's own honesty
    ledger); explicit ``h=``/``er=``/``t=`` kwargs are the no-record
    path (and the ONLY stripline path: no fab publishes the per-layer
    role table a stripline cavity derivation would need, the WO-78
    recorded residual). The trace width ``w`` is always claim-supplied
    -- pre-layout it is the `in [lo, hi]` slot the engine solves
    against this very claim (D184 boundary-finding).

    Named honest deferrals: ``si_differential_unexposed`` (feldspar's
    own `diff_pair_z` cut -- no independently verifiable published
    table), ``si_role_unknown``, ``si_stackup_unknown``,
    ``si_layer_unsupported``, ``si_stripline_stackup_underivable``,
    ``si_inputs_missing``, ``unresolved_limit``.
    """
    limit = _parse_float(bound_text)
    if limit is None:
        return Err(
            Deferral(
                reason="unresolved_limit",
                detail=f"impedance bound {bound_text!r} not literal",
            )
        )
    half = _si_half_of(obligation, comparator)
    numeric = _parse_call_kwargs(args_text)
    symbols = _parse_call_symbol_kwargs(args_text)
    role = symbols.get("role", "microstrip")
    if role in ("diff", "differential", "diff_pair"):
        return Err(
            Deferral(
                reason="si_differential_unexposed",
                detail=(
                    "differential impedance has no exposed feldspar model "
                    "(the WO-25 diff_pair_z named cut: no independently "
                    "verifiable published table); the claim defers until "
                    "that residual closes"
                ),
            )
        )
    if role == "microstrip":
        inputs: dict[str, Interval] = {}
        for name in ("w", "h", "t", "er"):
            if name in numeric:
                inputs[_SI_MICROSTRIP_PORTS[name]] = numeric[name]
        stackup_key = symbols.get("stackup")
        if stackup_key is not None:
            stackups = si_context.stackups if si_context is not None else {}
            record = stackups.get(stackup_key)
            if record is None:
                return Err(
                    Deferral(
                        reason="si_stackup_unknown",
                        detail=(
                            f"stackup {stackup_key!r} is not among the loaded "
                            f"records ({sorted(stackups) or 'none loaded'}); "
                            "nothing resolved, never a guessed dielectric"
                        ),
                    )
                )
            layer = symbols.get("layer", "outer")
            if layer != "outer":
                return Err(
                    Deferral(
                        reason="si_layer_unsupported",
                        detail=(
                            f"microstrip layer {layer!r}: the fab publishes "
                            "outer prepreg spans only; an inner trace is a "
                            "stripline claim with explicit b/er (the record "
                            "file's stripline residual)"
                        ),
                    )
                )
            h_m = record.microstrip_h_m()
            er = record.microstrip_er()
            if h_m is None or er is None:
                return Err(
                    Deferral(
                        reason="si_stackup_underivable",
                        detail=(
                            f"stackup {stackup_key!r} states no outer dielectric "
                            "span/Dk pair; the record is honest about what the "
                            "fab published"
                        ),
                    )
                )
            inputs[_SI_MICROSTRIP_PORTS["h"]] = Interval(lo=h_m, hi=h_m)
            inputs[_SI_MICROSTRIP_PORTS["er"]] = Interval(lo=er, hi=er)
            t_m = record.microstrip_t_m()
            inputs[_SI_MICROSTRIP_PORTS["t"]] = Interval(lo=t_m, hi=t_m)
            _log.info(
                "si impedance %s: stackup %s resolved h=%gm er=%g t=%gm (%s)",
                obligation.claim.name,
                stackup_key,
                h_m,
                er,
                t_m,
                record.reference,
            )
        needed = tuple(_SI_MICROSTRIP_PORTS.values())
        missing = sorted(p for p in needed if p not in inputs)
        if missing:
            return Err(
                Deferral(
                    reason="si_inputs_missing",
                    detail=(
                        f"microstrip impedance is missing inputs {missing} "
                        "(supply w= plus either stackup=<record key> or "
                        "explicit h=/er=/t= kwargs)"
                    ),
                )
            )
        claim_kind = _SI_MICROSTRIP_KINDS[half]
        request_inputs = {name: inputs[name] for name in needed}
    elif role == "stripline":
        if "stackup" in symbols:
            return Err(
                Deferral(
                    reason="si_stripline_stackup_underivable",
                    detail=(
                        "stripline cavity heights are not derivable from the "
                        "loaded stackup records (no fab-published per-layer "
                        "role table -- the WO-78 recorded residual); supply "
                        "explicit b=/er= kwargs"
                    ),
                )
            )
        needed = tuple(_SI_STRIPLINE_PORTS.values())
        inputs = {
            _SI_STRIPLINE_PORTS[name]: numeric[name]
            for name in ("w", "b", "er")
            if name in numeric
        }
        missing = sorted(p for p in needed if p not in inputs)
        if missing:
            return Err(
                Deferral(
                    reason="si_inputs_missing",
                    detail=f"stripline impedance is missing inputs {missing}",
                )
            )
        claim_kind = _SI_STRIPLINE_KINDS[half]
        request_inputs = {name: inputs[name] for name in needed}
    else:
        return Err(
            Deferral(
                reason="si_role_unknown",
                detail=(
                    f"impedance role {role!r} is not a modeled trace geometry "
                    "(microstrip | stripline)"
                ),
            )
        )
    _log.debug(
        "translated si impedance subject=%s -> claim_kind=%s limit=%g",
        obligation.subject_ref,
        claim_kind,
        limit,
    )
    return Ok(
        DischargeRequest(
            claim_kind=claim_kind,
            limit=limit,
            inputs=request_inputs,
            deterministic=True,
            regimes=_regimes_for(claim_kind),
        )
    )


def _translate_si_termination(
    obligation: Obligation, args_text: str, bound_text: str
) -> Result[DischargeRequest, Deferral]:
    """Lower an `elec.termination(<net>, scheme=..., ...)` sizing claim
    (charter 35 sec. 1.3) to the matching feldspar WO-25 termination
    model request. The model computes the SIZED value from the cited
    formula (Rs = Z0 - Ro, the Thevenin pair, the matched shunt R and
    quarter-rise-time C) with the arithmetic in evidence; the claim's
    bound is the designer's chosen component window edge.

    Thevenin claims name their leg (``leg=r1|r2``), ac_shunt claims
    their part (``part=r|c``) -- one obligation per sized value.
    ``scheme=parallel`` defers honestly: feldspar exposes no plain
    parallel-to-rail model (a WO-78 recorded residual, same posture as
    the differential cut).
    """
    limit = _parse_float(bound_text)
    if limit is None:
        return Err(
            Deferral(
                reason="unresolved_limit",
                detail=f"termination bound {bound_text!r} not literal",
            )
        )
    symbols = _parse_call_symbol_kwargs(args_text)
    numeric = _parse_call_kwargs(args_text)
    scheme = symbols.get("scheme")
    if scheme is None:
        return Err(
            Deferral(
                reason="si_scheme_missing",
                detail=(
                    "elec.termination(...) names no scheme= "
                    "(series | thevenin | ac_shunt)"
                ),
            )
        )
    if scheme == "parallel":
        return Err(
            Deferral(
                reason="si_scheme_unexposed",
                detail=(
                    "scheme=parallel has no exposed feldspar sizing model "
                    "(WO-78 recorded residual); series/thevenin/ac_shunt are "
                    "the modeled schemes"
                ),
            )
        )
    selector = ""
    if scheme == "thevenin":
        selector = symbols.get("leg", "")
    elif scheme == "ac_shunt":
        selector = symbols.get("part", "")
    route = _SI_TERMINATION_ROUTES.get((scheme, selector))
    if route is None:
        return Err(
            Deferral(
                reason="si_scheme_unknown",
                detail=(
                    f"termination scheme {scheme!r} (selector {selector!r}) is "
                    "not a modeled sizing route: series | thevenin leg=r1|r2 | "
                    "ac_shunt part=r|c"
                ),
            )
        )
    claim_kind, port_map = route
    missing = sorted(k for k in port_map if k not in numeric)
    if missing:
        return Err(
            Deferral(
                reason="si_inputs_missing",
                detail=(
                    f"termination scheme {scheme!r} is missing inputs "
                    f"{missing} (need {sorted(port_map)})"
                ),
            )
        )
    inputs = {port: numeric[kwarg] for kwarg, port in port_map.items()}
    _log.debug(
        "translated si termination subject=%s scheme=%s -> claim_kind=%s limit=%g",
        obligation.subject_ref,
        scheme,
        claim_kind,
        limit,
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


def si_sheet_fields(obligation: Obligation) -> dict[str, str] | None:
    """The SI table sheet's display fields for one obligation (WO-78
    deliverable 5) -- the ONE home for SI claim-text parsing, shared by
    this module's translators and `regolith.backends.ship`'s row
    derivation (NO DUPLICATION: the sheet never re-invents the claim
    grammar). Returns ``None`` for a non-SI obligation.
    """
    form = obligation.claim.form
    if not isinstance(form, ClaimForm1):
        return None
    match = _match_call_lhs(
        form.lhs, _SI_IMPEDANCE_FORM_NAMES + _SI_TERMINATION_FORM_NAMES
    )
    if match is None:
        return None
    call_name, args_text = match
    parts = _split_top_level_args(args_text)
    net = parts[0] if parts and "=" not in parts[0] else ""
    symbols = _parse_call_symbol_kwargs(args_text)
    numeric = _parse_call_kwargs(args_text)
    split = _split_comparator(form.op, form.rhs)
    target = f"{split[0]} {split[1].strip()}" if split is not None else form.rhs
    if call_name == "elec.impedance":
        geometry = ", ".join(
            f"{k}={numeric[k].lo:g}" for k in ("w", "gap", "b") if k in numeric
        )
    else:
        scheme = symbols.get("scheme", "")
        selector = symbols.get("leg") or symbols.get("part") or ""
        geometry = f"scheme={scheme}" + (f" {selector}" if selector else "")
    return {
        "claim": obligation.claim.name or form.lhs,
        "net": net,
        "target": target,
        "stackup": symbols.get("stackup", "-"),
        "layer": symbols.get("layer", "-"),
        "geometry": geometry,
    }


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


def _payload_ref(kind: str, digest: str, origin: str) -> PayloadRef:
    """One home for building an outgoing `DischargeRequest` payload ref
    (WO-69: every `_translate_cam` port uses this exact construction)."""
    return PayloadRef(kind=kind, digest=digest, origin=origin)


def _translate_cam(
    obligation: Obligation,
    claim_kind: str,
    plan_context: PlanContext | None,
) -> Result[DischargeRequest, Deferral]:
    """Lower a `cam.*` obligation (WO-69: `push_plan_obligations`'
    Rust-side emission) into the `std.cam` pack's `DischargeRequest`
    shape (WO-67's landed models): resolve the extern plan ref to
    pinned bytes, the declared `machine=`/`tooling=` records, and (for
    the three checks that need it) the target's `StockTarget` record
    -- stamped with the REAL RealizedGeometry digest this build
    supplied for the plan's own subject, when one was (deliverable 2's
    "target RealizedGeometry digest"). Every resolution failure is an
    honest, named :class:`Deferral` -- never a fabricated pass.
    """
    fields = _load_fields(obligation.given.loads)
    plan_ref = fields.get(_PLAN_REF_FIELD)
    dialect = fields.get(_PLAN_DIALECT_FIELD)
    if not plan_ref or not dialect:
        return Err(
            Deferral(
                reason="plan_clause_incomplete",
                detail="obligation carries no plan_ref/plan_dialect given",
            )
        )
    if plan_context is None:
        return Err(
            Deferral(
                reason="plan_context_unconfigured",
                detail=(
                    "no machine/tooling/stock_target records were resolved "
                    "for this build (this entry point does not thread a "
                    "plan context)"
                ),
            )
        )

    plan_bytes = resolve_plan_bytes(plan_context, plan_ref)
    if plan_bytes.is_err:
        failure = plan_bytes.danger_err
        return Err(Deferral(reason=failure.reason, detail=failure.detail))
    _, plan_digest = plan_bytes.danger_ok

    payloads: dict[str, PayloadRef] = {
        _CAM_PLAN_PORT: _payload_ref(_CAM_PLAN_KIND, plan_digest, plan_ref)
    }

    if claim_kind in _CAM_NEEDS_MACHINE:
        machine_ref = fields.get(_CAM_MACHINE_REF_FIELD)
        if not machine_ref:
            return Err(
                Deferral(
                    reason="cam_machine_ref_missing",
                    detail=f"{claim_kind} needs a declared machine= record",
                )
            )
        machine = plan_context.machine(machine_ref)
        if machine is None:
            return Err(
                Deferral(
                    reason="cam_machine_unresolved",
                    detail=(
                        f"machine={machine_ref!r} names no loaded [[machine]] record"
                    ),
                )
            )
        digest = stage_record(plan_context, machine_ref, machine)
        if digest is None:
            return Err(
                Deferral(
                    reason="cam_payload_store_missing",
                    detail="no payload store is configured for this build",
                )
            )
        payloads[_CAM_MACHINE_PORT] = _payload_ref(_CAM_TABLE_KIND, digest, machine_ref)

    if claim_kind in _CAM_NEEDS_TOOLING:
        tooling_ref = fields.get(_CAM_TOOLING_REF_FIELD)
        if tooling_ref:
            tool = plan_context.tool(tooling_ref)
            if tool is not None:
                digest = stage_record(plan_context, tooling_ref, tool)
                if digest is not None:
                    payloads[_CAM_TOOLING_PORT] = _payload_ref(
                        _CAM_TABLE_KIND, digest, tooling_ref
                    )
            else:
                _log.info(
                    "obligation %s: tooling=%r names no loaded [[tool]] "
                    "record; envelope/removal proceed without stickout",
                    obligation.subject_ref,
                    tooling_ref,
                )

    if claim_kind in _CAM_NEEDS_TARGET:
        target_ref = fields.get(_CAM_MACHINE_REF_FIELD) or plan_ref
        target = None
        # A `cam_target` PayloadRef names a `stock_target` record whose
        # KEY the source declares no separate argument for (WO-69's
        # design note: the plan's target is its OWN enclosing subject);
        # the record is instead looked up by the subject_ref the core
        # already keyed this obligation with -- fall back to any
        # single declared stock_target record when the project declares
        # exactly one (the common single-part-corpus case), never a
        # guess among several.
        candidates = [
            key
            for key, (_, rec) in plan_context.records.items()
            if isinstance(rec, StockTarget)
        ]
        if len(candidates) == 1:
            target_ref = candidates[0]
            target = plan_context.stock_target(target_ref)
        if target is None:
            return Err(
                Deferral(
                    reason="cam_target_unresolved",
                    detail=(
                        f"{claim_kind} needs exactly one declared "
                        "[[stock_target]] record in this build "
                        f"(found {len(candidates)})"
                    ),
                )
            )
        # Stamp the REAL RealizedGeometry digest this build supplied for
        # the plan's own subject over the declared fixture bounds
        # (deliverable 2's "target RealizedGeometry digest" citation) --
        # only when the core actually attached one (a `geometry.realized`
        # PayloadRef on this SAME obligation, D128's honest placeholder
        # path otherwise: the declared bounds still discharge, citing
        # whatever `geometry_digest` the record itself declared).
        geometry_ref = next(
            (r for r in obligation.payloads or () if r.kind == "geometry.realized"),
            None,
        )
        if geometry_ref is not None:
            target = target.model_copy(update={"geometry_digest": geometry_ref.digest})
        digest = stage_record(plan_context, target_ref, target)
        if digest is None:
            return Err(
                Deferral(
                    reason="cam_payload_store_missing",
                    detail="no payload store is configured for this build",
                )
            )
        payloads[_CAM_TARGET_PORT] = _payload_ref(_CAM_TABLE_KIND, digest, target_ref)

    inputs: dict[str, Interval] = {}
    if claim_kind == _CAM_REMOVAL_KIND:
        resolution_text = fields.get(_RESOLUTION_MM_FIELD)
        resolution = _parse_float(resolution_text) if resolution_text else None
        if resolution is None:
            return Err(
                Deferral(
                    reason="cam_resolution_missing",
                    detail=(
                        "cam.removal needs a declared resolution= voxel "
                        "error term (charter D3 conservatism)"
                    ),
                )
            )
        inputs["resolution_mm"] = Interval(lo=resolution, hi=resolution)

    # `cam.removal`'s claim bound is NOT zero: `CamRemovalModel` reports
    # `value=excess, eps=resolution_mm` (the declared voxel error term,
    # charter D3 conservatism), and `Model.discharge`'s single shared
    # margin rule computes `margin = limit - (value + eps)`. Claiming
    # against `limit=0.0` would make ANY nonzero declared resolution
    # violate even a perfectly good plan (excess=0.0), which is not
    # "conservative", it is wrong -- the declared tolerance IS
    # `target.margin_mm` (the design margin the target commits to
    # holding, `StockTarget.margin_mm`), so the claim bound is folded
    # into THAT limit here. This keeps the shared margin rule
    # untouched (it is correct for every claim whose limit is a real
    # tolerance) and matches the intended semantics: a removal check
    # passes iff `excess + resolution_mm <= target.margin_mm`. The
    # separate conservative-honesty gate (resolution_mm not finer than
    # margin_mm stays indeterminate, `check_removal` in
    # `harness/models/cam/checks.py`) is unaffected -- it already
    # short-circuits to `Err(DomainError)` before this margin ever
    # runs, for every other cam.* claim `limit` stays `0.0` exactly as
    # before.
    limit = target.margin_mm if claim_kind == _CAM_REMOVAL_KIND else 0.0

    _log.debug(
        "translated cam obligation subject=%s -> claim_kind=%s dialect=%s ports=%s "
        "limit=%s",
        obligation.subject_ref,
        claim_kind,
        dialect,
        sorted(payloads),
        limit,
    )
    return Ok(
        DischargeRequest(
            claim_kind=claim_kind,
            limit=limit,
            inputs=inputs,
            deterministic=True,
            payloads=payloads,
            regimes=(dialect,),
        )
    )


def _translate_hdl(
    obligation: Obligation,
    claim_kind: str,
    plan_context: PlanContext | None,
) -> Result[DischargeRequest, Deferral]:
    """Lower an `hdl.*` obligation (WO-82) into the `std.hdl` pack's
    `DischargeRequest` shape: resolve the extern HDL ref to pinned
    bytes and carry the declared regime as a required regime tag --
    mirrors `_translate_cam`'s ref-resolution shape exactly, reusing
    `resolve_plan_bytes` (a generic project-relative extern-ref reader,
    not gcode-specific despite its name) and the SAME `PlanContext`
    plumbing rather than inventing a second one (NO DUPLICATION). Every
    resolution failure is a named :class:`Deferral`. NOTE: as of this
    dispatch no Rust lowering emits `hdl.*` obligations with the
    `hdl_src_ref`/`hdl_regime` given-fields this reads (see the WO-82
    ledger) -- this function is dead code until that lands, wired now
    so the field names are settled in one place.
    """
    fields = _load_fields(obligation.given.loads)
    src_ref = fields.get(_HDL_SRC_REF_FIELD)
    regime = fields.get(_HDL_REGIME_FIELD)
    if not src_ref or not regime:
        return Err(
            Deferral(
                reason="hdl_clause_incomplete",
                detail="obligation carries no hdl_src_ref/hdl_regime given",
            )
        )
    if plan_context is None:
        return Err(
            Deferral(
                reason="plan_context_unconfigured",
                detail=(
                    "no extern-ref resolution context was configured for "
                    "this build (this entry point does not thread a "
                    "plan/extern context)"
                ),
            )
        )
    src_bytes = resolve_plan_bytes(plan_context, src_ref)
    if src_bytes.is_err:
        failure = src_bytes.danger_err
        return Err(Deferral(reason=failure.reason, detail=failure.detail))
    _, src_digest = src_bytes.danger_ok

    payloads = {
        _HDL_SRC_PORT: _payload_ref(_HDL_SRC_KIND, src_digest, src_ref),
    }
    _log.debug(
        "translated hdl obligation subject=%s -> claim_kind=%s regime=%s",
        obligation.subject_ref,
        claim_kind,
        regime,
    )
    return Ok(
        DischargeRequest(
            claim_kind=claim_kind,
            limit=0.0,
            inputs={},
            deterministic=True,
            payloads=payloads,
            regimes=(regime,),
        )
    )


def _translate_manufacturable(
    obligation: Obligation,
    token: str,
    dfm_context: DfmContext | None,
    plan_context: PlanContext | None,
) -> Result[DischargeRequest, Deferral]:
    """Lower a `makeable: manufacturable(<token>)` obligation (WO-110)
    into the `mfg.manufacturable` model's `DischargeRequest` shape:
    the part's staged DFM facts (`dfm_staging.derive_part_facts` --
    FeatureProgram features + the realized bounding box) plus the SAME
    `[[machine]]`/`[[tool]]` records the `std.cam` pack consumes.
    Every gap is an honest, NAMED :class:`Deferral` (never a fabricated
    pass; the reason vocabulary below is golden-visible):

    - ``mfg.manufacturable_unknown_process`` -- the spelled token is
      outside the claim vocabulary.
    - ``mfg.manufacturable_ungrounded_process`` -- the token's process
      family has no record-groundable envelope check yet (v1 grounds
      MILL only; form-family physics lives in the WO-28 rule packs +
      `mech.sheet.min_bend_radius`, one home).
    - ``mfg.manufacturable_process_mismatch`` -- the token's family
      matches none of the part's spelled stage processes.
    - ``mfg.manufacturable_inputs_missing`` -- geometry/feature scalars
      absent (each named: the D224/WO-113 enrichment surface).
    - ``mfg.manufacturable_records_missing`` -- no (or ambiguous)
      `[[machine]]`/`[[tool]]` records to ground tool/travel checks.
    """
    family = _DFM_TOKEN_FAMILIES.get(token)
    if family is None:
        return Err(
            Deferral(
                reason="mfg.manufacturable_unknown_process",
                detail=(
                    f"manufacturable({token}) names no known process token "
                    f"(known: {', '.join(sorted(_DFM_TOKEN_FAMILIES))})"
                ),
            )
        )
    if dfm_context is None:
        return Err(
            Deferral(
                reason="dfm_context_unconfigured",
                detail=(
                    "no DFM staging context was built for this run (this "
                    "entry point does not thread one)"
                ),
            )
        )
    part_name = dfm_context.scope_of(obligation.subject_ref)
    if part_name is None:
        return Err(
            Deferral(
                reason="mfg.manufacturable_inputs_missing",
                detail=(
                    "obligation subject maps to no snapshot scope; the "
                    "claiming part cannot be identified"
                ),
            )
        )
    facts = derive_part_facts(dfm_context, part_name, token)
    if facts.part is None and facts.geometry_gap.startswith("no emitted"):
        return Err(
            Deferral(
                reason="mfg.manufacturable_inputs_missing",
                detail=facts.geometry_gap,
            )
        )
    program = dfm_context.program_of(part_name)
    assert program is not None  # the geometry_gap branch above covers None
    spelled_processes = sorted(
        {op.process for op in program.features if op.process is not None}
    )
    part_families = facts.part.families if facts.part is not None else ()
    if family == "all":
        target_families: tuple[str, ...] = tuple(part_families) or ("all",)
    else:
        target_families = (family,)
    ungrounded = [f for f in target_families if f not in _DFM_GROUNDED_FAMILIES]
    if ungrounded:
        return Err(
            Deferral(
                reason="mfg.manufacturable_ungrounded_process",
                detail=(
                    f"process family(ies) {', '.join(sorted(set(ungrounded)))} "
                    "have no record-groundable envelope check (v1 grounds "
                    "'mill' via [[machine]]/[[tool]] records; form-family "
                    "physics is the rule packs' home)"
                ),
            )
        )
    if facts.part is not None and _DFM_MILL_FAMILY not in part_families:
        return Err(
            Deferral(
                reason="mfg.manufacturable_process_mismatch",
                detail=(
                    f"manufacturable({token}) claims the {family!r} family "
                    f"but the part's stages spell {spelled_processes or ['none']}"
                ),
            )
        )
    if facts.missing_params:
        return Err(
            Deferral(
                reason="mfg.manufacturable_inputs_missing",
                detail=(
                    "feature scalar(s) not spelled as literals: "
                    + ", ".join(facts.missing_params)
                ),
            )
        )
    if facts.part is None:
        return Err(
            Deferral(
                reason="mfg.manufacturable_inputs_missing",
                detail=facts.geometry_gap,
            )
        )
    if plan_context is None:
        return Err(
            Deferral(
                reason="mfg.manufacturable_records_missing",
                detail=(
                    "no plan-record context for this run; [[machine]]/"
                    "[[tool]] records cannot be resolved"
                ),
            )
        )
    machines = [
        (key, rec)
        for key, (_, rec) in sorted(plan_context.records.items())
        if isinstance(rec, MachineRecord)
    ]
    if len(machines) != 1:
        return Err(
            Deferral(
                reason="mfg.manufacturable_records_missing",
                detail=(
                    f"need exactly one declared [[machine]] record to ground "
                    f"travel fit (found {len(machines)})"
                ),
            )
        )
    tools = tuple(
        rec
        for _, (_, rec) in sorted(plan_context.records.items())
        if isinstance(rec, ToolRecord)
    )
    if not tools:
        return Err(
            Deferral(
                reason="mfg.manufacturable_records_missing",
                detail="no [[tool]] records declared; tool fit cannot be grounded",
            )
        )
    machine_key, machine = machines[0]
    machine_digest = stage_record(plan_context, machine_key, machine)
    part_digest = dfm_context.stage(f"dfm_part:{part_name}", facts.part)
    tools_digest = dfm_context.stage("dfm_tools", DfmToolSet(tools=tools))
    if machine_digest is None or part_digest is None or tools_digest is None:
        return Err(
            Deferral(
                reason="mfg.manufacturable_records_missing",
                detail="no payload store is configured for this build",
            )
        )
    _log.debug(
        "translated manufacturable claim part=%s token=%s family=%s "
        "features=%d machine=%s tools=%d",
        part_name,
        token,
        family,
        len(facts.part.features),
        machine_key,
        len(tools),
    )
    return Ok(
        DischargeRequest(
            claim_kind=_MANUFACTURABLE_KIND,
            limit=0.0,
            inputs={},
            deterministic=True,
            regimes=(_DFM_MILL_FAMILY,),
            payloads={
                _DFM_PART_PORT: _payload_ref(
                    _DFM_TABLE_KIND, part_digest, part_name
                ),
                _DFM_MACHINE_PORT: _payload_ref(
                    _DFM_TABLE_KIND, machine_digest, machine_key
                ),
                _DFM_TOOLS_PORT: _payload_ref(_DFM_TABLE_KIND, tools_digest, "tools"),
            },
        )
    )


def translate(
    obligation: Obligation,
    *,
    cost_context: CostContext | None = None,
    dfm_context: DfmContext | None = None,
    frame_context: FrameContext | None = None,
    plan_context: PlanContext | None = None,
    si_context: SiContext | None = None,
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
    against it. ``si_context`` (WO-78) is the build's loaded stackup-record
    state; an `elec.impedance` window half naming a `stackup=<key>` kwarg
    resolves its dielectric geometry through
    :func:`_translate_si_impedance` against it.
    """
    form = obligation.claim.form
    # WO-69: a `cam.*` obligation (`push_plan_obligations`) is marked by
    # its claim NAME, not a comparator shape -- checked before the
    # generic ClaimForm1 dispatch below (its `op="<="`/`rhs="0"` are
    # placeholder text `_translate_cam` never reads).
    model_pin = obligation.claim.model_pin
    claim_kind_name = obligation.claim.name
    if claim_kind_name in _CAM_CLAIM_KINDS:
        return _pin_model(
            _translate_cam(obligation, claim_kind_name, plan_context), model_pin
        )
    if claim_kind_name in _HDL_CLAIM_KINDS:
        return _pin_model(
            _translate_hdl(obligation, claim_kind_name, plan_context), model_pin
        )
    if isinstance(form, ClaimForm1) and form.op == "conforms":
        return _pin_model(_translate_conformance(obligation), model_pin)
    if isinstance(form, ClaimForm1) and form.op == "implies":
        return _pin_model(_translate_realization(obligation), model_pin)
    if isinstance(form, (ClaimForm2, ClaimForm3, ClaimForm4, ClaimForm5, ClaimForm6)):
        return _pin_model(_translate_temporal(obligation, form), model_pin)
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
            return _pin_model(
                _translate_frame(obligation, frame_split, frame_context), model_pin
            )
    # `mech.bolt.joint_separation`/`mech.bearing.l10_hours` (WO-72
    # coordinator wiring dispatch): the same after-the-call comparator
    # shape as a frame predicate, but no frame payload to gate on --
    # checked unconditionally on `op == "require"`, same ordering
    # rationale as the frame check above (before the generic path,
    # which cannot see a comparator hidden after a full call).
    if form.op == "require":
        bolt_split = _split_named_call_predicate(form.rhs, _BOLT_JOINT_FORM_NAMES)
        if bolt_split is not None:
            return _pin_model(
                _translate_bolted_joint(obligation, bolt_split), model_pin
            )
        bearing_split = _split_named_call_predicate(form.rhs, _BEARING_L10_FORM_NAMES)
        if bearing_split is not None:
            return _pin_model(
                _translate_bearing_l10(obligation, bearing_split), model_pin
            )
        fluid_dp_split = _split_named_call_predicate(form.rhs, _FLUID_DP_FORM_NAMES)
        if fluid_dp_split is not None:
            return _pin_model(
                _translate_fluid_dp(obligation, fluid_dp_split), model_pin
            )
        thermo_split = _split_named_call_predicate(form.rhs, _THERMO_FORM_NAMES)
        if thermo_split is not None:
            return _pin_model(_translate_thermo(obligation, thermo_split), model_pin)
        # WO-109: the non-frame `mech.deflection(...)` call form --
        # checked here (not gated on `has_frame_ref`, which already
        # returned above when true) so a machined-part cantilever claim
        # routes by call form regardless of its author label.
        cantilever_split = _split_named_call_predicate(form.rhs, _CANTILEVER_FORM_NAMES)
        if cantilever_split is not None:
            return _pin_model(
                _translate_cantilever_deflection(obligation, cantilever_split),
                model_pin,
            )
        term_split = _split_named_call_predicate(form.rhs, _SI_TERMINATION_FORM_NAMES)
        if term_split is not None:
            _, args_text, term_bound = term_split
            return _pin_model(
                _translate_si_termination(obligation, args_text, term_bound),
                model_pin,
            )
        # WO-86: `mech.cg(members=[...])` -- always defers honestly in
        # v1 (see `_translate_cg_moment`'s docstring for the keystone
        # finding). Matched unconditionally on `op == "require"`, same
        # non-frame call-form posture as bolt/bearing/thermo above; the
        # predicate's comparator shape (`in [...]` containment) does not
        # matter since this never reaches `_split_comparator`.
        cg_split = _split_named_call_predicate(form.rhs, _CG_MOMENT_FORM_NAMES)
        if cg_split is not None:
            return _pin_model(_translate_cg_moment(obligation), model_pin)
        # WO-110 (F130 census item 4): the bare `manufacturable(<token>)`
        # predicate -- the one undotted call form with a registered
        # channel; checked before the unmatched-call naming below so it
        # never lands in `unsupported_op` again.
        manufacturable = _MANUFACTURABLE_CALL.match(form.rhs.strip())
        if manufacturable is not None:
            return _pin_model(
                _translate_manufacturable(
                    obligation,
                    manufacturable.group(1),
                    dfm_context,
                    plan_context,
                ),
                model_pin,
            )
        # WO-109 deliverable 4(b): the predicate opens with a dotted
        # model call NO route above matched -- name the call path in the
        # deferral instead of folding it into the anonymous
        # `unsupported_op` bucket (a `crit_speed: mech.critical_speed(
        # ...)` claim is a MODEL gap, and its deferral must say which
        # model). A head-of-rhs comparator shape (`>= 6 dB`) never
        # matches here and keeps flowing to `_split_comparator` below.
        unmatched_call = _leading_dotted_call(form.rhs)
        if unmatched_call is not None:
            _log.info(
                "obligation %s: call path %s matches no registered route",
                obligation.subject_ref,
                unmatched_call,
            )
            return Err(
                Deferral(
                    reason="unmatched_call_path",
                    detail=(
                        f"call path {unmatched_call!r} (claim label "
                        f"{obligation.claim.name!r}) matches no registered "
                        "harness model or translate route"
                    ),
                )
            )
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
    # A `mech.bolt.joint_separation(...)`/`mech.bearing.l10_hours(...)`
    # call whose predicate fits ONE physical source line lowers through
    # the ordinary comparator split above (`form.lhs` IS the call
    # expression, `op` is already a real comparator, never `"require"`)
    # -- the sibling `op == "require"` check earlier in this function
    # only ever fires for a predicate the core's `rhs` truncates at a
    # line wrap (WO-65/WO-72 caveat), so this is the path a real
    # single-line caller actually hits. Checked here (after the split,
    # before the generic claim_kind fallback) so `form.lhs` is matched
    # exactly, not as a substring of a longer expression.
    bolt_lhs = _match_call_lhs(form.lhs, _BOLT_JOINT_FORM_NAMES)
    if bolt_lhs is not None:
        _, args_text = bolt_lhs
        return _pin_model(
            _translate_bolted_joint(
                obligation, (_BOLT_JOINT_KIND, args_text, bound_text)
            ),
            model_pin,
        )
    bearing_lhs = _match_call_lhs(form.lhs, _BEARING_L10_FORM_NAMES)
    if bearing_lhs is not None:
        _, args_text = bearing_lhs
        return _pin_model(
            _translate_bearing_l10(
                obligation, (_BEARING_L10_KIND, args_text, bound_text)
            ),
            model_pin,
        )
    fluid_dp_lhs = _match_call_lhs(form.lhs, _FLUID_DP_FORM_NAMES)
    if fluid_dp_lhs is not None:
        _, args_text = fluid_dp_lhs
        return _pin_model(
            _translate_fluid_dp(obligation, (_FLUID_DP_KIND, args_text, bound_text)),
            model_pin,
        )
    thermo_lhs = _match_call_lhs(form.lhs, _THERMO_FORM_NAMES)
    if thermo_lhs is not None:
        _, args_text = thermo_lhs
        return _pin_model(
            _translate_thermo(obligation, (_THERMO_KIND, args_text, bound_text)),
            model_pin,
        )
    # WO-109: the non-frame `mech.deflection(...)` call form, single-
    # source-line variant (a real comparator already split above,
    # mirroring the bolt/bearing/thermo `_lhs` siblings) -- the
    # `op == "require"` branch earlier only ever fires when the
    # predicate wraps onto a later source line (the WO-65/WO-72
    # caveat).
    cantilever_lhs = _match_call_lhs(form.lhs, _CANTILEVER_FORM_NAMES)
    if cantilever_lhs is not None:
        _, args_text = cantilever_lhs
        return _pin_model(
            _translate_cantilever_deflection(
                obligation, (_CANTILEVER_KIND, args_text, bound_text)
            ),
            model_pin,
        )
    # WO-78: the SI claim forms. The impedance window halves arrive with
    # the resolved call preserved as `lhs` (the Rust lowering's
    # `push_impedance_window_obligations`); a comparator-shaped
    # impedance claim rides the same match. Termination sizing claims
    # are ordinary D103 call-lhs comparisons.
    impedance_lhs = _match_call_lhs(form.lhs, _SI_IMPEDANCE_FORM_NAMES)
    if impedance_lhs is not None:
        _, args_text = impedance_lhs
        return _pin_model(
            _translate_si_impedance(
                obligation, args_text, comparator, bound_text, si_context
            ),
            model_pin,
        )
    termination_lhs = _match_call_lhs(form.lhs, _SI_TERMINATION_FORM_NAMES)
    if termination_lhs is not None:
        _, args_text = termination_lhs
        return _pin_model(
            _translate_si_termination(obligation, args_text, bound_text),
            model_pin,
        )
    cost_fields = _load_fields(obligation.given.loads)
    if _COST_SUBJECT_FIELD in cost_fields:
        return _pin_model(
            _translate_cost(obligation, cost_fields, bound_text, cost_context),
            model_pin,
        )
    # WO-109 (F130 Class B): a bare `mfg.unit_cost(qty=...)` call form --
    # no `given cost_subject=` marker, so the check above never fires --
    # is the SAME `mfg.cost` model's claim kind by call form (the corpus
    # spells the marker-carrying and bare forms differently; both name
    # one model). `_translate_cost` needs `cost_subject` unconditionally
    # (`costing.assemble_inputs_doc`'s subject argument), so a bare call
    # honestly defers naming exactly that missing given, never "no model
    # for label 'cost'".
    if _match_call_lhs(form.lhs, _COST_CALL_FORM_NAMES) is not None:
        return Err(
            Deferral(
                reason=f"{_COST_KIND}_inputs_missing",
                detail=(
                    "call form 'mfg.unit_cost(...)' matches the mfg.cost "
                    "model, but no `given cost_subject=` clause names the "
                    "cost profile subject to resolve it against"
                ),
            )
        )
    limit = _parse_float(bound_text)
    if limit is None:
        # D103: a general comparison whose bound is not a bare literal
        # may still be the link-budget shape, whose reference terms the
        # core resolved into `given.refs` (the Kestrel downlink). Only
        # when it is NOT link-shaped does the honest unresolved-limit
        # deferral stand.
        link = _try_link_budget(obligation, form)
        if link is not None:
            return _pin_model(link, model_pin)
        return Err(
            Deferral(
                reason="unresolved_limit", detail=f"bound {bound_text!r} not literal"
            )
        )
    # WO-109 (F130 Class B): a claim whose LHS is a whole dotted model
    # call routes by the CALL PATH, never the author's label -- the
    # request's claim kind is what the registry keys models by, and
    # `payload_ok`/`sag`/`crit_speed` labels are not model names. A
    # label-only claim (no call form) keeps its label as the kind (its
    # honest no-model deferral downstream is the (a) case of the
    # deliverable-4 reason split in `discharge_one`).
    call_path = _match_dotted_call(form.lhs)
    claim_kind = call_path or obligation.claim.name or form.lhs
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
            model_pin=model_pin,
        )
    )
