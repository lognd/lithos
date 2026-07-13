# PROOF (GAP): bounded sketch-segment slot sized by a real margin search (WingSpar, WO-97/D209)

- optimized quantity: slot value (SparCapFlat.b)
- domain: uav_talon WingSpar bounded sketch-segment [3mm, 8mm]
- status: NOT LIVE -- the surface machinery is not yet merged
- blocked on: WO-97 D209 coupling + structural model channel (F125/F126.1)

## Why no artifact

The bounded slot promotes to a `SegmentLength::Bounded` closure (WO-97 promotion half, landed), but D209's per-candidate evaluator IS the discharge pipeline, and every bounded-slot part's governing structural claim (mech.stress.von_mises / mech.deflection) defers `no_model`: none of ['mech.stress.von_mises', 'mech.deflection'] is a registered model kind on the installed core. So no part can be pinned to a genuine optimize(...) value yet (WO-97 E1). This probe flips to the live path the moment that structural model channel + the D209 coupling land in the parallel D218.3 dispatch.

No artifact is emitted rather than a fabricated one (WO-108 rule:
an unmerged surface emits an honest gap note and exits nonzero
from `make demos-strict`). This script is already wired behind an
availability probe; it produces the real proof pack the moment
the machinery lands, with no further edit.
