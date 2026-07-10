"""`plan:` linkage staging: extern plan bytes + machine/tooling/target
records reaching the landed `std.cam` pack (WO-69; regolith/08 sec. 4's
L6 row, WO-67's close-out ledger follow-up).

Mirrors `regolith.orchestrator.costing`'s staged-doc precedent: this
module owns resolving the source-declared `machine=`/`tooling=` record
refs (the ``[[machine]]``/``[[tool]]``/``[[stock_target]]`` local
record tables, same `key = "..."`/local-path-only posture as
`costing.load_cost_records`) and reading the extern-referenced plan
bytes off disk, staging both into the build's ONE `PayloadStore`
(D96/D154) so the `std.cam` models' `plan`/`cam_machine`/`cam_tooling`/
`cam_target` ports resolve. The obligation-to-request lowering itself
stays in :mod:`regolith.orchestrator.translate` (`_translate_cam`),
which maps this module's error values onto its own `Deferral` surface
-- same split as costing/translate.

Every consumed record lands in `PlanContext.consumed_pins` (INV-22),
read out by :func:`record_pins` post-discharge, mirroring
`costing.record_pins` exactly.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError
from typani.result import Err, Ok, Result

from regolith.errors import OrchestratorError
from regolith.harness.models.cam.records import MachineRecord, StockTarget, ToolRecord
from regolith.logging_setup import get_logger
from regolith.magnetite.stdlib_records import row_hash
from regolith.orchestrator.payload_store import PayloadStore

_log = get_logger(__name__)

# The record TOML tables this loader consumes (mirrors costing's
# `[[rate]]`/`[[pricing]]`/`[[unit_cost]]` precedent, WO-66-soft
# fixture-shaped records per WO-67's own ledger note).
_MACHINE_TABLE = "machine"
_TOOL_TABLE = "tool"
_STOCK_TARGET_TABLE = "stock_target"


class PlanResolutionError(BaseModel):
    """A named plan-resolution failure `translate._translate_cam`
    surfaces as an honest deferral (never an exception, never a
    silent skip)."""

    model_config = ConfigDict(frozen=True)

    reason: str
    detail: str


class PlanRecordSet(BaseModel):
    """Every loaded machine/tooling/stock-target record, keyed by its
    declared `key` (the same dotted-ref text a `plan:` clause's
    `machine=`/`tooling=` argument names)."""

    model_config = ConfigDict(frozen=True)

    machines: dict[str, MachineRecord] = {}
    tools: dict[str, ToolRecord] = {}
    stock_targets: dict[str, StockTarget] = {}


def _load_record_file(
    path: Path,
    out_machines: dict[str, tuple[str, MachineRecord]],
    out_tools: dict[str, tuple[str, ToolRecord]],
    out_targets: dict[str, tuple[str, StockTarget]],
) -> Result[None, OrchestratorError]:
    """Load one records TOML file's `machine`/`tool`/`stock_target`
    tables into the three maps (value = `(digest, record)`, the digest
    an INV-22 lockfile pin later cites). A malformed row is a loud
    error naming the file and key; any other table is skipped (other
    record families -- cost, sections, ... -- have their own loaders)."""
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return Err(
            OrchestratorError(kind="plan_records_malformed", message=f"{path}: {exc}")
        )
    for table, rows in data.items():
        if table not in (_MACHINE_TABLE, _TOOL_TABLE, _STOCK_TARGET_TABLE):
            continue
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict) or "key" not in row:
                return Err(
                    OrchestratorError(
                        kind="plan_records_malformed",
                        message=f"{path}: a {table!r} row has no 'key'",
                    )
                )
            key = str(row["key"])
            digest = row_hash(table, row)
            try:
                if table == _MACHINE_TABLE:
                    out_machines.setdefault(
                        key, (digest, MachineRecord.model_validate(row))
                    )
                elif table == _TOOL_TABLE:
                    out_tools.setdefault(key, (digest, ToolRecord.model_validate(row)))
                else:
                    out_targets.setdefault(
                        key, (digest, StockTarget.model_validate(row))
                    )
            except ValidationError as exc:
                return Err(
                    OrchestratorError(
                        kind="plan_records_malformed",
                        message=f"{path}: {table}/{key}: {exc}",
                    )
                )
    return Ok(None)


def load_plan_records(
    search_paths: tuple[str, ...],
) -> Result[
    dict[str, tuple[str, MachineRecord | ToolRecord | StockTarget]], OrchestratorError
]:
    """Load every `machine`/`tool`/`stock_target` record under
    `search_paths` (local-path only, the `costing.load_cost_records`
    posture: no network, no registry fetch). Each search path
    contributes its own `records/*.toml` plus every package
    subdirectory's, in sorted order; the FIRST loaded row for a key
    wins deterministically. Returns the three families flattened into
    ONE `key -> (digest, record)` map (the caller narrows by type);
    kept flat rather than three separate dicts so a duplicate key
    across families is still deterministic-first-wins, matching
    `load_cost_records`'s own one-namespace-per-loader shape at the
    file level.
    """
    machines: dict[str, tuple[str, MachineRecord]] = {}
    tools: dict[str, tuple[str, ToolRecord]] = {}
    targets: dict[str, tuple[str, StockTarget]] = {}
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
                loaded = _load_record_file(toml_file, machines, tools, targets)
                if loaded.is_err:
                    return Err(loaded.danger_err)
    _log.debug(
        "loaded plan records: %d machine(s), %d tool(s), %d stock_target(s) from %s",
        len(machines),
        len(tools),
        len(targets),
        list(search_paths),
    )
    merged: dict[str, tuple[str, MachineRecord | ToolRecord | StockTarget]] = {}
    merged.update(machines)
    merged.update(tools)
    merged.update(targets)
    return Ok(merged)


class PlanContext:
    """One build's plan-resolution state: the loaded machine/tooling/
    stock-target records, the project root plan bytes resolve
    relative to, the staging store handle, and the consumed-record pin
    ledger (INV-22) -- mirrors `costing.CostContext` exactly."""

    def __init__(
        self,
        *,
        project_root: str,
        records: dict[str, tuple[str, MachineRecord | ToolRecord | StockTarget]],
        store: PayloadStore | None,
    ) -> None:
        """Bind one build's fixed plan-resolution inputs."""
        self.project_root = Path(project_root)
        self.records = records
        self.store = store
        # Record key (or plan ref path) -> digest, for the lockfile's
        # `pin` lines.
        self.consumed_pins: dict[str, str] = {}

    def machine(self, key: str) -> MachineRecord | None:
        """The declared machine record for `key`, if loaded and of the
        right type (a key colliding across families is a config error
        the loader already logs; this narrows honestly, never guesses)."""
        found = self.records.get(key)
        if found is None or not isinstance(found[1], MachineRecord):
            return None
        return found[1]

    def tool(self, key: str) -> ToolRecord | None:
        """The declared tool record for `key`, if loaded and typed right."""
        found = self.records.get(key)
        if found is None or not isinstance(found[1], ToolRecord):
            return None
        return found[1]

    def stock_target(self, key: str) -> StockTarget | None:
        """The declared stock-target record for `key`, if loaded and typed right."""
        found = self.records.get(key)
        if found is None or not isinstance(found[1], StockTarget):
            return None
        return found[1]

    def digest_of(self, key: str) -> str | None:
        """The record digest for `key` (the INV-22 pin value)."""
        found = self.records.get(key)
        return None if found is None else found[0]


def load_plan_context(
    project_root: str,
    *,
    payload_store: PayloadStore | None,
    record_search_paths: tuple[str, ...] = (),
) -> Result[PlanContext, OrchestratorError]:
    """Load the build's plan context (always `Ok`, even with zero
    records loaded -- `cam.*` obligations naming a record this build
    never declared simply defer honestly at translate time, never an
    error for a plan-less build). `record_search_paths` extends the
    default (the project root itself) with additional local package
    roots, same posture as `costing.load_cost_context`.
    """
    records_result = load_plan_records((project_root, *record_search_paths))
    if records_result.is_err:
        return Err(records_result.danger_err)
    return Ok(
        PlanContext(
            project_root=project_root,
            records=records_result.danger_ok,
            store=payload_store,
        )
    )


def resolve_plan_bytes(
    context: PlanContext, plan_ref: str
) -> Result[tuple[bytes, str], PlanResolutionError]:
    """Read the extern-referenced plan file's bytes off disk (relative
    to the project root, the same posture `import(path)`/`by extern`
    linkage resolves against elsewhere) and stage them into the
    payload store, returning `(bytes, digest)`. An unreadable ref is a
    named `PlanResolutionError`, never an exception.
    """
    path = context.project_root / plan_ref
    try:
        data = path.read_bytes()
    except OSError as exc:
        return Err(
            PlanResolutionError(
                reason="plan_ref_unreadable",
                detail=f"{path}: {exc}",
            )
        )
    if context.store is None:
        return Err(
            PlanResolutionError(
                reason="plan_payload_store_missing",
                detail="no payload store is configured for this build",
            )
        )
    digest = context.store.put(data)
    context.consumed_pins[f"extern({plan_ref})"] = digest
    _log.debug("plan_staging: staged plan ref=%s digest=%s", plan_ref, digest)
    return Ok((data, digest))


def stage_record(
    context: PlanContext, key: str, record: MachineRecord | ToolRecord | StockTarget
) -> str | None:
    """Stage a resolved `machine`/`tool`/`stock_target` record's JSON
    body into the payload store (the `table`-kind port a `std.cam`
    model resolves, same `table` kind `std.cost`'s staged docs already
    use); record the INV-22 pin. Returns `None` when no store is
    configured for this build.
    """
    if context.store is None:
        return None
    data = record.model_dump_json().encode("utf-8")
    digest = context.store.put(data)
    context.consumed_pins[key] = context.digest_of(key) or digest
    return digest


def record_pins(context: PlanContext) -> tuple[tuple[str, str], ...]:
    """The INV-22 lockfile pins for every consumed record/plan ref,
    sorted (mirrors `costing.record_pins` exactly)."""
    return tuple(sorted(context.consumed_pins.items()))
