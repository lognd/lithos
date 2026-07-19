"""Direct unit coverage for `section_inertia_m4`, the pure rectangular
second-moment-of-area helper in `orchestrator/optimize_sketch.py`, flagged
by `frob check` (TEST001) with no existing test naming it directly (W2a
frob-adoption sweep).
"""

from __future__ import annotations

from regolith.orchestrator.optimize_sketch import section_inertia_m4


# frob:tests python/regolith/orchestrator/optimize_sketch.py::section_inertia_m4
def test_section_inertia_m4_matches_rectangular_formula() -> None:
    """`I = t * b**3 / 12` for the documented (thickness, width) orientation."""
    thickness_m = 0.01
    width_m = 0.05
    expected = thickness_m * width_m**3 / 12.0
    assert section_inertia_m4(thickness_m, width_m) == expected
    # doubling the bending-axis width scales inertia by 8x (cubic term)
    assert section_inertia_m4(thickness_m, 2 * width_m) == 8 * expected
