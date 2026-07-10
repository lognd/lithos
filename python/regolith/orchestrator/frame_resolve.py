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

Scope note (WO-65 update; the original WO-48 cut ledger note is
superseded, not silently dropped): this module resolves SECTION/
MATERIAL numeric properties (`resolve_member`) AND per-member UDL
demand (`member_udl_demand`), the latter now covering BOTH directly-
targeted literal loads (`on [...]`, calcite/03 sec. 4) AND tributary-
transfer demand via `resolve_tributary_demand` (feldspar WO-23's
`resolve_tributary_loads` seam, mirrored in-repo since feldspar is a
separate distribution this toolchain does not import -- WO-27), fed
by `FramePayload.transfers` (D176, WO-62 slice B). A member with
neither a direct load nor a resolvable tributary transfer still
defers `frame_load_untargeted`, naming exactly that combined gap.

WO-65 reopen (this module's newest addition): a `section: free`
member carrying a DECLARED candidate family (WO-68's
`FrameMember.section_domain`, `section: in registry(<family>)`) no
longer stops at the blanket `frame_section_domain_unsearched`
deferral -- :func:`search_free_section` runs a real section search
over that family's std.civil catalog rows, through the SANCTIONED
`regolith.orchestrator.optimize.optimize_discrete` driver (AD-30: no
private scoring path -- the evaluator IS the same moment/(S*Fy)
utilization formula `_translate_civil_utilization` already computes
for a resolved member, so search and discharge share one formula, not
two). Feasibility is the member's own flexural utilization
(`abs(moment)/(section_modulus*fy) <= 1.0`, mirroring feldspar's
AISC 360-16 F2.1 shape yield check -- feldspar's actual
`flexural_yield_capacity_f2` needs a plastic section modulus (Zx) NO
std.civil section record carries (only the elastic `s_mm3`/`s_in3`),
so this search reuses the elastic-modulus formula already landed in
`_translate_civil_utilization` rather than fabricate a Zx value; a
candidate with no resolvable `area`/`s` field is skipped, not
guessed). The objective is mass-per-length (`area_m2 *
material.density_kg_m3`, ascending -- no corpus design declares a
`policy:` block for its structural claims, so this is the WO-56
disclosed tie-break default, not a silent choice). A `section: free`
member with NO declared domain still defers `frame_section_free`
unchanged (D181: no reinterpretation); a declared family with no
std.civil rows defers `frame_section_family_not_landed`; a declared
family whose rows all lack usable properties (e.g. a family with no
`area`/`s` field at all) defers `capacity_unresolved`; a family whose
rows resolve but no candidate satisfies utilization<=1.0 defers
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
from regolith.harness.models.cost_common import LENGTH_TO_M
from regolith.logging_setup import get_logger
from regolith.magnetite.stdlib_records import row_hash
from regolith.orchestrator.optimize import (
    ChoicePointDomain,
    EvalOutcome,
    optimize_discrete,
)

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


class FrameRecordSet(BaseModel):
    """Every loaded std.civil section/material record, keyed by name,
    PLUS sections indexed by declared `family` in TOML declaration
    order (WO-65: the section search's candidate domain -- declaration
    order is the deterministic default enumeration order, AD-6)."""

    model_config = ConfigDict(frozen=True)

    sections: dict[str, SectionProps] = {}
    materials: dict[str, MaterialProps] = {}
    sections_by_family: dict[str, tuple[str, ...]] = {}


class FrameResolutionError(BaseModel):
    """A named frame-resolution failure the translate layer surfaces
    as an honest deferral (never an exception, never a silent skip)."""

    model_config = ConfigDict(frozen=True)

    reason: str
    detail: str


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
                ),
            )
    return Ok(None)


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


class FrameContext:
    """One build's frame-resolution state: the loaded std.civil
    section/material records, the build's raw frame payloads (name ->
    `FramePayload` dict, `BuildPayload.frames`), and the consumed-
    record pin ledger (the `CostContext.consumed_pins` precedent,
    INV-22's lockfile-pin shape)."""

    def __init__(
        self,
        *,
        records: FrameRecordSet,
        frames: dict[str, dict],
        search_paths: tuple[str, ...],
    ) -> None:
        """Bind one build's fixed frame-resolution inputs."""
        self.records = records
        self.frames = frames
        self.search_paths = search_paths
        # `std.civil.<section|material>.<key>` -> row digest.
        self.consumed_pins: dict[str, str] = {}


def load_frame_context(
    project_root: str,
    *,
    build_payload: dict[str, object] | None = None,
    record_search_paths: tuple[str, ...] = (),
) -> Result[FrameContext | None, OrchestratorError]:
    """Load this build's frame-resolution context, or `Ok(None)` when
    the build's payload carries no frames at all (a build with no
    calcite structures -- frame-referencing claims cannot even arise,
    so no honest reason to load std.civil records).

    `record_search_paths` extends the default (the project root
    itself) with additional local package roots (e.g. `stdlib/`),
    exactly the `load_cost_records` posture."""
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
    return Ok(
        FrameContext(records=loaded.danger_ok, frames=frames_raw, search_paths=paths)
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
        )
    )


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

    Feasibility: the member's own flexural utilization under its
    resolved demand (`member_udl_demand`, the SAME formula
    `_translate_civil_utilization` uses downstream) must be <= 1.0.
    Objective: mass-per-length (`area_m2 * material.density_kg_m3`),
    ascending -- the WO-56 disclosed tie-break default (no corpus
    design declares a `policy:` block for its structural claims).
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
    demand = member_udl_demand(frame, probe)
    if demand.is_err:
        return Err(demand.danger_err)
    w_load = demand.danger_ok
    moment = abs(w_load) * length_m**2 / 8.0

    usable_sections: dict[str, SectionProps] = {}
    for key in candidate_keys:
        section = ctx.records.sections[key]
        if section.area_m2 is not None and section.s_m3 is not None:
            usable_sections[key] = section
    if not usable_sections:
        return Err(
            FrameResolutionError(
                reason="capacity_unresolved",
                detail=(
                    f"member {member_id!r}'s declared family {section_domain!r} "
                    f"has {len(candidate_keys)} record(s), none carrying both "
                    "area and section-modulus fields this resolver reduces"
                ),
            )
        )

    def evaluate(assignment: Any) -> EvalOutcome:
        key = assignment[member_id]
        section = usable_sections[key]
        assert section.area_m2 is not None
        assert section.s_m3 is not None
        utilization = moment / (section.s_m3 * material.fy_pa)
        feasible = utilization <= 1.0
        mass_per_length = section.area_m2 * (material.density_kg_m3 or 0.0)
        return EvalOutcome(
            feasible=feasible,
            objective_vector=(mass_per_length,),
            verdict_summary=f"utilization={utilization:.4f} section={key}",
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
        return Err(
            FrameResolutionError(
                reason="frame_section_search_infeasible",
                detail=(
                    f"member {member_id!r}'s declared family {section_domain!r} "
                    f"searched {len(usable_sections)} candidate(s) with usable "
                    "properties; none satisfies utilization<=1.0 under the "
                    "resolved demand"
                ),
            )
        )
    winner_entry = trace.candidates[trace.winner]
    winner_key = winner_entry.assignment[0].root[1]
    winner = usable_sections[winner_key]
    trace_digest = (
        "blake3:" + blake3.blake3(trace.model_dump_json().encode("utf-8")).hexdigest()
    )
    cause = f"optimize(mass_per_length, winner={winner_key}, trace={trace_digest})"

    ctx.consumed_pins[f"std.civil.section.{winner.key}"] = winner.digest
    ctx.consumed_pins[f"std.civil.material.{material.key}"] = material.digest
    _log.info(
        "section search: member %s family=%s winner=%s %s",
        member_id,
        family,
        winner_key,
        cause,
    )
    return Ok(
        ResolvedMember(
            id=member_id,
            role=member.get("role", ""),
            length_m=length_m,
            area_m2=winner.area_m2 or 0.0,
            i_m4=winner.i_m4 or 0.0,
            s_m3=winner.s_m3,
            e_pa=material.e_pa,
            fy_pa=material.fy_pa,
            search_cause=cause,
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


def member_udl_demand(
    frame: dict, member: ResolvedMember
) -> Result[float, FrameResolutionError]:
    """The member's own uniformly-distributed-load demand (N/m): the
    sum of every literal `FrameLoad` entry directly targeting
    `member.id` (calcite/03 sec. 4's `on [...]` field) PLUS any
    tributary-transfer demand `resolve_tributary_demand` (WO-65,
    feldspar WO-23's seam) reduces from `FramePayload.transfers`.

    A member with NEITHER a directly-targeted literal load NOR a
    resolvable tributary transfer defers `frame_load_untargeted`,
    naming exactly that combined gap (not attempted, not fabricated).
    """
    total = 0.0
    hit = False
    for load in frame.get("loads", []):
        if load.get("target") != member.id:
            continue
        if load.get("kind") != "distributed":
            continue
        value = load.get("value") or {}
        unit = value.get("unit")
        magnitude = value.get("hi", value.get("lo", 0.0))
        # A `kPa` area load (calcite/02 sec. 7's `on [Deck]` shape) is
        # NOT reduced to a line load here: doing so honestly needs the
        # loaded area's tributary WIDTH, which a DIRECTLY-targeted load
        # entry does not itself carry (only a `Bearing(tributary=...)`
        # transfer does -- see `resolve_tributary_demand` above; a
        # direct pressure load stays out of scope for this loop,
        # unchanged from before WO-65). Only an already-linear load
        # unit is summed here.
        if unit in _LINE_TO_N_PER_M:
            total += float(magnitude) * _LINE_TO_N_PER_M[unit]
            hit = True
    tributary = resolve_tributary_demand(frame, member)
    if tributary.is_err:
        return Err(tributary.danger_err)
    trib_total = tributary.danger_ok
    if trib_total != 0.0:
        total += trib_total
        hit = True
    if not hit:
        return Err(
            FrameResolutionError(
                reason="frame_load_untargeted",
                detail=(
                    f"member {member.id!r} carries no directly-targeted "
                    "literal distributed load in this frame's `loads`, "
                    "and no resolvable tributary transfer in "
                    "`FramePayload.transfers` (either no Bearing "
                    "transfer names it, or the source member carries no "
                    "recognized pressure-unit load) -- not attempted "
                    "further, not fabricated"
                ),
            )
        )
    return Ok(total)
