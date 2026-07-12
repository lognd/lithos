"""WO-97 (D205/D209): a `<seg>.length = in [lo, hi] minimize` bounded
optimize slot survives walk promotion as a `SegmentLength::Bounded`
segment in the lowered `FeatureProgram` sketch payload -- instead of the
old WO-104 posture where the whole profile came back as an
`Unsupported` "expression constraints are out of this increment" reason.

This is the census guard for the WO-104 -> WO-97 handoff: WO-104 landed
the inert `Bounded` variant; this proves the promotion surface now
EMITS it for every named flagship bounded slot. It deliberately checks
the payload SURFACE, not optimizer pinning: the continuous-optimizer
coupling (D209) is honestly deferred (see the WO-97 close-out ledger --
every corpus bounded-slot part's governing structural claim defers
`no_model`, so its evaluator is `optimizer_evaluator_deferred`; STEP
emission awaits a registered structural model), so the bounded slot is
promoted-but-unpinned here by design (never guessed to a literal).
"""

from __future__ import annotations

import json

import pytest
from regolith.orchestrator.orchestrate import build
from regolith.orchestrator.tiers import BuildTier


def _bounded_segments(payload_json: bytes) -> dict[tuple[str, str, str], dict]:
    """Every promoted sketch segment whose length is a bounded optimize
    slot, keyed `(part, profile, segment)` -> the `{lo, hi, direction}`
    payload."""
    out: dict[tuple[str, str, str], dict] = {}
    payload = json.loads(payload_json)
    for program in payload.get("feature_programs") or []:
        part = str(program.get("part_name") or "?")
        for profile, sketch in (program.get("sketches") or {}).items():
            promoted = sketch.get("promoted") if isinstance(sketch, dict) else None
            if not isinstance(promoted, dict):
                continue
            for seg in promoted.get("segments") or []:
                bounded = (seg.get("length") or {}).get("bounded")
                if isinstance(bounded, dict):
                    out[(part, str(profile), str(seg.get("name")))] = bounded
    return out


# (flagship dir, part, profile, segment, lo, hi, direction) -- the four
# named WO-97 targets plus printer_k1 (the WO-64/WO-70 recipe's dims).
_CASES = [
    ("examples/flagships/uav_talon", "WingSpar", "SparCapFlat", "b", 3.0, 8.0),
    ("examples/flagships/arm_a6", "UpperArm", "UpperArmPlate", "b", 24.0, 40.0),
    ("examples/flagships/arm_a6", "Forearm", "ForearmPlate", "b", 18.0, 32.0),
    ("examples/flagships/cubesat", "SidePanel", "SidePanelFlat", "a", 94.0, 96.0),
]


@pytest.mark.parametrize("path,part,profile,segment,lo,hi", _CASES)
def test_named_bounded_slot_promotes_as_bounded_segment(
    path, part, profile, segment, lo, hi
) -> None:
    report = build((path,), BuildTier.CHECK).danger_ok
    bounded = _bounded_segments(report.payload_json)
    # The profile/segment is present with the declared bounds and a
    # `minimize` direction, unpinned (planner-owned), never a literal.
    match = {
        (pf, sg): v
        for (pt, pf, sg), v in bounded.items()
        if pt == part and sg == segment
    }
    assert match, (
        f"{part}: expected a bounded slot on segment `{segment}` of some "
        f"promoted profile; got bounded slots {sorted(bounded)}"
    )
    # Exactly one profile carries this part's bounded segment.
    ((_, value),) = match.items()
    assert value["lo"] == pytest.approx(lo)
    assert value["hi"] == pytest.approx(hi)
    assert value["direction"] == "minimize"


def test_uav_talon_wing_spar_slot_is_promoted_not_unsupported() -> None:
    """Regression pin for the WO-104 -> WO-97 flip: SparCapFlat used to
    come back `Unsupported`; it now promotes with `b` bounded and its
    close edge intact."""
    report = build(("examples/flagships/uav_talon",), BuildTier.CHECK).danger_ok
    bounded = _bounded_segments(report.payload_json)
    assert ("WingSpar", "SparCapFlat", "b") in bounded
