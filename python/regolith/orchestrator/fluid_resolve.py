"""Fluid medium-record chain resolution: a `fluids.dp(...)` claim's
missing `density_kgm3` input walks obligation -> flownet payload ->
`medium.records` -> the std.fluid `[[medium]]` property record
(WO-112 Class 4, the F131.4 chain half of `fluids.dp_inputs_missing`).

The fluorite corpus declares its medium properties BY REFERENCE
(`medium BrewWater: liquid` / `props: registry(water_iapws_liquid)`),
and the Rust lowering threads those names into the flownet payload's
`medium.records` -- but nothing ever WALKED the chain, so every dp
claim deferred naming ALL of its inputs even when density was one
record lookup away. This module is that walk: the flownet payloads
come from the build payload (the `FrameContext.frames` posture), the
`[[medium]]` rows load from the same D192 record search paths every
other record family uses, and a resolved record pins an INV-22 ledger
row. A medium record the design names but the paths do not carry
stays an honest, NAMED gap (the Class D half -- authoring the record
is WO-113/D224 territory, never fabricated here).
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith.errors import OrchestratorError
from regolith.logging_setup import get_logger
from regolith.magnetite.stdlib_records import row_hash

_log = get_logger(__name__)

# The record TOML table this loader consumes (`std.fluid`'s
# `media.toml` row shape).
_MEDIUM_TABLE = "medium"

# WO-139 (D258.3/F158 GAP a3 consumption rule): the `std.fluid`
# `roughness.toml` catalog table -- `[[roughness]]` rows keyed by
# `material`, consumed to derive a missing `friction_factor` input
# (never a fallback for an inline declaration, AD-22).
_ROUGHNESS_TABLE = "roughness"


# frob:doc docs/modules/py-orchestrator.md#fluid_resolve
class MediumProps(BaseModel):
    """One std.fluid `[[medium]]` record's properties (SI base units);
    a field the row does not carry stays honestly `None`.

    WO-138 widening (D258.1/F158 GAP c3 consumption rule): beyond the
    original rho/mu single-point scalars, a row may also carry cp,
    pv, and k (conductivity) -- either as a single-point scalar (the
    media.toml convention today) or as a cited POINT TABLE (the
    polymer_melt.toml `[{t_k, value, note}]` convention, D182) when
    the record needs more than one state. `bracket_conservative`
    resolves a claim's corner temperature against a point table by
    taking the WORSE (never-narrowing, INV-9) of the two rows
    straddling it -- it never interpolates a fabricated in-between
    value, and returns `None` (an honest out-of-domain absence) when
    the corner temperature falls outside every recorded point."""

    model_config = ConfigDict(frozen=True)

    key: str
    digest: str
    rho_kg_m3: float | None = None
    mu_pa_s: float | None = None
    cp_j_kgk: float | None = None
    pv_pa: float | None = None
    k_w_mk: float | None = None
    # Optional point tables: (t_k, value) pairs, sorted by t_k ascending.
    rho_points: tuple[tuple[float, float], ...] = ()
    mu_points: tuple[tuple[float, float], ...] = ()
    cp_points: tuple[tuple[float, float], ...] = ()
    pv_points: tuple[tuple[float, float], ...] = ()
    k_points: tuple[tuple[float, float], ...] = ()

    # frob:doc docs/modules/py-orchestrator.md#fluid_resolve
    # frob:waive TEST001 reason="fluid-resolve helper, tested via fluid record tests"
    # frob:waive TEST005 reason="measured 5.9% branch on 2026-07-19; backfill T-0036"
    def bracket_conservative(
        self, points: tuple[tuple[float, float], ...], t_k: float, *, sense: str
    ) -> float | None:
        """The conservative bound for `t_k` from a `(t_k, value)` point
        table: `sense="upper"` takes the larger of the two bracketing
        rows' values, `sense="lower"` the smaller -- an outward-only
        widen (INV-9), never a narrowing interpolation. `None` (an
        honest named absence, never a silent clamp) when `t_k` is
        outside the table's own recorded range or the table is empty."""
        if not points:
            return None
        if t_k < points[0][0] or t_k > points[-1][0]:
            return None
        lo = points[0]
        hi = points[-1]
        for a, b in zip(points, points[1:], strict=False):
            if a[0] <= t_k <= b[0]:
                lo, hi = a, b
                break
        candidates = (lo[1], hi[1])
        if sense == "upper":
            return max(candidates)
        if sense == "lower":
            return min(candidates)
        raise ValueError(f"unknown bracketing sense: {sense!r}")


# frob:doc docs/modules/py-orchestrator.md#fluid_resolve
class RoughnessProps(BaseModel):
    """One std.fluid `[[roughness]]` catalog record (WO-139/D258.1
    GAP a3): a material's absolute roughness height, either a single
    cited figure (`roughness_m`) or a cited RANGE (`roughness_m_min`/
    `roughness_m_max`, e.g. concrete/riveted steel's construction-
    dependent spread) -- both bounds are recorded rather than picking
    one, so a claim's bracketing walk takes the conservative end."""

    model_config = ConfigDict(frozen=True)

    key: str
    digest: str
    roughness_m: float | None = None
    roughness_m_min: float | None = None
    roughness_m_max: float | None = None

    # frob:doc docs/modules/py-orchestrator.md#fluid_resolve
    # frob:waive TEST001 reason="fluid-resolve helper, tested via fluid record tests"
    # frob:waive TEST005 reason="measured 50.0% branch on 2026-07-19; backfill T-0036"
    def interval_m(self) -> tuple[float, float] | None:
        """This record's roughness height as an `(lo, hi)` pair (m);
        `None` if the row carries neither a point value nor a range
        (an honest absence, never fabricated)."""
        if self.roughness_m is not None:
            return (self.roughness_m, self.roughness_m)
        if self.roughness_m_min is not None and self.roughness_m_max is not None:
            return (self.roughness_m_min, self.roughness_m_max)
        return None


# frob:doc docs/modules/py-orchestrator.md#fluid_resolve
class FluidContext:
    """One build's fluid-resolution state: the loaded `[[medium]]`
    property records, the loaded `[[roughness]]` catalog records
    (WO-139), the build's raw flownet payloads (name -> dict,
    `BuildPayload.flownets` -- the `FrameContext.frames` posture), and
    the consumed-record pin ledger (INV-22)."""

    def __init__(
        self,
        *,
        records: dict[str, MediumProps],
        flownets: dict[str, dict],
        search_paths: tuple[str, ...],
        roughness: dict[str, RoughnessProps] | None = None,
    ) -> None:
        """Bind one build's fixed fluid-resolution inputs."""
        self.records = records
        self.flownets = flownets
        self.search_paths = search_paths
        self.roughness = roughness if roughness is not None else {}
        # `std.fluid.medium.<key>` / `std.fluid.roughness.<key>` -> row
        # digest (INV-22, one shared ledger both record families pin
        # into).
        self.consumed_pins: dict[str, str] = {}
        # WO-139: a human-readable note per DERIVED friction_factor
        # (its model citation + the roughness record it pinned) -- the
        # calc package's own appendix so a reviewer sees the citation
        # for an input that never became its own obligation/calc sheet
        # (see `orchestrator.translate._translate_fluid_dp`).
        self.derived_notes: list[str] = []

    # frob:doc docs/modules/py-orchestrator.md#fluid_resolve
    def consume(self, props: MediumProps) -> None:
        """Record the INV-22 pin for a record a claim input consumed."""
        self.consumed_pins[f"std.fluid.medium.{props.key}"] = props.digest

    # frob:doc docs/modules/py-orchestrator.md#fluid_resolve
    # frob:waive TEST001 reason="fluid-resolve helper, tested via fluid record tests"
    def consume_roughness(self, props: RoughnessProps) -> None:
        """Record the INV-22 pin for a roughness record a claim
        input actually consumed (WO-139)."""
        self.consumed_pins[f"std.fluid.roughness.{props.key}"] = props.digest

    # frob:doc docs/modules/py-orchestrator.md#fluid_resolve
    # frob:waive TEST001 reason="fluid-resolve helper, tested via fluid record tests"
    def roughness_for(self, material: str) -> RoughnessProps | None:
        """The `[[roughness]]` record for a material key, or `None`
        (an honest named absence -- authoring the record is D224
        territory, never fabricated here)."""
        return self.roughness.get(material)

    # frob:doc docs/modules/py-orchestrator.md#fluid_resolve
    # frob:waive TEST001 reason="fluid-resolve helper, tested via fluid record tests"
    def medium_record_names(self, flownet_name: str) -> tuple[str, ...]:
        """The `medium.records` names the named flownet's medium
        declares (`props: registry(<key>)`), in declaration order;
        empty for an unknown flownet or a record-less medium."""
        flownet = self.flownets.get(flownet_name)
        if not isinstance(flownet, dict):
            return ()
        medium = flownet.get("medium")
        if not isinstance(medium, dict):
            return ()
        records = medium.get("records")
        if not isinstance(records, list):
            return ()
        return tuple(
            str(r.get("name")) for r in records if isinstance(r, dict) and r.get("name")
        )


def _load_medium_file(
    path: Path, out: dict[str, MediumProps]
) -> Result[None, OrchestratorError]:
    """Load one records TOML file's `[[medium]]` rows; other tables
    (pump curves, pipe tables, ...) have their own consumers."""
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return Err(
            OrchestratorError(kind="fluid_records_malformed", message=f"{path}: {exc}")
        )
    rows = data.get(_MEDIUM_TABLE)
    if not isinstance(rows, list):
        return Ok(None)
    for row in rows:
        if not isinstance(row, dict) or "key" not in row:
            return Err(
                OrchestratorError(
                    kind="fluid_records_malformed",
                    message=f"{path}: a 'medium' row has no 'key'",
                )
            )
        key = str(row["key"])
        rho = row.get("rho_kg_m3")
        mu = row.get("mu_Pa_s")
        cp = row.get("cp_J_kgK")
        pv = row.get("pv_Pa")
        k = row.get("k_W_mK")
        out.setdefault(
            key,
            MediumProps(
                key=key,
                digest=row_hash(_MEDIUM_TABLE, row),
                rho_kg_m3=float(rho) if isinstance(rho, (int, float)) else None,
                mu_pa_s=float(mu) if isinstance(mu, (int, float)) else None,
                cp_j_kgk=float(cp) if isinstance(cp, (int, float)) else None,
                pv_pa=float(pv) if isinstance(pv, (int, float)) else None,
                k_w_mk=float(k) if isinstance(k, (int, float)) else None,
                rho_points=_point_table(row.get("rho_kg_m3_points")),
                mu_points=_point_table(row.get("mu_Pa_s_points")),
                cp_points=_point_table(row.get("cp_J_kgK_points")),
                pv_points=_point_table(row.get("pv_Pa_points")),
                k_points=_point_table(row.get("k_W_mK_points")),
            ),
        )
    return Ok(None)


def _load_roughness_file(
    path: Path, out: dict[str, RoughnessProps]
) -> Result[None, OrchestratorError]:
    """Load one records TOML file's `[[roughness]]` rows (WO-139/
    D258.1 GAP a3: `stdlib/std.fluid/records/roughness.toml`), keyed
    by `material` -- one row per material/finish, the source's own
    reprinted list, never a fit this loader invents."""
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return Err(
            OrchestratorError(kind="fluid_records_malformed", message=f"{path}: {exc}")
        )
    rows = data.get(_ROUGHNESS_TABLE)
    if not isinstance(rows, list):
        return Ok(None)
    for row in rows:
        if not isinstance(row, dict) or "key" not in row:
            return Err(
                OrchestratorError(
                    kind="fluid_records_malformed",
                    message=f"{path}: a 'roughness' row has no 'key'",
                )
            )
        material = row.get("material")
        if not isinstance(material, str) or not material:
            return Err(
                OrchestratorError(
                    kind="fluid_records_malformed",
                    message=f"{path}: roughness row {row['key']!r} has no 'material'",
                )
            )
        r_m = row.get("roughness_m")
        r_min = row.get("roughness_m_min")
        r_max = row.get("roughness_m_max")
        out.setdefault(
            material,
            RoughnessProps(
                key=str(row["key"]),
                digest=row_hash(_ROUGHNESS_TABLE, row),
                roughness_m=float(r_m) if isinstance(r_m, (int, float)) else None,
                roughness_m_min=(
                    float(r_min) if isinstance(r_min, (int, float)) else None
                ),
                roughness_m_max=(
                    float(r_max) if isinstance(r_max, (int, float)) else None
                ),
            ),
        )
    return Ok(None)


# frob:waive PERF004 reason="one-shot sort of a small set, never re-sorted"
def _point_table(raw: object) -> tuple[tuple[float, float], ...]:
    """Parse an optional `[{t_k, value, note}]` point-table field (the
    `polymer_melt.toml` rho_melt/mu convention, D182) into sorted
    `(t_k, value)` pairs; the field's own second key name varies per
    property (`rho_kg_m3`, `mu_pa_s`, `cp_j_kgk`, `pv_pa`, `k_w_mk`),
    so every non-`t_k`/`note` numeric field on the row is accepted."""
    if not isinstance(raw, list):
        return ()
    points: list[tuple[float, float]] = []
    for entry in raw:
        if not isinstance(entry, dict) or "t_k" not in entry:
            continue
        t_k = entry.get("t_k")
        value = next(
            (
                v
                for k, v in entry.items()
                if k not in ("t_k", "note") and isinstance(v, (int, float))
            ),
            None,
        )
        if isinstance(t_k, (int, float)) and value is not None:
            points.append((float(t_k), float(value)))
    return tuple(sorted(points, key=lambda p: p[0]))


# frob:doc docs/modules/py-orchestrator.md#fluid_resolve
def load_fluid_context(
    project_root: str,
    *,
    build_payload: dict[str, object] | None = None,
    record_search_paths: tuple[str, ...] = (),
) -> Result[FluidContext, OrchestratorError]:
    """Load this build's fluid-resolution context (always `Ok`: a
    build with no flownets or no medium records simply resolves
    nothing, and a dp claim then defers naming what is missing --
    the honest si/material-context posture).

    The directory walk is the `load_frame_records` posture verbatim:
    each search path contributes its own `records/*.toml` plus every
    package subdirectory's, sorted, first row per key wins.
    """
    records: dict[str, MediumProps] = {}
    roughness: dict[str, RoughnessProps] = {}
    for base_str in (project_root, *record_search_paths):
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
                loaded = _load_medium_file(toml_file, records)
                if loaded.is_err:
                    return Err(loaded.danger_err)
                # WO-139: the same directory walk also loads
                # `[[roughness]]` rows (one file, `roughness.toml`,
                # today; any file may carry the table).
                loaded_roughness = _load_roughness_file(toml_file, roughness)
                if loaded_roughness.is_err:
                    return Err(loaded_roughness.danger_err)
    flownets_raw = (build_payload or {}).get("flownets")
    flownets: dict[str, dict] = (
        {str(k): v for k, v in flownets_raw.items() if isinstance(v, dict)}
        if isinstance(flownets_raw, dict)
        else {}
    )
    _log.debug(
        "fluid context loaded: %d medium record(s), %d roughness record(s), "
        "%d flownet(s)",
        len(records),
        len(roughness),
        len(flownets),
    )
    return Ok(
        FluidContext(
            records=records,
            flownets=flownets,
            search_paths=(project_root, *record_search_paths),
            roughness=roughness,
        )
    )


# frob:doc docs/modules/py-orchestrator.md#fluid_resolve
def fluid_record_pins(ctx: FluidContext) -> tuple[tuple[str, str], ...]:
    """The INV-22 lockfile pins for every std.fluid medium/roughness
    record this build's dp resolution consumed, sorted -- the one pin
    grammar (`costing.record_pins`/`frame_record_pins` shape)."""
    return tuple(
        (f"{key}@1", digest) for key, digest in sorted(ctx.consumed_pins.items())
    )


# frob:doc docs/modules/py-orchestrator.md#fluid_resolve
def fluid_derived_notes(ctx: FluidContext) -> tuple[str, ...]:
    """The WO-139 derived-friction-factor notes this build recorded,
    in recording order -- surfaces a derived input's model citation in
    the calc package appendix (`build_calc_book`'s `notes=`)."""
    return tuple(ctx.derived_notes)
