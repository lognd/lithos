"""Material-record bound resolution: `material.<prop>` entity-derived
claim bounds -> std.materials numeric properties (WO-112 Class 2, the
D103 ref-resolution residual named by F130/F131.2).

A corpus claim like `shell: peak(mech.stress.von_mises, at=...) <
material.sigma_y / 2.5` carries its bound in a MATERIAL RECORD, not a
literal: the declaring part pins `material: AL_5052_H32` (threaded by
the Rust lowering into `given.materials`), and the yield stress lives
in `std.materials`' records. Records are magnetite/Python domain
(D192/D193 -- the Rust core never reads TOML), so the bound
literalizes HERE, at the orchestrator boundary, exactly where
`frame_resolve` literalizes std.civil section refs.

One loader home (NO DUPLICATION): this module does not parse record
TOML itself -- it reuses :func:`frame_resolve.load_frame_records`,
whose `[[material]]` reader already walks every package's
`records/*.toml` under the search paths (std.materials included) and
reduces rows to SI-unit :class:`frame_resolve.MaterialProps`. This
module only adds the build-level context object (records +
consumed-pin ledger, the `CostContext`/`FrameContext` posture) and
the INV-22 pin collector.
"""

from __future__ import annotations

from typani.result import Err, Ok, Result

from regolith.errors import OrchestratorError
from regolith.logging_setup import get_logger
from regolith.orchestrator.frame_resolve import MaterialProps, load_frame_records

_log = get_logger(__name__)

#: `material.<prop>` names this resolver maps to a record field. The
#: value is a human-readable citation of the record field consumed
#: (used in deferral details so an author knows which TOML field to
#: publish). ONE home for the mapping -- translate's bound parser and
#: the tests both read it.
# frob:doc docs/modules/py-orchestrator.md#material_resolve
PROPERTY_FIELDS: dict[str, str] = {
    "sigma_y": "yield_MPa",
    "sigma_u": "ultimate_MPa",
}


# frob:doc docs/modules/py-orchestrator.md#material_resolve
class MaterialContext:
    """One build's material-record resolution state: the loaded
    `[[material]]` records (keyed by record key, e.g. `AL_5052_H32`)
    and the consumed-record pin ledger (INV-22, the
    `FrameContext.consumed_pins` shape)."""

    def __init__(
        self,
        *,
        records: dict[str, MaterialProps],
        search_paths: tuple[str, ...],
    ) -> None:
        """Bind one build's fixed material-record inputs."""
        self.records = records
        self.search_paths = search_paths
        # `std.materials.material.<key>` -> row digest (INV-22).
        self.consumed_pins: dict[str, str] = {}

    # frob:doc docs/modules/py-orchestrator.md#material_resolve
    def consume(self, props: MaterialProps) -> None:
        """Record the INV-22 pin for a record a claim bound consumed."""
        self.consumed_pins[f"std.materials.material.{props.key}"] = props.digest


# frob:doc docs/modules/py-orchestrator.md#material_resolve
def load_material_context(
    project_root: str,
    *,
    record_search_paths: tuple[str, ...] = (),
) -> Result[MaterialContext, OrchestratorError]:
    """Load this build's material-record context (always `Ok`: a build
    with no material records simply resolves nothing, and a
    `material.<prop>` bound then defers naming the missing record --
    the same honest posture as a stackup-less `si_context`).

    `record_search_paths` extends the default (the project root
    itself) with additional local package roots (`stdlib/`), exactly
    the `load_frame_context` posture -- and the same D192-resolved
    paths every CLI verb already threads.
    """
    search_paths = (project_root, *record_search_paths)
    loaded = load_frame_records(search_paths)
    if loaded.is_err:
        return Err(loaded.danger_err)
    records = loaded.danger_ok.materials
    _log.debug(
        "material context loaded: %d material record(s) from %s",
        len(records),
        list(search_paths),
    )
    return Ok(MaterialContext(records=records, search_paths=search_paths))


# frob:doc docs/modules/py-orchestrator.md#material_resolve
def material_record_pins(ctx: MaterialContext) -> tuple[tuple[str, str], ...]:
    """The INV-22 lockfile pins for every std.materials record this
    build's bound resolution consumed, sorted: ``(<key>@1, <row
    digest>)`` -- revision 1 is the stdlib loader's fixed starter
    revision, exactly the `costing.record_pins`/`frame_record_pins`
    shape (one pin grammar, three ledgers)."""
    return tuple(
        (f"{key}@1", digest) for key, digest in sorted(ctx.consumed_pins.items())
    )
