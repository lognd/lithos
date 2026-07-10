"""std.cam's input record shapes (WO-67 deliverable 1's data half).

WO-66 (`std.machines`/`std.tooling`, toolchain/32 sec. 2) is a SOFT
dependency that has not landed (its Status is `todo` as of this WO's
dispatch). Per the WO-67 dispatch note, this module defines FIXTURE
record shapes that MIRROR the charter's described fields (travel/
kinematics/spindle-or-nozzle for machines; diameter/flutes/stickout
for tooling) so `std.cam`'s models have something typed to consume
now. Swap-to-stdlib-refs is tracked as a follow-up (see this WO's
close-out ledger entry) -- when WO-66 lands, these fixture shapes
should be reconciled with (or replaced by) the real loader records
rather than kept as a second parallel shape (NO DUPLICATION).

Also defines the fixture "target" shape :class:`StockTarget` standing
in for a resolved `RealizedGeometry` + `FeatureProgram` pair: a
declared stock envelope, a per-feature nominal + tolerance volume, and
a bounding-box travel envelope. Full RealizedGeometry/FeatureProgram
consumption (the `_schema.models` FFI types) is cut from v1 for the
same reason -- see the close-out ledger.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Aabb(BaseModel):
    """An axis-aligned bounding box in machine/part coordinates."""

    model_config = ConfigDict(frozen=True)

    x_min: float
    x_max: float
    y_min: float
    y_max: float
    z_min: float
    z_max: float

    def contains_point(self, x: float, y: float, z: float) -> bool:
        """True iff the point lies within this box (inclusive bounds)."""
        return (
            self.x_min <= x <= self.x_max
            and self.y_min <= y <= self.y_max
            and self.z_min <= z <= self.z_max
        )


class MachineRecord(BaseModel):
    """Machine travel/kinematics/spindle-or-nozzle envelope (std.machines shape).

    ``kind`` distinguishes a 3-axis mill from an FDM printer -- the
    charter's dialect-to-machine-class pairing (fanuc -> mill,
    marlin -> printer). ``travel`` is the machine-frame envelope every
    commanded position must stay within (`cam.envelope`'s subject).
    """

    model_config = ConfigDict(frozen=True)

    name: str
    kind: str  # "mill_3axis" | "fdm_printer"
    travel: Aabb
    max_feed_mm_min: float
    source: str  # citation (sourcing law, toolchain/32 sec. 1)


class ToolRecord(BaseModel):
    """Tool geometry (std.tooling shape): diameter/flutes/stickout."""

    model_config = ConfigDict(frozen=True)

    tool_id: int
    diameter_mm: float
    flutes: int
    stickout_mm: float
    source: str


class FeatureTarget(BaseModel):
    """One FeatureProgram-machined feature, in fixture form for coverage.

    ``touch_zone`` is the AABB a cutting move must pass through for the
    feature to count as covered (a conservative stand-in for a real
    swept-volume intersection against the RealizedGeometry, which is
    the WO's cut -- see the close-out ledger note on `cam.coverage`).
    """

    model_config = ConfigDict(frozen=True)

    name: str
    kind: str
    touch_zone: Aabb


class StockTarget(BaseModel):
    """Fixture stand-in for a resolved target: stock block + tolerance +
    the FeatureProgram's machined features.

    ``geometry_digest`` stands in for the RealizedGeometry content hash
    the real evidence would cite (AD-25); here it is any caller-supplied
    stable string, since no realizer runs in this fixture path.
    ``margin_mm`` is the design margin the target commits to holding
    (undercut/overcut budget) -- the conservative-honesty test in
    `tests/harness/test_cam_removal.py` uses this to prove a resolution
    finer than the margin is required before a removal claim can be
    Valid (charter D3/acceptance-shape "conservative honesty").
    """

    model_config = ConfigDict(frozen=True)

    geometry_digest: str
    stock: Aabb
    finished: Aabb
    margin_mm: float
    features: tuple[FeatureTarget, ...] = ()
