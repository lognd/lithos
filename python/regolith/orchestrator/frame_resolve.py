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

Scope note (recorded in the WO-48 cut ledger, not silently dropped):
this module resolves SECTION/MATERIAL numeric properties only. It
does NOT attempt tributary-transfer load-path analysis (turning a
distributed load declared `on [Deck]` into a girder's own bending
demand through a `Bearing(tributary=...)` transfer) -- the frame
payload's v1 `loads` field carries only literal `on [...]`-targeted
entries (calcite/03 sec. 4), the exact same limitation the WO-54
`civil_takeoff_estimate` close-out already names as a declared
exclusion for the same payload surface. A member whose demand is
not directly targeted by a literal load defers naming that gap.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith.errors import OrchestratorError
from regolith.logging_setup import get_logger
from regolith.magnetite.stdlib_records import row_hash

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
_LENGTH_TO_M = {"m": 1.0, "mm": 1.0e-3}


class SectionProps(BaseModel):
    """One std.civil section record's numeric properties (SI base
    units); a field this resolver cannot reduce (a family that ships
    no `area_mm2`/`i_mm4`, e.g. a per-metre strip section) stays
    `None` rather than a fabricated value."""

    model_config = ConfigDict(frozen=True)

    key: str
    digest: str
    area_m2: float | None = None
    i_m4: float | None = None
    s_m3: float | None = None


class MaterialProps(BaseModel):
    """One std.civil material record's elastic modulus and reference
    (yield/28-day) stress, SI base units (Pa)."""

    model_config = ConfigDict(frozen=True)

    key: str
    digest: str
    e_pa: float
    fy_pa: float


class FrameRecordSet(BaseModel):
    """Every loaded std.civil section/material record, keyed by name."""

    model_config = ConfigDict(frozen=True)

    sections: dict[str, SectionProps] = {}
    materials: dict[str, MaterialProps] = {}


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


def _section_props(key: str, row: dict[str, Any], digest: str) -> SectionProps:
    """Reduce one `[[section]]` TOML row to SI-unit numeric properties,
    leaving a field the row does not carry honestly `None`."""
    area_mm2 = row.get("area_mm2")
    i_mm4 = row.get("i_mm4")
    if i_mm4 is None:
        i_mm4 = row.get("i_mm4_per_m")
    s_mm3 = row.get("s_mm3")
    return SectionProps(
        key=key,
        digest=digest,
        area_m2=area_mm2 * _MM2_TO_M2 if isinstance(area_mm2, (int, float)) else None,
        i_m4=i_mm4 * _MM4_TO_M4 if isinstance(i_mm4, (int, float)) else None,
        s_m3=s_mm3 * _MM3_TO_M3 if isinstance(s_mm3, (int, float)) else None,
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
            out_materials.setdefault(
                key,
                MaterialProps(
                    key=key,
                    digest=digest,
                    e_pa=float(e_gpa) * _GPA_TO_PA,
                    fy_pa=float(fy_mpa) * _MPA_TO_PA,
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
    wins deterministically."""
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
    _log.debug(
        "loaded frame records: %d section(s), %d material(s) from %s",
        len(sections),
        len(materials),
        list(search_paths),
    )
    return Ok(FrameRecordSet(sections=sections, materials=materials))


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
    if not section_name or section_name == "free":
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


def member_udl_demand(
    frame: dict, member: ResolvedMember
) -> Result[float, FrameResolutionError]:
    """The member's own uniformly-distributed-load demand (N/m),
    summed from every literal `FrameLoad` entry directly targeting
    `member.id` (calcite/03 sec. 4's `on [...]` field).

    Deliberately does NOT attempt tributary-transfer analysis (see the
    module docstring's scope note): a member with no directly-targeted
    literal load (every corpus girder -- its load arrives through a
    `Bearing(tributary=...)` transfer from a slab member, not a
    literal `on [G1]` entry) defers `frame_load_untargeted`, naming
    exactly this gap rather than fabricating a tributary reaction.
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
        # loaded area's tributary WIDTH, which the v1 frame payload
        # does not carry (only the member's own length) -- reducing it
        # anyway would silently fabricate a width. Only an
        # already-linear load unit is summed.
        if unit in ("N/m", "kN/m"):
            scale = 1.0 if unit == "N/m" else 1.0e3
            total += float(magnitude) * scale
            hit = True
    if not hit:
        return Err(
            FrameResolutionError(
                reason="frame_load_untargeted",
                detail=(
                    f"member {member.id!r} carries no directly-targeted "
                    "literal distributed load in this frame's `loads` -- "
                    "its demand arrives through a Bearing/tributary "
                    "transfer, which the v1 frame payload does not carry "
                    "as numeric data (the same exclusion WO-54's civil "
                    "takeoff estimator already names for this payload "
                    "surface); not attempted here"
                ),
            )
        )
    return Ok(total)
