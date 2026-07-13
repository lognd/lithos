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


class MediumProps(BaseModel):
    """One std.fluid `[[medium]]` record's properties (SI base units);
    a field the row does not carry stays honestly `None`."""

    model_config = ConfigDict(frozen=True)

    key: str
    digest: str
    rho_kg_m3: float | None = None
    mu_pa_s: float | None = None


class FluidContext:
    """One build's fluid-resolution state: the loaded `[[medium]]`
    property records, the build's raw flownet payloads (name -> dict,
    `BuildPayload.flownets` -- the `FrameContext.frames` posture), and
    the consumed-record pin ledger (INV-22)."""

    def __init__(
        self,
        *,
        records: dict[str, MediumProps],
        flownets: dict[str, dict],
        search_paths: tuple[str, ...],
    ) -> None:
        """Bind one build's fixed fluid-resolution inputs."""
        self.records = records
        self.flownets = flownets
        self.search_paths = search_paths
        # `std.fluid.medium.<key>` -> row digest (INV-22).
        self.consumed_pins: dict[str, str] = {}

    def consume(self, props: MediumProps) -> None:
        """Record the INV-22 pin for a record a claim input consumed."""
        self.consumed_pins[f"std.fluid.medium.{props.key}"] = props.digest

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
        out.setdefault(
            key,
            MediumProps(
                key=key,
                digest=row_hash(_MEDIUM_TABLE, row),
                rho_kg_m3=float(rho) if isinstance(rho, (int, float)) else None,
                mu_pa_s=float(mu) if isinstance(mu, (int, float)) else None,
            ),
        )
    return Ok(None)


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
    flownets_raw = (build_payload or {}).get("flownets")
    flownets: dict[str, dict] = (
        {str(k): v for k, v in flownets_raw.items() if isinstance(v, dict)}
        if isinstance(flownets_raw, dict)
        else {}
    )
    _log.debug(
        "fluid context loaded: %d medium record(s), %d flownet(s)",
        len(records),
        len(flownets),
    )
    return Ok(
        FluidContext(
            records=records,
            flownets=flownets,
            search_paths=(project_root, *record_search_paths),
        )
    )


def fluid_record_pins(ctx: FluidContext) -> tuple[tuple[str, str], ...]:
    """The INV-22 lockfile pins for every std.fluid medium record this
    build's dp resolution consumed, sorted -- the one pin grammar
    (`costing.record_pins`/`frame_record_pins` shape)."""
    return tuple(
        (f"{key}@1", digest) for key, digest in sorted(ctx.consumed_pins.items())
    )
