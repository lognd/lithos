"""Frame payload resolution: name-only section/material `RecordRef`s
-> std.civil numeric properties, staged as harness model inputs
(WO-48 slice B/C close-out follow-up -- "frame chain completion").

The frame payload itself is content-addressed at lowering and MUST
NOT be mutated post hoc (AD-18/AD-22): resolution happens here, at
the ORCHESTRATOR boundary, against the same payload bytes the frame
producer (`orchestrate._put_frame_payloads`) already staged into the
WO-30 store. This module mirrors `regolith.orchestrator.costing`'s
seam discipline (the WO-54 precedent): a plain per-family TOML
loader, `row_hash`-pinned records, and an honest `Result` for every
resolution step -- a section/material ref that resolves to no
std.civil record, or a member whose section is still the L3
search placeholder (`RecordRef(name="free", digest="")`), defers by
NAME, never fabricated (D58/AD-25).

Scope note (WO-85 update; the WO-65 note before it is superseded, not
silently dropped): this module resolves SECTION/MATERIAL numeric
properties (`resolve_member`) AND the full per-member gravity demand
surface (`member_demand` -> `MemberDemand`): directly-targeted line
loads (`kN/m on [...]`, SCHEMA 27's `line` kind, calcite/03 sec. 4),
tributary-transfer demand via `resolve_tributary_demand` (feldspar
WO-23's `resolve_tributary_loads` seam, mirrored in-repo since
feldspar is a separate distribution this toolchain does not import --
WO-27; fed by `FramePayload.transfers`, D176), stationed POINT loads
(`on [G1@0.5]`, D194), and column AXIAL demand from incoming gravity
load paths (`_axial_demand` -- the "axial pinned at 0" wall is dead).
A member with no resolvable demand source at all still defers
`frame_load_untargeted`, naming exactly that combined gap.

WO-65 reopen (this module's newest addition): a `section: free`
member carrying a DECLARED candidate family (WO-68's
`FrameMember.section_domain`, `section: in registry(<family>)`) no
longer stops at the blanket `frame_section_domain_unsearched`
deferral -- :func:`search_free_section` runs a real section search
over that family's std.civil catalog rows, through the SANCTIONED
`regolith.orchestrator.optimize.optimize_discrete` driver (AD-30: no
private scoring path). Candidate feasibility is DISCHARGE-COHERENT
by construction: each candidate is evaluated through the SAME
harness models the claims later discharge with
(`BeamUtilizationModel` for the member's declared `civil.utilization`
limit, `BeamServiceDeflectionModel` for its declared
`mech.deflection(...) <= span/N` bound -- the bounds come from the
build's OWN obligations via `translate.frame_claim_bounds`, never
invented) under the SAME `value + eps <= limit` margin rule the
evidence layer applies (`harness/evidence.py`) -- so a search winner
cannot fail its own claims at discharge. A claim form with no
harness model (e.g. `mech.first_mode`) gates nothing: it stays
honestly deferred at translate time whatever section wins, and a
gate the pipeline could never check would be a private scoring path.

Capacity-form provenance (the WO-65 dispatch's feldspar question):
feldspar's `mech.member.flexural_yield_capacity_f2` (AISC 360-16
F2.1, `Mn = Fy*Zx`) needs a PLASTIC section modulus; NO std.civil
section record carries a Zx field, only the elastic `s_mm3`/`s_in3`,
and fabricating Zx from S via a shape-factor guess is the "invented
equivalence" D58/WO-60's honesty note forbids. The search therefore
evaluates through the toolchain's landed elastic-interaction model
(`beam_utilization.py`, `|M|/(S*Fy) + |P|/(A*Fy)` with its own
declared 8 percent eps) -- the exact model the claim discharges with.
WO-85/D194 wired the AXIAL term: `member_demand` resolves a column's
axial demand from its incoming gravity load paths (`_axial_demand`),
so both the search and the discharge path now exercise the full
interaction (feldspar's `axial_yield_buckling_capacity_e3` -- true
buckling with Ag/r/KL -- remains a recorded feldspar-side follow-up;
the elastic interaction here is the landed in-tree tier).

The objective is mass-per-length (`area_m2 *
material.density_kg_m3`, ascending -- no corpus design declares a
`policy:` block for its structural claims, so this is the WO-56
disclosed tie-break default, not a silent choice). The winner is
pinned the ONE canonical way: its `OptimizationTrace` persisted via
`optimize.store_trace` (when the build threads a payload store) and
its lockfile row built by `optimize.winner_lock_row`
(`cause: optimize(mass_per_length, trace=<digest>)`, INV-21/INV-22),
accumulated on `FrameContext.winner_rows` +
`FrameContext.consumed_pins` for the build report to collect.

A `section: free` member with NO declared domain still defers
`frame_section_free` unchanged (D181: no reinterpretation); a
declared family with no std.civil rows defers
`frame_section_family_not_landed`; a declared family whose rows all
lack the properties its declared claims need defers
`capacity_unresolved`; a family whose rows resolve but no candidate
satisfies every declared bound defers
`frame_section_search_infeasible` -- four distinct, honest reasons,
never a blanket catch-all.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

import blake3
from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith.errors import OrchestratorError
from regolith.harness import DischargeRequest, Interval
from regolith.harness.models.beam_service_deflection import BeamServiceDeflectionModel
from regolith.harness.models.beam_utilization import BeamUtilizationModel
from regolith.harness.models.cost_common import LENGTH_TO_M
from regolith.logging_setup import get_logger
from regolith.magnetite.stdlib_records import row_hash
from regolith.orchestrator.lockfile import LockRow
from regolith.orchestrator.optimize import (
    ChoicePointDomain,
    EvalOutcome,
    optimize_discrete,
    store_trace,
    winner_lock_row,
)
from regolith.orchestrator.payload_store import PayloadStore

_log = get_logger(__name__)

# The record TOML tables this loader consumes (`std.civil`'s
# `sections.toml`/`materials.toml` row shapes).
_SECTION_TABLE = "section"
_MATERIAL_TABLE = "material"

# Unit scale factors this resolver understands (the small, fixed
# vocabulary the frame payload and std.civil records actually use;
# an unrecognized unit defers rather than guessing a conversion).
_MM2_TO_M2 = 1.0e-6
_MM3_TO_M3 = 1.0e-9
_MM4_TO_M4 = 1.0e-12
_GPA_TO_PA = 1.0e9
_MPA_TO_PA = 1.0e6
_LENGTH_TO_M = LENGTH_TO_M

# Exact inch -> SI conversions (25.4mm/in, NOT an engineering guess --
# the WO-60 AISC widening's `*_in`/`*_in2`/`*_in3`/`*_in4` rows are the
# ONLY std.civil section family with a real, multi-row search domain;
# a physical unit conversion is not the "invented equivalence" D58/
# WO-60's honesty note forbids -- that note is about guessing a
# section-family SUBSTITUTION, not converting inches to metres).
_IN_TO_M = 0.0254
_IN2_TO_M2 = _IN_TO_M**2
_IN3_TO_M3 = _IN_TO_M**3
_IN4_TO_M4 = _IN_TO_M**4


# frob:doc docs/modules/py-orchestrator.md#frame_resolve
class SectionProps(BaseModel):
    """One std.civil section record's numeric properties (SI base
    units); a field this resolver cannot reduce (a family that ships
    no `area_mm2`/`i_mm4`, e.g. a per-metre strip section) stays
    `None` rather than a fabricated value."""

    model_config = ConfigDict(frozen=True)

    key: str
    digest: str
    family: str | None = None
    area_m2: float | None = None
    i_m4: float | None = None
    s_m3: float | None = None


# frob:doc docs/modules/py-orchestrator.md#frame_resolve
class MaterialProps(BaseModel):
    """One std.civil material record's elastic modulus and reference
    (yield/28-day) stress, SI base units (Pa), plus density (kg/m3,
    WO-65: the section search's mass-per-length tie-break objective
    needs it; `None` when a material row carries no `density_kg_m3`
    field -- never fabricated)."""

    model_config = ConfigDict(frozen=True)

    key: str
    digest: str
    e_pa: float
    fy_pa: float
    density_kg_m3: float | None = None
    #: WO-112 Class 2: ultimate (tensile) stress, Pa, from a row's
    #: `ultimate_MPa` -- the `material.sigma_u` bound family's source;
    #: `None` when the row publishes no ultimate value (never guessed
    #: from yield).
    u_pa: float | None = None


# frob:doc docs/modules/py-orchestrator.md#frame_resolve
class FrameRecordSet(BaseModel):
    """Every loaded std.civil section/material record, keyed by name,
    PLUS sections indexed by declared `family` in TOML declaration
    order (WO-65: the section search's candidate domain -- declaration
    order is the deterministic default enumeration order, AD-6)."""

    model_config = ConfigDict(frozen=True)

    sections: dict[str, SectionProps] = {}
    materials: dict[str, MaterialProps] = {}
    sections_by_family: dict[str, tuple[str, ...]] = {}


# frob:doc docs/modules/py-orchestrator.md#frame_resolve
class FrameClaimBounds(BaseModel):
    """Every frame-claim bound the section search must satisfy (WO-65),
    extracted from the build's OWN obligations by
    `translate.frame_claim_bounds` (the one claim-parsing home) --
    keyed `(frame_name, member_id)`, plus the per-frame
    `<X>.members.all` utilization limit. Empty maps mean "no declared,
    checkable bound gates this member" -- the search then has nothing
    to gate on (feasibility is about the design's DECLARED demands,
    never an invented house rule)."""

    model_config = ConfigDict(frozen=True)

    deflection_divisors: dict[tuple[str, str], float] = {}
    utilization_limit_all: dict[str, float] = {}
    utilization_limits: dict[tuple[str, str], float] = {}

    # frob:doc docs/modules/py-orchestrator.md#frame_resolve
    # frob:waive TEST001 reason="frame-resolve helper, tested via frame-resolve tests"
    def deflection_divisor(self, frame_name: str, member_id: str) -> float | None:
        """The tightest declared `span / N` divisor for this member."""
        return self.deflection_divisors.get((frame_name, member_id))

    # frob:doc docs/modules/py-orchestrator.md#frame_resolve
    # frob:waive TEST001 reason="frame-resolve helper, tested via frame-resolve tests"
    def utilization_limit(self, frame_name: str, member_id: str) -> float | None:
        """The tightest declared utilization limit covering this member
        (a member-specific claim beats/joins its frame's `members.all`
        claim by MIN -- both are demands, the tightest governs)."""
        per_member = self.utilization_limits.get((frame_name, member_id))
        per_all = self.utilization_limit_all.get(frame_name)
        candidates = [v for v in (per_member, per_all) if v is not None]
        return min(candidates) if candidates else None


# frob:doc docs/modules/py-orchestrator.md#frame_resolve
class FrameResolutionError(BaseModel):
    """A named frame-resolution failure the translate layer surfaces
    as an honest deferral (never an exception, never a silent skip)."""

    model_config = ConfigDict(frozen=True)

    reason: str
    detail: str


# frob:doc docs/modules/py-orchestrator.md#frame_resolve
class ResolvedMember(BaseModel):
    """One `FrameMember`'s section/material refs reduced to the scalar
    properties the beam harness models consume (SI base units)."""

    model_config = ConfigDict(frozen=True)

    id: str
    role: str
    length_m: float
    area_m2: float
    i_m4: float
    s_m3: float | None
    e_pa: float
    fy_pa: float
    #: The std.civil section record key this member resolved to
    #: (declared key for a fixed section, the search winner for a
    #: `section: free` member); `None` only for pre-WO-65 callers that
    #: construct this model by hand.
    section_key: str | None = None
    #: WO-65: `cause: optimize(...)` for a member resolved via
    #: :func:`search_free_section` (a real `optimize_discrete` trace);
    #: `None` for a member resolved from a plain `registry(<key>)` ref
    #: (no search ran -- nothing to pin).
    search_cause: str | None = None


def _section_props(key: str, row: dict[str, Any], digest: str) -> SectionProps:
    """Reduce one `[[section]]` TOML row to SI-unit numeric properties,
    leaving a field the row does not carry honestly `None`. Understands
    BOTH the metric (`area_mm2`/`i_mm4`/`s_mm3`) and imperial
    (`area_in2`/`i_in4`/`s_in3`, the WO-60 AISC widening's rows) field
    vocabularies -- a real, exact unit conversion (25.4mm/in), never an
    engineering-equivalence guess; a row carrying neither unit system
    for a field stays honestly `None`."""
    area_mm2 = row.get("area_mm2")
    i_mm4 = row.get("i_mm4")
    if i_mm4 is None:
        i_mm4 = row.get("i_mm4_per_m")
    s_mm3 = row.get("s_mm3")
    area_m2 = area_mm2 * _MM2_TO_M2 if isinstance(area_mm2, (int, float)) else None
    i_m4 = i_mm4 * _MM4_TO_M4 if isinstance(i_mm4, (int, float)) else None
    s_m3 = s_mm3 * _MM3_TO_M3 if isinstance(s_mm3, (int, float)) else None
    if area_m2 is None:
        area_in2 = row.get("area_in2")
        if isinstance(area_in2, (int, float)):
            area_m2 = area_in2 * _IN2_TO_M2
    if i_m4 is None:
        i_in4 = row.get("i_in4")
        if isinstance(i_in4, (int, float)):
            i_m4 = i_in4 * _IN4_TO_M4
    if s_m3 is None:
        s_in3 = row.get("s_in3")
        if isinstance(s_in3, (int, float)):
            s_m3 = s_in3 * _IN3_TO_M3
    family = row.get("family")
    return SectionProps(
        key=key,
        digest=digest,
        family=str(family) if isinstance(family, str) else None,
        area_m2=area_m2,
        i_m4=i_m4,
        s_m3=s_m3,
    )


# frob:waive PERF003 reason="O(1) check against a fixed small set, not nested"
def _load_record_file(
    path: Path,
    out_sections: dict[str, SectionProps],
    out_materials: dict[str, MaterialProps],
) -> Result[None, OrchestratorError]:
    """Load one records TOML file's `section`/`material` tables.

    A malformed row is a loud error naming the file and key; a table
    this loader does not own (occupancy, load_cases, soil, ...) is
    skipped -- other record families have their own consumers."""
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return Err(
            OrchestratorError(kind="frame_records_malformed", message=f"{path}: {exc}")
        )
    for table, rows in data.items():
        if table not in (_SECTION_TABLE, _MATERIAL_TABLE):
            continue
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict) or "key" not in row:
                return Err(
                    OrchestratorError(
                        kind="frame_records_malformed",
                        message=f"{path}: a {table!r} row has no 'key'",
                    )
                )
            key = str(row["key"])
            digest = row_hash(table, row)
            if table == _SECTION_TABLE:
                out_sections.setdefault(key, _section_props(key, row, digest))
                continue
            e_gpa = row.get("E_GPa")
            fy_mpa = row.get("yield_MPa")
            if fy_mpa is None:
                fy_mpa = row.get("f_c_MPa")
            if not isinstance(e_gpa, (int, float)) or not isinstance(
                fy_mpa, (int, float)
            ):
                # A material row this resolver's inputs do not cover
                # (e.g. the soil-only rows in `materials.toml` carry
                # neither field) -- skip, not an error: other consumers
                # (geotech records) own those rows.
                continue
            density = row.get("density_kg_m3")
            ultimate_mpa = row.get("ultimate_MPa")
            out_materials.setdefault(
                key,
                MaterialProps(
                    key=key,
                    digest=digest,
                    e_pa=float(e_gpa) * _GPA_TO_PA,
                    fy_pa=float(fy_mpa) * _MPA_TO_PA,
                    density_kg_m3=float(density)
                    if isinstance(density, (int, float))
                    else None,
                    u_pa=float(ultimate_mpa) * _MPA_TO_PA
                    if isinstance(ultimate_mpa, (int, float))
                    else None,
                ),
            )
    return Ok(None)


# frob:doc docs/modules/py-orchestrator.md#frame_resolve
def load_frame_records(
    search_paths: tuple[str, ...],
) -> Result[FrameRecordSet, OrchestratorError]:
    """Load every std.civil section/material record under
    `search_paths` (the `load_cost_records` local-path posture
    verbatim: no network, no registry fetch). Each search path
    contributes its own `records/*.toml` plus every package
    subdirectory's, in sorted order; the first loaded row for a key
    wins deterministically. `sections_by_family` groups sections by
    their declared `family` in the SAME declaration order (WO-65: this
    is the section search's deterministic candidate enumeration
    order, AD-6)."""
    sections: dict[str, SectionProps] = {}
    materials: dict[str, MaterialProps] = {}
    for base_str in search_paths:
        base = Path(base_str)
        candidates = [base / "records"]
        if base.is_dir():
            candidates.extend(
                sub / "records"
                for sub in sorted(base.iterdir())
                if sub.is_dir() and (sub / "magnetite.toml").is_file()
            )
        for records_dir in candidates:
            if not records_dir.is_dir():
                continue
            for toml_file in sorted(records_dir.glob("*.toml")):
                loaded = _load_record_file(toml_file, sections, materials)
                if loaded.is_err:
                    return Err(loaded.danger_err)
    by_family: dict[str, list[str]] = {}
    for key, section in sections.items():
        if section.family is None:
            continue
        by_family.setdefault(section.family, []).append(key)
    _log.debug(
        "loaded frame records: %d section(s), %d material(s), %d family/families "
        "from %s",
        len(sections),
        len(materials),
        len(by_family),
        list(search_paths),
    )
    return Ok(
        FrameRecordSet(
            sections=sections,
            materials=materials,
            sections_by_family={k: tuple(v) for k, v in by_family.items()},
        )
    )


# frob:doc docs/modules/py-orchestrator.md#frame_resolve
class FrameContext:
    """One build's frame-resolution state: the loaded std.civil
    section/material records, the build's raw frame payloads (name ->
    `FramePayload` dict, `BuildPayload.frames`), the declared claim
    bounds the section search gates on (WO-65), the consumed-record
    pin ledger (the `CostContext.consumed_pins` precedent, INV-22's
    lockfile-pin shape), and the search-winner lockfile rows
    (`cause: optimize(...)`, INV-21)."""

    def __init__(
        self,
        *,
        records: FrameRecordSet,
        frames: dict[str, dict],
        search_paths: tuple[str, ...],
        claim_bounds: FrameClaimBounds | None = None,
        payload_store: PayloadStore | None = None,
    ) -> None:
        """Bind one build's fixed frame-resolution inputs."""
        self.records = records
        self.frames = frames
        self.search_paths = search_paths
        # WO-65: the declared frame-claim bounds the section search
        # gates candidate feasibility on (empty = nothing declared).
        self.claim_bounds = claim_bounds or FrameClaimBounds()
        # WO-65: where a search winner's `OptimizationTrace` persists
        # (`optimize.store_trace`); `None` for translate-only entry
        # points (the digest is still computed identically -- see
        # `search_free_section`).
        self.payload_store = payload_store
        # `std.civil.<section|material>.<key>` -> row digest.
        self.consumed_pins: dict[str, str] = {}
        # WO-65: slot -> the winner's `optimize.winner_lock_row` row.
        self.winner_rows: dict[str, LockRow] = {}

    # frob:doc docs/modules/py-orchestrator.md#frame_resolve
    # frob:waive TEST001 reason="frame-resolve helper, tested via frame-resolve tests"
    def frame_name(self, frame: dict) -> str:
        """The `BuildPayload.frames` key for `frame` (identity lookup:
        the context hands out exactly these dict objects), or `""` for
        a frame this context does not hold (hand-built test fixtures)."""
        return next((k for k, v in self.frames.items() if v is frame), "")


# frob:doc docs/modules/py-orchestrator.md#frame_resolve
def load_frame_context(
    project_root: str,
    *,
    build_payload: dict[str, object] | None = None,
    record_search_paths: tuple[str, ...] = (),
    payload_store: PayloadStore | None = None,
) -> Result[FrameContext | None, OrchestratorError]:
    """Load this build's frame-resolution context, or `Ok(None)` when
    the build's payload carries no frames at all (a build with no
    calcite structures -- frame-referencing claims cannot even arise,
    so no honest reason to load std.civil records).

    `record_search_paths` extends the default (the project root
    itself) with additional local package roots (e.g. `stdlib/`),
    exactly the `load_cost_records` posture. The claim bounds the
    WO-65 section search gates on are extracted from the SAME payload
    here (`translate.frame_claim_bounds` -- the one claim-parsing
    home), so every entry point that can search also knows the
    design's declared demands."""
    frames_any = (build_payload or {}).get("frames", {})
    frames_raw = (
        {str(k): v for k, v in frames_any.items() if isinstance(v, dict)}
        if isinstance(frames_any, dict)
        else {}
    )
    if not frames_raw:
        _log.debug("frame_resolve: build payload carries no frames; context skipped")
        return Ok(None)
    paths = (project_root, *record_search_paths)
    loaded = load_frame_records(paths)
    if loaded.is_err:
        return Err(loaded.danger_err)
    # Runtime-lazy: `translate` type-imports this module (see its
    # TYPE_CHECKING note); the function-local import keeps the
    # layering acyclic in the other direction too.
    from regolith.orchestrator.translate import frame_claim_bounds

    bounds = frame_claim_bounds(build_payload or {})
    return Ok(
        FrameContext(
            records=loaded.danger_ok,
            frames=frames_raw,
            search_paths=paths,
            claim_bounds=bounds,
            payload_store=payload_store,
        )
    )


def _length_m(interval: dict[str, Any] | None) -> float | None:
    """A `ScalarInterval` dict's magnitude in metres, or `None` for an
    unrecognized unit (never a silent misconversion)."""
    if not isinstance(interval, dict):
        return None
    unit = interval.get("unit")
    scale = _LENGTH_TO_M.get(unit)
    if scale is None:
        return None
    hi = interval.get("hi", interval.get("lo", 0.0))
    return float(hi) * scale


# frob:doc docs/modules/py-orchestrator.md#frame_resolve
def resolve_member(
    ctx: FrameContext, frame: dict, member_id: str
) -> Result[ResolvedMember, FrameResolutionError]:
    """Resolve one `FramePayload` member's section/material name refs
    to std.civil numeric properties, pinning every record consumed.

    Named failure modes (each an honest, greppable deferral reason,
    never a guess):
    - `frame_member_not_found`: `member_id` names no member in this
      frame (e.g. a claim's subject naming a non-frame quantity, like
      retaining_wall's `heel_sg` sliding-stability subject).
    - `frame_section_free`: the member's `section: free` -- an L3
      section-search variable never committed to a catalog choice.
      This is a GENUINELY unresolved design decision, not a missing
      std.civil record (D58 does not apply): no section-search solver
      exists in this toolchain (out of this WO's scope, no
      SCHEMA_VERSION-preserving path closes it).
    - `frame_section_unresolved` / `frame_material_unresolved`: the
      named section/material key matches no std.civil record (a real
      D58 tier-honesty gap; extend the stdlib record set to close it).
    - `frame_section_incomplete`: the matched section record carries
      no `area_mm2`/`i_mm4` field this resolver reduces (a per-metre
      strip section family, e.g. `rc_wall`/`rc_footing`/`comp_deck`).
    - `frame_length_unresolved`: the member's length unit is outside
      this resolver's small fixed vocabulary (`m`/`mm`).
    """
    member = next(
        (m for m in frame.get("members", []) if m.get("id") == member_id), None
    )
    if member is None:
        return Err(
            FrameResolutionError(
                reason="frame_member_not_found",
                detail=(
                    f"{member_id!r} names no member in this frame payload "
                    "(the claim's subject may name a derived quantity this "
                    "resolver does not cover, not a frame member)"
                ),
            )
        )
    section_ref = member.get("section") or {}
    section_name = section_ref.get("name", "")
    section_domain = member.get("section_domain")
    if not section_name or section_name == "free":
        # WO-68 deliverable 6 (minimal touch-up; WO-65's reopen does the
        # full section-search flip): a member with a DECLARED family
        # (`section: in registry(<family>)`, `FrameMember.section_domain`
        # populated) is a narrower, more specific deferral than one with
        # no domain at all (D181 finding 2's `family_not_landed`,
        # unchanged) -- distinct reason strings so WO-65's reopen can
        # key off "has a family, just needs the search" without
        # re-auditing every member from scratch.
        if section_domain:
            _log.info(
                "frame resolve: member %s section is `free` with a "
                "declared domain %s -- running the WO-65 section search",
                member_id,
                section_domain,
            )
            return search_free_section(ctx, frame, member, member_id, section_domain)
        _log.info(
            "frame resolve: member %s section is `free` (L3 search unresolved)",
            member_id,
        )
        return Err(
            FrameResolutionError(
                reason="frame_section_free",
                detail=(
                    f"member {member_id!r}'s section is `free` -- an L3 "
                    "section-search variable never committed to a catalog "
                    "choice; genuinely unresolved (no section-search solver "
                    "exists), not a missing std.civil record"
                ),
            )
        )
    section = ctx.records.sections.get(section_name)
    if section is None:
        _log.info(
            "frame resolve: member %s section %s MISS (no std.civil record)",
            member_id,
            section_name,
        )
        return Err(
            FrameResolutionError(
                reason="frame_section_unresolved",
                detail=f"section {section_name!r} names no std.civil section record",
            )
        )
    if section.area_m2 is None or section.i_m4 is None:
        return Err(
            FrameResolutionError(
                reason="frame_section_incomplete",
                detail=(
                    f"section {section_name!r}'s record carries no "
                    "area_mm2/i_mm4 field this resolver reduces (a "
                    "per-metre strip section family)"
                ),
            )
        )
    material_ref = member.get("material") or {}
    material_name = material_ref.get("name", "")
    material = ctx.records.materials.get(material_name)
    if material is None:
        _log.info(
            "frame resolve: member %s material %s MISS (no std.civil record)",
            member_id,
            material_name,
        )
        return Err(
            FrameResolutionError(
                reason="frame_material_unresolved",
                detail=(
                    f"material {material_name!r} names no std.civil material record"
                ),
            )
        )
    length_m = _length_m(member.get("length"))
    if length_m is None:
        return Err(
            FrameResolutionError(
                reason="frame_length_unresolved",
                detail=f"member {member_id!r}'s length unit is not recognized",
            )
        )

    ctx.consumed_pins[f"std.civil.section.{section.key}"] = section.digest
    ctx.consumed_pins[f"std.civil.material.{material.key}"] = material.digest
    _log.info(
        "frame resolve: member %s section=%s material=%s HIT",
        member_id,
        section_name,
        material_name,
    )
    return Ok(
        ResolvedMember(
            id=member_id,
            role=member.get("role", ""),
            length_m=length_m,
            area_m2=section.area_m2,
            i_m4=section.i_m4,
            s_m3=section.s_m3,
            e_pa=material.e_pa,
            fy_pa=material.fy_pa,
            section_key=section.key,
        )
    )


# frob:doc docs/modules/py-orchestrator.md#frame_resolve
def search_free_section(
    ctx: FrameContext,
    frame: dict,
    member: dict,
    member_id: str,
    section_domain: str,
) -> Result[ResolvedMember, FrameResolutionError]:
    """WO-65: resolve a `section: free` member carrying a declared
    candidate family (`section_domain`, e.g. `"std.civil.w_shape"`) by
    running a real section search over that family's std.civil rows,
    through `regolith.orchestrator.optimize.optimize_discrete` (AD-30:
    the evaluator IS the pipeline -- no private scoring path). See the
    module docstring for the full honesty accounting of each named
    deferral reason this can still produce.

    Feasibility (discharge-coherent by construction): every bound the
    build's own obligations declare over this member -- its
    `civil.utilization` limit and its `mech.deflection <= span/N`
    bound (`FrameContext.claim_bounds`) -- evaluated per candidate
    through the SAME harness models discharge later uses
    (`BeamUtilizationModel`/`BeamServiceDeflectionModel`) under the
    SAME `value + eps <= limit` margin rule (`harness/evidence.py`).
    Objective: mass-per-length (`area_m2 * material.density_kg_m3`),
    ascending -- the WO-56 disclosed tie-break default (no corpus
    design declares a `policy:` block for its structural claims). The
    winner pins canonically: trace persisted via `optimize.
    store_trace` (when a payload store is threaded), lockfile row via
    `optimize.winner_lock_row` (INV-21/INV-22).
    """
    family = section_domain.rsplit(".", 1)[-1]
    candidate_keys = ctx.records.sections_by_family.get(family, ())
    if not candidate_keys:
        return Err(
            FrameResolutionError(
                reason="frame_section_family_not_landed",
                detail=(
                    f"member {member_id!r}'s declared family {section_domain!r} "
                    "names no std.civil section record (family unrecognized or "
                    "empty in the loaded records)"
                ),
            )
        )

    material_ref = member.get("material") or {}
    material_name = material_ref.get("name", "")
    material = ctx.records.materials.get(material_name)
    if material is None:
        _log.info(
            "section search: member %s material %s MISS (no std.civil record)",
            member_id,
            material_name,
        )
        return Err(
            FrameResolutionError(
                reason="frame_material_unresolved",
                detail=(
                    f"material {material_name!r} names no std.civil material record"
                ),
            )
        )
    length_m = _length_m(member.get("length"))
    if length_m is None:
        return Err(
            FrameResolutionError(
                reason="frame_length_unresolved",
                detail=f"member {member_id!r}'s length unit is not recognized",
            )
        )

    probe = ResolvedMember(
        id=member_id,
        role=member.get("role", ""),
        length_m=length_m,
        area_m2=1.0,
        i_m4=1.0,
        s_m3=1.0,
        e_pa=material.e_pa,
        fy_pa=material.fy_pa,
    )
    probe_demand = member_demand(frame, probe)
    if probe_demand.is_err:
        return Err(probe_demand.danger_err)
    demand = probe_demand.danger_ok
    # WO-85: the full demand surface -- bending from line + stationed
    # point loads, axial from gravity load paths (a column-role member
    # with only axial demand now searches instead of deferring).
    moment = demand.moment_nm(length_m)
    axial_n = demand.axial_n
    w_defl = demand.deflection_w_equiv(length_m)

    # A usable candidate carries EVERY property the downstream
    # translators consume for a resolved member (area + I always --
    # `resolve_member`'s own fixed-section bar -- plus S, the strength
    # path's input); a family whose rows all miss one defers
    # `capacity_unresolved`, never interpolates (D58/WO-60).
    usable_sections: dict[str, SectionProps] = {}
    for key in candidate_keys:
        section = ctx.records.sections[key]
        if (
            section.area_m2 is not None
            and section.i_m4 is not None
            and section.s_m3 is not None
        ):
            usable_sections[key] = section
    if not usable_sections:
        return Err(
            FrameResolutionError(
                reason="capacity_unresolved",
                detail=(
                    f"member {member_id!r}'s declared family {section_domain!r} "
                    f"has {len(candidate_keys)} record(s), none carrying the "
                    "area/inertia/section-modulus fields this resolver reduces"
                ),
            )
        )

    # The member's DECLARED, model-checkable demands (WO-65): bounds
    # come from the build's own obligations (`translate.
    # frame_claim_bounds`), and each candidate is evaluated through the
    # SAME harness models discharge later uses, under the SAME
    # `value + eps <= limit` margin rule (`harness/evidence.py`) -- a
    # winner here cannot fail its own claims at discharge. A member no
    # checkable claim covers gates on nothing (the objective alone
    # picks) -- honest: feasibility means "all DECLARED demands
    # dischargeable", not an invented house rule.
    frame_name = ctx.frame_name(frame)
    util_limit = ctx.claim_bounds.utilization_limit(frame_name, member_id)
    defl_divisor = ctx.claim_bounds.deflection_divisor(frame_name, member_id)
    util_model = BeamUtilizationModel()
    defl_model = BeamServiceDeflectionModel()
    if util_limit is None and defl_divisor is None:
        _log.info(
            "section search: member %s has no declared checkable claim "
            "bound; objective alone picks (feasibility gates nothing)",
            member_id,
        )

    def _point(value: float) -> Interval:
        return Interval(lo=value, hi=value)

    def evaluate(assignment: Any) -> EvalOutcome:
        key = assignment[member_id]
        section = usable_sections[key]
        assert section.area_m2 is not None  # usable_sections invariant
        assert section.i_m4 is not None
        assert section.s_m3 is not None
        feasible = True
        summary: list[str] = [f"section={key}"]
        if util_limit is not None:
            prediction = util_model.estimate(
                DischargeRequest(
                    claim_kind=util_model.signature.claim_kind,
                    limit=util_limit,
                    inputs={
                        "moment_demand": _point(moment),
                        # WO-85: real axial demand from gravity load
                        # paths (the "pinned at 0" wall is dead).
                        "axial_demand": _point(axial_n),
                        "section_modulus": _point(section.s_m3),
                        "area": _point(section.area_m2),
                        "fy": _point(material.fy_pa),
                    },
                )
            )
            if prediction.is_err:
                feasible = False
                summary.append(f"utilization=domain_error({prediction.danger_err})")
            else:
                pred = prediction.danger_ok
                # evidence.py's upper-bound margin rule, verbatim.
                feasible = feasible and (pred.value + pred.eps <= util_limit)
                summary.append(f"utilization={pred.value:.4f}+eps<= {util_limit}")
        if defl_divisor is not None:
            defl_limit = length_m / defl_divisor
            prediction = defl_model.estimate(
                DischargeRequest(
                    claim_kind=defl_model.signature.claim_kind,
                    limit=defl_limit,
                    inputs={
                        # WO-85: line + point-load deflection, folded
                        # to the model's UDL input via the exact
                        # (conservatively summed) equivalence -- see
                        # `MemberDemand.deflection_w_equiv`.
                        "w_load": _point(w_defl),
                        "length": _point(length_m),
                        "e_modulus": _point(material.e_pa),
                        "i_area": _point(section.i_m4),
                    },
                )
            )
            if prediction.is_err:
                feasible = False
                summary.append(f"deflection=domain_error({prediction.danger_err})")
            else:
                pred = prediction.danger_ok
                feasible = feasible and (pred.value + pred.eps <= defl_limit)
                summary.append(f"deflection={pred.value:.5f}+eps<= {defl_limit:.5f}")
        mass_per_length = section.area_m2 * (material.density_kg_m3 or 0.0)
        return EvalOutcome(
            feasible=feasible,
            objective_vector=(mass_per_length,),
            verdict_summary=" ".join(summary),
            evidence_digests=(section.digest, material.digest),
        )

    domains = (ChoicePointDomain(subject=member_id, candidates=tuple(usable_sections)),)
    trace = optimize_discrete(
        domains,
        evaluate,
        ("minimize",),
        budget_evals=len(usable_sections),
    )
    if trace.winner is None:
        gates = []
        if util_limit is not None:
            gates.append(f"utilization<={util_limit}")
        if defl_divisor is not None:
            gates.append(f"deflection<=span/{defl_divisor:g}")
        return Err(
            FrameResolutionError(
                reason="frame_section_search_infeasible",
                detail=(
                    f"member {member_id!r}'s declared family {section_domain!r} "
                    f"searched {len(usable_sections)} candidate(s) with usable "
                    f"properties; none satisfies the declared bound(s) "
                    f"[{', '.join(gates)}] under the resolved demand "
                    "(discharge-coherent: value+eps vs limit)"
                ),
            )
        )
    winner_entry = trace.candidates[trace.winner]
    winner_key = winner_entry.assignment[0].root[1]
    winner = usable_sections[winner_key]
    # `usable_sections` invariant (checked at admission above).
    assert winner.area_m2 is not None and winner.i_m4 is not None
    # Persist the trace (the AD-30 audit surface) when this build
    # threads a payload store; a translate-only entry point (the
    # deferral corpus) still computes the IDENTICAL content digest
    # (`PayloadStore.put` is blake3 over these same bytes), so the
    # cause string never depends on which entry point ran (INV-30).
    if ctx.payload_store is not None:
        trace_digest = store_trace(ctx.payload_store, trace)
    else:
        trace_digest = (
            "blake3:"
            + blake3.blake3(trace.model_dump_json().encode("utf-8")).hexdigest()
        )
    slot = f"{frame_name}.{member_id}.section" if frame_name else f"{member_id}.section"
    row_result = winner_lock_row(trace, slot, "mass_per_length", trace_digest)
    # `trace.winner` is not None here, so the row cannot honestly fail.
    row = row_result.danger_ok
    ctx.winner_rows[slot] = row
    ctx.consumed_pins[f"std.civil.section.{winner.key}"] = winner.digest
    ctx.consumed_pins[f"std.civil.material.{material.key}"] = material.digest
    _log.info(
        "section search: member %s family=%s winner=%s cause=%s",
        member_id,
        family,
        winner_key,
        row.cause,
    )
    return Ok(
        ResolvedMember(
            id=member_id,
            role=member.get("role", ""),
            length_m=length_m,
            area_m2=winner.area_m2,
            i_m4=winner.i_m4,
            s_m3=winner.s_m3,
            e_pa=material.e_pa,
            fy_pa=material.fy_pa,
            section_key=winner.key,
            search_cause=row.cause,
        )
    )


#: Pressure-unit -> Pa scale, the small fixed vocabulary this resolver
#: understands for a tributary source's own area load intensity
#: (calcite/03 sec. 4 loads are area-sourced, kPa-shaped in every
#: corpus design that declares one; an unrecognized unit is skipped,
#: never guessed).
_PRESSURE_TO_PA = {"Pa": 1.0, "kPa": 1.0e3}

#: Linear-load-unit -> N/m scale (the same small vocabulary
#: `member_udl_demand`'s direct-load loop already uses).
_LINE_TO_N_PER_M = {"N/m": 1.0, "kN/m": 1.0e3}


# frob:doc docs/modules/py-orchestrator.md#frame_resolve
def resolve_tributary_demand(
    frame: dict, member: ResolvedMember
) -> Result[float, FrameResolutionError]:
    """WO-65 deliverable 1 (feldspar WO-23's `resolve_tributary_loads`
    seam, mirrored in-repo since feldspar is a separate distribution
    this toolchain does not import -- AD per WO-27, "reference external
    FEA pack, separate distribution"): reduce member.id's incoming
    `Bearing(tributary=...)` transfer(s) (`FramePayload.transfers`,
    D176/WO-62 slice B) to a distributed-load demand (N/m), the SAME
    deterministic algorithm feldspar's `resolve_tributary_loads`
    documents (`tributary.kind == "width"`: pressure*width is already a
    line load; `tributary.kind == "area"`: pressure*area is a resultant
    force, spread over the RECEIVING member's own length).

    ONLY a `Bearing` transfer carrying an explicit `tributary` value
    resolves (feldspar's own "no inferred geometry" law, mirrored
    here); the source member's own load must be a literal, directly-
    targeted, pressure-unit (`Pa`/`kPa`) `FrameLoad` this resolver's
    small fixed vocabulary recognizes -- any other shape is skipped,
    not zero-filled (a source with no matching load this case is a
    different fact than a zero load).

    Returns `Ok(0.0)` (not an error) when the member carries no
    resolvable tributary transfer at all -- "no tributary demand" is a
    legitimate zero, distinct from `member_udl_demand`'s
    `frame_load_untargeted` (which means "no demand source resolved by
    ANY path"); callers combine this with the direct-load total and
    only defer if BOTH are silent.
    """
    total = 0.0
    hit = False
    for transfer in frame.get("transfers", []):
        if transfer.get("to") != member.id:
            continue
        if transfer.get("kind") != "Bearing":
            continue
        # WO-65 bugfix: `FrameTransfer.tributary` (`crates/regolith-oblig/
        # src/frame.rs`) is a FLAT `ScalarInterval` (`{lo, hi, unit}`) --
        # no `kind`/`value` wrapper exists in the real lowered payload
        # (verified live against `compiler.check(footbridge.calx)`'s
        # own `transfers` array). `kind` ("width" vs "area") is INFERRED
        # from the unit itself (`m` is a width, `m2` is an area -- the
        # two units this resolver's small fixed vocabulary recognizes),
        # not a separate declared field. The earlier `tributary.kind`/
        # `tributary.value` shape this loop checked before was dead code
        # (never matched any real payload); fixed here rather than
        # carried forward silently broken.
        tributary = transfer.get("tributary")
        if not isinstance(tributary, dict):
            continue
        trib_unit = tributary.get("unit")
        trib_magnitude = tributary.get("hi", tributary.get("lo"))
        if trib_magnitude is None:
            continue
        if trib_unit == "m":
            trib_kind = "width"
        elif trib_unit == "m2":
            trib_kind = "area"
        else:
            trib_kind = None
        source_id = transfer.get("from")
        # The source's own directly-targeted, pressure-unit load (any
        # case -- `member_udl_demand`'s own direct loop does not filter
        # by case either, the same simplification, kept consistent).
        pressure_pa = None
        for load in frame.get("loads", []):
            if load.get("target") != source_id:
                continue
            if load.get("kind") != "distributed":
                continue
            value = load.get("value") or {}
            scale = _PRESSURE_TO_PA.get(value.get("unit"))
            if scale is None:
                continue
            magnitude = value.get("hi", value.get("lo", 0.0))
            pressure_pa = float(magnitude) * scale
            break
        if pressure_pa is None:
            _log.info(
                "tributary resolve: member %s transfer %s from %s has no "
                "resolvable source pressure load; skipped (not zero-filled)",
                member.id,
                transfer.get("id"),
                source_id,
            )
            continue
        if trib_kind == "width" and trib_unit == "m":
            line_n_per_m = pressure_pa * float(trib_magnitude)
        elif trib_kind == "area" and trib_unit == "m2":
            if member.length_m <= 0.0:
                continue
            total_force_n = pressure_pa * float(trib_magnitude)
            line_n_per_m = total_force_n / member.length_m
        else:
            _log.info(
                "tributary resolve: member %s transfer %s tributary "
                "kind/unit (%s/%s) not recognized; skipped",
                member.id,
                transfer.get("id"),
                trib_kind,
                trib_unit,
            )
            continue
        total += line_n_per_m
        hit = True
        _log.info(
            "tributary resolve: member %s HIT via transfer %s from %s (%.3f N/m)",
            member.id,
            transfer.get("id"),
            source_id,
            line_n_per_m,
        )
    if not hit:
        return Ok(0.0)
    return Ok(total)


#: Force-unit -> N scale for a concentrated (point) load's magnitude
#: (WO-85/D194; the same small fixed-vocabulary posture as the tables
#: above -- an unrecognized unit is skipped, never guessed).
_FORCE_TO_N = {"N": 1.0, "kN": 1.0e3, "MN": 1.0e6}

#: The transfer classes whose (beam -> column) edge carries the source
#: member's gravity reaction into the receiving column as AXIAL demand
#: (WO-85 deliverable 3: "axial from column-role members' gravity load
#: paths"). `Bearing` is deliberately absent: a Bearing transfer is the
#: tributary-DISTRIBUTION idiom `resolve_tributary_demand` already
#: consumes as a line load, not an end reaction.
_AXIAL_TRANSFER_KINDS = ("Pinned", "Moment", "BasePlate")


# frob:doc docs/modules/py-orchestrator.md#frame_resolve
class MemberDemand(BaseModel):
    """One member's resolved gravity demand set (WO-85/D194): its
    uniformly-distributed line demand, its stationed point loads, and
    its axial demand from incoming gravity load paths -- the ONE home
    the utilization/deflection translate paths and the WO-65 section
    search all read (NO DUPLICATION: each consumer derives its own
    moment/deflection reduction from these fields via the methods
    below, never re-summing the raw payload)."""

    model_config = ConfigDict(frozen=True)

    #: Distributed demand (N/m): direct line/N-per-m loads + tributary.
    w_n_per_m: float = 0.0
    #: Stationed point loads: `(magnitude N, normalized station 0..1)`.
    point_loads: tuple[tuple[float, float], ...] = ()
    #: Axial demand (N) from incoming gravity load-path reactions.
    axial_n: float = 0.0

    # frob:doc docs/modules/py-orchestrator.md#frame_resolve
    def moment_nm(self, length_m: float) -> float:
        """Worst-case simple-span bending moment (N*m): `w*L^2/8` for
        the distributed part plus each point load's exact simple-span
        maximum `P*L*f*(1-f)`. Summing per-load MAXIMA (their peaks sit
        at different stations) is conservative, never optimistic
        (INV-9)."""
        moment = abs(self.w_n_per_m) * length_m**2 / 8.0
        for magnitude, station in self.point_loads:
            moment += abs(magnitude) * length_m * station * (1.0 - station)
        return moment

    # frob:doc docs/modules/py-orchestrator.md#frame_resolve
    def deflection_w_equiv(self, length_m: float) -> float:
        """The equivalent UDL (N/m) reproducing this demand's summed
        midspan deflection through the landed `5*w*L^4/(384*E*I)`
        model: each point load contributes its EXACT simple-span
        maximum-deflection term `P*b*(L^2-b^2)^1.5/(9*sqrt(3)*L*E*I)`
        (Roark; `b` = distance to the nearer support), re-expressed as
        a `w` so `EI` cancels -- exact linear superposition except that
        per-load maxima at different stations are summed, which is
        conservative (INV-9). An endpoint load (`b = 0`) deflects the
        span not at all -- its share rides the axial path instead."""
        if length_m <= 0.0:
            return abs(self.w_n_per_m)
        w_total = abs(self.w_n_per_m)
        for magnitude, station in self.point_loads:
            b = min(station, 1.0 - station) * length_m
            delta_term = b * (length_m**2 - b**2) ** 1.5 / (9.0 * 3.0**0.5 * length_m)
            w_total += 384.0 * abs(magnitude) * delta_term / (5.0 * length_m**4)
        return w_total

    # frob:doc docs/modules/py-orchestrator.md#frame_resolve
    def total_gravity_n(self, length_m: float) -> float:
        """The member's total gravity load (N): `w*L` plus every point
        load -- the reaction sum its outgoing transfers deliver."""
        return abs(self.w_n_per_m) * length_m + sum(abs(m) for m, _ in self.point_loads)


def _direct_line_demand(frame: dict, member_id: str) -> tuple[float, bool]:
    """Sum of literal line-unit loads directly targeting `member_id`
    (`(total N/m, any hit)`). Covers BOTH the SCHEMA 27 `line` kind
    (`kN/m` rows, WO-85) and a linear-unit `distributed` row. A `kPa`
    area load is NOT reduced here: a directly-targeted pressure entry
    carries no tributary width (only a `Bearing(tributary=...)`
    transfer does -- `resolve_tributary_demand`'s territory)."""
    total = 0.0
    hit = False
    for load in frame.get("loads", []):
        if load.get("target") != member_id:
            continue
        if load.get("kind") not in ("distributed", "line"):
            continue
        value = load.get("value") or {}
        scale = _LINE_TO_N_PER_M.get(value.get("unit"))
        if scale is None:
            continue
        magnitude = value.get("hi", value.get("lo", 0.0))
        total += float(magnitude) * scale
        hit = True
    return total, hit


def _point_loads(frame: dict, member_id: str) -> tuple[tuple[float, float], ...]:
    """Every stationed literal point load targeting `member_id` as
    `(magnitude N, station)` (WO-85/D194). A point row with no station
    is joint-targeted by construction (the frame producer never lowers
    a bare-member concentrated row -- E0211) and never appears here; a
    force unit outside the vocabulary is skipped, never guessed."""
    out: list[tuple[float, float]] = []
    for load in frame.get("loads", []):
        if load.get("target") != member_id:
            continue
        if load.get("kind") != "point":
            continue
        station = load.get("station")
        if station is None:
            continue
        value = load.get("value") or {}
        scale = _FORCE_TO_N.get(value.get("unit"))
        if scale is None:
            _log.info(
                "point load on %s: unit %r outside the force vocabulary; skipped",
                member_id,
                value.get("unit"),
            )
            continue
        magnitude = value.get("hi", value.get("lo", 0.0))
        out.append((float(magnitude) * scale, float(station)))
    return tuple(out)


# frob:doc docs/modules/py-orchestrator.md#frame_resolve
def declared_embedment_m(frame: dict, member_id: str) -> float | None:
    """`member_id`'s declared embedment depth in metres (WO-85/D194):
    the first outgoing transfer carrying a `depth` value
    (`EmbeddedPost(depth=1.4m)`, `FrameTransfer.depth`, SCHEMA 27), or
    `None` when no transfer declares one / the unit is unrecognized
    (the `civil.embedment` translator defers by name)."""
    for transfer in frame.get("transfers", []):
        if transfer.get("from") != member_id:
            continue
        depth = transfer.get("depth")
        if depth is None:
            continue
        depth_m = _length_m(depth)
        if depth_m is None:
            _log.info(
                "embedment resolve: member %s transfer %s depth unit "
                "unrecognized; skipped",
                member_id,
                transfer.get("id"),
            )
            continue
        _log.info(
            "embedment resolve: member %s declared depth %.3f m via %s",
            member_id,
            depth_m,
            transfer.get("id"),
        )
        return depth_m
    return None


def _member_length_m(frame: dict, member_id: str) -> float | None:
    """`member_id`'s payload length in metres, or `None` (unknown
    member / unrecognized unit)."""
    member = next(
        (m for m in frame.get("members", []) if m.get("id") == member_id), None
    )
    if member is None:
        return None
    return _length_m(member.get("length"))


# frob:doc docs/modules/py-orchestrator.md#frame_resolve
def reaction_into_n(
    frame: dict, target_id: str, _visited: frozenset[str] = frozenset()
) -> tuple[float, bool]:
    """The gravity-path reaction (N) delivered into ANY transfer target
    -- a column-role member (`_axial_demand`'s original territory,
    WO-85 deliverable 3) or a footing/support id (cycle 33/D196,
    `civil.bearing_pressure`'s reaction input): for every `Pinned`/
    `Moment`/`BasePlate` transfer INTO `target_id`, the source
    member's total gravity load (:meth:`MemberDemand.total_gravity_n`
    over its own direct + point + tributary loads) PLUS whatever
    reaction the source itself receives transitively through ITS OWN
    incoming transfers (the column-to-footing chain: this call
    recurses into `reaction_into_n(frame, source_id, ...)` before
    applying the source's outgoing split -- cycle 33/D196 closes the
    one-hop wall `_gravity_demand_of` deliberately left standing)
    delivers a reaction share.

    Cycle protection: `_visited` accumulates every target id already on
    the current walk; a transfer whose source is already in `_visited`
    is skipped (a malformed/cyclic transfer graph degrades to the
    local-only demand at that node, never an infinite recursion).

    Share rule (deterministic, disclosed): a source with exactly TWO
    outgoing reaction transfers splits its distributed total evenly
    (exact for the symmetric simple span every corpus frame declares)
    and delivers each point load's CONSERVATIVE end reaction
    `P*max(f, 1-f)` to both ends (the true reactions are `P*(1-f)` and
    `P*f`, but a transfer edge does not say which member end it sits
    at -- the conservative corner is taken, never a guess, INV-9),
    with any transitively-resolved incoming reaction split the SAME
    conservative way (halved); a source with ONE outgoing reaction
    transfer delivers its whole total, transitive reaction included;
    any other arity is skipped with a log line (an equal split over a
    3+-support beam is indeterminate, not closed-form). Multiple
    transfers landing on the SAME `target_id` are summed
    (conservative combination, disclosed).
    Returns `(total N, any resolvable path found)`."""
    total = 0.0
    hit = False
    transfers = frame.get("transfers", [])
    walked = _visited | {target_id}
    for transfer in transfers:
        if transfer.get("to") != target_id:
            continue
        if transfer.get("kind") not in _AXIAL_TRANSFER_KINDS:
            continue
        source_id = str(transfer.get("from"))
        if source_id in walked:
            _log.info(
                "reaction resolve: target %s transfer %s source %s already "
                "on this walk; cycle guard skipped it",
                target_id,
                transfer.get("id"),
                source_id,
            )
            continue
        source_length = _member_length_m(frame, source_id)
        if source_length is None:
            _log.info(
                "reaction resolve: target %s transfer %s source %s has no "
                "resolvable length; skipped",
                target_id,
                transfer.get("id"),
                source_id,
            )
            continue
        source_demand = _gravity_demand_of(frame, source_id, source_length)
        transitive_n, transitive_hit = reaction_into_n(frame, source_id, walked)
        if source_demand is None and not transitive_hit:
            continue
        local_total = (
            source_demand.total_gravity_n(source_length)
            if source_demand is not None
            else 0.0
        )
        outgoing = [
            t
            for t in transfers
            if t.get("from") == source_id and t.get("kind") in _AXIAL_TRANSFER_KINDS
        ]
        n_out = len(outgoing)
        if n_out == 1:
            share = local_total + transitive_n
        elif n_out == 2:
            share = transitive_n / 2.0
            if source_demand is not None:
                share += abs(source_demand.w_n_per_m) * source_length / 2.0
                for magnitude, station in source_demand.point_loads:
                    share += abs(magnitude) * max(station, 1.0 - station)
        else:
            _log.info(
                "reaction resolve: target %s source %s has %d reaction "
                "transfers; equal split over 3+ supports is indeterminate, "
                "skipped (not guessed)",
                target_id,
                source_id,
                n_out,
            )
            continue
        total += share
        hit = True
        _log.info(
            "reaction resolve: target %s HIT via transfer %s from %s (%.1f N, "
            "transitive=%.1f N)",
            target_id,
            transfer.get("id"),
            source_id,
            share,
            transitive_n,
        )
    return total, hit


def _axial_demand(frame: dict, member: ResolvedMember) -> tuple[float, bool]:
    """A column's axial demand (N) from incoming gravity load paths
    (WO-85 deliverable 3 -- the "axial pinned at 0" wall dies here);
    thin column-role gate over :func:`reaction_into_n` (NO DUPLICATION
    -- cycle 33/D196 generalized the reaction loop to any transfer
    target, this wrapper keeps the pre-existing column-only contract
    callers rely on)."""
    if member.role != "column":
        return 0.0, False
    return reaction_into_n(frame, member.id)


# frob:doc docs/modules/py-orchestrator.md#frame_resolve
# frob:waive TEST001 reason="frame-resolve helper, tested via frame-resolve tests"
def declared_footing_area_m2(frame: dict, support_id: str) -> float | None:
    """`support_id`'s declared bearing area in square metres (cycle
    33/D196, `civil.bearing_pressure`'s area input): the first
    transfer INTO `support_id` carrying a `tributary` value in area
    units (`m2`) -- the generic `FrameTransfer.tributary` field
    (SCHEMA_VERSION 27). Since WO-96's bearing close-out `std.civil`'s
    `BasePlate<anchors, bearing: area>` exposes an optional `bearing=`
    plate area, which the Rust lowering threads onto this same
    `tributary` field (`Bearing<tributary: area>` was the only prior
    source); this reader consumes either without a change.
    `None` when no incoming transfer declares an area-unit tributary
    -- the `civil.bearing_pressure` translator defers by name rather
    than fabricating an area."""
    for transfer in frame.get("transfers", []):
        if transfer.get("to") != support_id:
            continue
        tributary = transfer.get("tributary")
        if not isinstance(tributary, dict):
            continue
        if tributary.get("unit") != "m2":
            continue
        magnitude = tributary.get("hi", tributary.get("lo"))
        if not isinstance(magnitude, (int, float)):
            continue
        _log.info(
            "footing area resolve: support %s declared area %.3f m2 via %s",
            support_id,
            float(magnitude),
            transfer.get("id"),
        )
        return float(magnitude)
    return None


def _gravity_demand_of(
    frame: dict, member_id: str, length_m: float
) -> MemberDemand | None:
    """A SOURCE member's own LOCAL gravity demand (direct line + point
    + tributary; NO axial of its own -- `reaction_into_n` is what adds
    a source's transitively-resolved incoming reaction on top of this,
    cycle 33/D196), or `None` when nothing resolves. Used by
    :func:`_axial_demand`/`reaction_into_n` for the member at the far
    end of an incoming transfer."""
    w_direct, w_hit = _direct_line_demand(frame, member_id)
    points = _point_loads(frame, member_id)
    probe = ResolvedMember(
        id=member_id,
        role="",
        length_m=length_m,
        area_m2=1.0,
        i_m4=1.0,
        s_m3=1.0,
        e_pa=1.0,
        fy_pa=1.0,
    )
    tributary = resolve_tributary_demand(frame, probe)
    trib = tributary.danger_ok if tributary.is_ok else 0.0
    if not w_hit and not points and trib == 0.0:
        return None
    return MemberDemand(w_n_per_m=w_direct + trib, point_loads=points)


# frob:doc docs/modules/py-orchestrator.md#frame_resolve
def member_demand(
    frame: dict, member: ResolvedMember
) -> Result[MemberDemand, FrameResolutionError]:
    """The member's full resolved gravity demand (WO-85/D194): direct
    line loads (SCHEMA 27 `line` kind + linear-unit `distributed`
    rows) plus tributary-transfer demand (`resolve_tributary_demand`,
    WO-65/feldspar WO-23's seam) plus stationed point loads plus (for
    a column) axial demand from incoming gravity load paths.

    A member with NO resolvable demand source at all defers
    `frame_load_untargeted`, naming exactly that combined gap (not
    attempted, not fabricated)."""
    w_direct, w_hit = _direct_line_demand(frame, member.id)
    tributary = resolve_tributary_demand(frame, member)
    if tributary.is_err:
        return Err(tributary.danger_err)
    trib_total = tributary.danger_ok
    points = _point_loads(frame, member.id)
    axial, axial_hit = _axial_demand(frame, member)
    if not w_hit and trib_total == 0.0 and not points and not axial_hit:
        return Err(
            FrameResolutionError(
                reason="frame_load_untargeted",
                detail=(
                    f"member {member.id!r} carries no directly-targeted "
                    "literal distributed/line/point load in this frame's "
                    "`loads`, no resolvable tributary transfer, and no "
                    "resolvable incoming gravity load path in "
                    "`FramePayload.transfers` -- not attempted further, "
                    "not fabricated"
                ),
            )
        )
    demand = MemberDemand(
        w_n_per_m=w_direct + trib_total,
        point_loads=points,
        axial_n=axial,
    )
    _log.info(
        "member demand: %s w=%.3f N/m points=%d axial=%.1f N",
        member.id,
        demand.w_n_per_m,
        len(demand.point_loads),
        demand.axial_n,
    )
    return Ok(demand)


# frob:doc docs/modules/py-orchestrator.md#frame_resolve
def member_udl_demand(
    frame: dict, member: ResolvedMember
) -> Result[float, FrameResolutionError]:
    """The member's uniformly-distributed-load demand (N/m) alone: the
    direct line-unit loads plus tributary-transfer demand -- the
    pre-WO-85 surface, kept for callers that genuinely want ONLY the
    distributed component (and for the existing test contract). A
    member whose only demand is point/axial defers here; the full
    surface is :func:`member_demand`."""
    demand = member_demand(frame, member)
    if demand.is_err:
        return Err(demand.danger_err)
    resolved = demand.danger_ok
    if resolved.w_n_per_m == 0.0:
        return Err(
            FrameResolutionError(
                reason="frame_load_untargeted",
                detail=(
                    f"member {member.id!r} resolves no distributed demand "
                    "(its load paths are point/axial only) -- not a UDL "
                    "subject"
                ),
            )
        )
    return Ok(resolved.w_n_per_m)


# frob:doc docs/modules/py-orchestrator.md#frame_resolve
def frame_record_pins(ctx: FrameContext) -> tuple[tuple[str, str], ...]:
    """The INV-22 lockfile pins for every std.civil record this build's
    frame resolution consumed, sorted: ``(<key>@1, <row digest>)`` --
    revision 1 is the stdlib loader's fixed starter revision, exactly
    the `costing.record_pins` shape (one pin grammar, two ledgers)."""
    return tuple(
        (f"{key}@1", digest) for key, digest in sorted(ctx.consumed_pins.items())
    )


# frob:doc docs/modules/py-orchestrator.md#frame_resolve
# frob:waive TEST001 reason="frame-resolve helper, tested via frame-resolve tests"
def frame_winner_rows(ctx: FrameContext) -> tuple[LockRow, ...]:
    """Every WO-65 section-search winner's `cause: optimize(...)`
    lockfile row (INV-21), slot-sorted for deterministic rendering."""
    return tuple(ctx.winner_rows[slot] for slot in sorted(ctx.winner_rows))
