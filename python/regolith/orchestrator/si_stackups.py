"""Stackup-record resolution for signal-integrity claims (WO-78).

This module owns the orchestrator half of charter 35 sec. 1.1-1.2's
record story: loading fab-published `[[stackup]]` record rows
(``stdlib/std.elec.stackups`` and any local package roots) and
resolving an ``elec.impedance(<net>, stackup=<key>, ...)`` claim's
dielectric geometry (h/er/t) from the named record instead of from
in-claim folklore numbers. The obligation-to-request lowering itself
stays in :mod:`regolith.orchestrator.translate` (the
``costing``/``plan_staging`` split, applied to SI).

Honesty rules carried from the record file's own ledger
(`stdlib/std.elec.stackups/records/jlcpcb.toml`):

- Microstrip (outer layer) is the ONLY stackup-derived mapping: the
  fab publishes the outer prepreg span + material Dk + outer copper,
  which are exactly Hammerstad-Jensen's h/er/t. The single-core
  2-layer record uses its core span/Dk the same way.
- Stripline cavity heights are NOT derived (no per-layer role table is
  published); a stripline claim supplies ``b``/``er`` explicitly and
  the deferral for a stackup-derived request names this residual.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError
from typani.result import Err, Ok, Result

from regolith.errors import OrchestratorError
from regolith.logging_setup import get_logger

_log = get_logger(__name__)

# The record TOML table this loader consumes (`[[stackup]]` rows, the
# stdlib/std.elec.stackups shape).
_STACKUP_TABLE = "stackup"


# frob:doc docs/modules/py-orchestrator.md#si_stackups
class StackupRecord(BaseModel):
    """One fab-published stackup row (AD-34-cited; charter 35 sec. 1.1).

    Dimensions are millimetres as published; ``microstrip_*`` accessors
    return SI base units for the model ports.
    """

    model_config = ConfigDict(frozen=True)

    key: str
    name: str
    layer_count: int
    outer_copper_mm: float
    core_mm: float | None = None
    core_dk: float | None = None
    outer_prepreg_mm: float | None = None
    outer_prepreg_dk: float | None = None
    reference: str
    source_file: str

    # frob:doc docs/modules/py-orchestrator.md#si_stackups
    # frob:waive TEST005 reason="measured 50.0% branch on 2026-07-19; backfill T-0036"
    def microstrip_h_m(self) -> float | None:
        """The outer-layer microstrip dielectric height in metres: the
        published outer prepreg span, or the single core span on a
        2-layer stackup; ``None`` when the record states neither."""
        if self.outer_prepreg_mm is not None:
            return self.outer_prepreg_mm / 1000.0
        if self.core_mm is not None:
            return self.core_mm / 1000.0
        return None

    # frob:doc docs/modules/py-orchestrator.md#si_stackups
    def microstrip_er(self) -> float | None:
        """The dielectric constant paired with :meth:`microstrip_h_m`
        (prepreg Dk, or core Dk on a 2-layer stackup)."""
        if self.outer_prepreg_mm is not None:
            return self.outer_prepreg_dk
        return self.core_dk

    # frob:doc docs/modules/py-orchestrator.md#si_stackups
    def microstrip_t_m(self) -> float:
        """The published outer copper thickness in metres."""
        return self.outer_copper_mm / 1000.0


# frob:doc docs/modules/py-orchestrator.md#si_stackups
class SiContext(BaseModel):
    """One build's SI resolution state: the loaded stackup records,
    keyed by record key (the ``stackup=<key>`` claim kwarg)."""

    model_config = ConfigDict(frozen=True)

    stackups: dict[str, StackupRecord] = {}


def _load_stackup_file(
    path: Path, stackups: dict[str, StackupRecord]
) -> Result[None, OrchestratorError]:
    """Load one records TOML file's ``[[stackup]]`` rows into
    ``stackups`` (later files/rows never silently shadow earlier ones:
    a duplicate key is a loud error, the rule-pack collision posture)."""
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return Err(
            OrchestratorError(kind="si_records_malformed", message=f"{path}: {exc}")
        )
    for row in data.get(_STACKUP_TABLE, ()):
        if not isinstance(row, dict):
            return Err(
                OrchestratorError(
                    kind="si_records_malformed",
                    message=f"{path}: [[stackup]] row is not a table",
                )
            )
        evidence = row.get("evidence")
        reference = ""
        if isinstance(evidence, dict):
            reference = str(evidence.get("reference", ""))
        try:
            record = StackupRecord(
                key=str(row.get("key", "")),
                name=str(row.get("name", "")),
                layer_count=int(row.get("layer_count", 0)),
                outer_copper_mm=float(row.get("outer_copper_mm", 0.0)),
                core_mm=(
                    float(row["core_mm"]) if row.get("core_mm") is not None else None
                ),
                core_dk=(
                    float(row["core_dk"]) if row.get("core_dk") is not None else None
                ),
                outer_prepreg_mm=(
                    float(row["outer_prepreg_mm"])
                    if row.get("outer_prepreg_mm") is not None
                    else None
                ),
                outer_prepreg_dk=(
                    float(row["outer_prepreg_dk"])
                    if row.get("outer_prepreg_dk") is not None
                    else None
                ),
                reference=reference,
                source_file=str(path),
            )
        except (TypeError, ValueError, ValidationError) as exc:
            return Err(
                OrchestratorError(
                    kind="si_records_malformed",
                    message=f"{path}: [[stackup]] row {row.get('key')!r}: {exc}",
                )
            )
        if not record.key:
            return Err(
                OrchestratorError(
                    kind="si_records_malformed",
                    message=f"{path}: [[stackup]] row with no key",
                )
            )
        if record.key in stackups:
            return Err(
                OrchestratorError(
                    kind="si_records_duplicate",
                    message=(
                        f"{path}: stackup key {record.key!r} already loaded from "
                        f"{stackups[record.key].source_file}"
                    ),
                )
            )
        stackups[record.key] = record
    return Ok(None)


# frob:doc docs/modules/py-orchestrator.md#si_stackups
def load_si_context(
    project_root: str,
    *,
    record_search_paths: tuple[str, ...] = (),
) -> Result[SiContext, OrchestratorError]:
    """Load the build's SI stackup context (always ``Ok`` for a
    stackup-less build -- an impedance claim naming a stackup this
    build never loaded simply defers honestly at translate time).

    Each search path contributes its own ``records/*.toml`` plus every
    package subdirectory's (``<path>/<pkg>/records/*.toml``), in sorted
    order -- the ``costing.load_cost_records`` walk, applied to
    ``[[stackup]]`` rows.
    """
    stackups: dict[str, StackupRecord] = {}
    for search_path in (project_root, *record_search_paths):
        base = Path(search_path)
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
                loaded = _load_stackup_file(toml_file, stackups)
                if loaded.is_err:
                    return Err(loaded.danger_err)
    _log.info(
        "loaded SI stackup records: %d stackup(s) from %s",
        len(stackups),
        (project_root, *record_search_paths),
    )
    return Ok(SiContext(stackups=stackups))
