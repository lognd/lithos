"""std.dfm's input record shapes (WO-110 deliverable 1's data half).

The `mfg.manufacturable` channel's staged payload tables: a
:class:`DfmPart` derived at translate time (`orchestrator/dfm_staging.py`)
from the build's OWN emitted FeatureProgram + realized TopologySummary
(never re-measured here -- the realizer already owns geometry truth,
AD-25), plus a :class:`DfmToolSet` wrapping the SAME `[[tool]]` records
the `std.cam` pack consumes (`regolith.harness.models.cam.records.
ToolRecord`, reused verbatim -- NO DUPLICATION; the machine port
likewise reuses `MachineRecord` directly, so this module defines no
machine shape at all).

Boundary posture (charter 39 sec. 4): every value in these records is
DECLARED data (feature params spelled in source, records with in-row
`source` citations, realizer-measured topology) -- the model computes
containment/comparison arithmetic only, no process physics. Process
physics (bend radii, punch floors) stays in the WO-28 rule packs and
`mech.sheet.min_bend_radius`; this channel deliberately checks only the
envelope facts those packs do NOT own: tool fit/reach and stock/travel
fit.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from regolith.harness.models.cam.records import Aabb, ToolRecord

# One home for the process-family vocabulary this channel grounds in
# v1: 3-axis milling-class removal (the only family the existing
# `[[machine]]`/`[[tool]]` record vocabulary can ground -- see
# `orchestrator/dfm_staging.py` for the token/process maps that feed
# it and the named deferrals every other family takes).
# frob:doc docs/modules/py-harness.md#models-dfm
MILL_FAMILY = "mill"


# frob:doc docs/modules/py-harness.md#models-dfm
class DfmFeature(BaseModel):
    """One machinable feature distilled from a FeatureProgram op.

    v1 carries the `hole` kind only (the op vocabulary's scalar-
    parameterized removal feature); `dia_mm` is the spelled diameter,
    `depth_mm` the spelled depth when present, else the enclosing
    blank/plate thickness when ONE is spelled (a through hole -- the
    derivation is recorded in `provenance`), else ``None`` (reach
    unchecked for that feature, named in the model's note).
    """

    model_config = ConfigDict(frozen=True)

    name: str
    count: int
    stage: str
    process: str
    dia_mm: float
    depth_mm: float | None = None
    provenance: str = ""


# frob:doc docs/modules/py-harness.md#models-dfm
class DfmPart(BaseModel):
    """The staged `dfm_part` payload: one part's DFM-relevant facts.

    ``bbox_mm`` is the realized part's axis-aligned bounding box
    (RealizedGeometry.topology, mm); ``geometry_digest`` pins the
    RealizedGeometry payload this box was read from (AD-18 citation).
    ``claim_process`` is the `manufacturable(<token>)` token as spelled;
    ``families`` the process families of the part's stages (the
    dfm_staging maps, one home).
    """

    model_config = ConfigDict(frozen=True)

    part_name: str
    claim_process: str
    families: tuple[str, ...]
    features: tuple[DfmFeature, ...]
    bbox_mm: Aabb
    geometry_digest: str
    material: str = ""


# frob:doc docs/modules/py-harness.md#models-dfm
class DfmToolSet(BaseModel):
    """The staged `dfm_tools` payload: every `[[tool]]` record this
    build loaded, in declaration order (the model's exists-a-tool
    search is order-independent; order is kept for determinism)."""

    model_config = ConfigDict(frozen=True)

    tools: tuple[ToolRecord, ...]


__all__ = ["Aabb", "DfmFeature", "DfmPart", "DfmToolSet", "MILL_FAMILY", "ToolRecord"]
