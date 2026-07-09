"""Component binding: allocation search (WO-24 deliverable 1).

Spec: regolith/07 sec. 7 (allocation search), D75 (nogoods stay solver
state). Covers WO-24 acceptance: "a binding that violates a budget
claim backjumps and lands on a feasible record."
"""

from __future__ import annotations

from regolith.realizer.elec.binding import (
    BlockRequirement,
    Budget,
    ComponentCandidate,
    bind_all,
)


def test_happy_bind_picks_cheapest_candidate() -> None:
    """The search prefers the cheapest satisfying candidate, deterministically."""
    requirements = [BlockRequirement(block="mcu", min_capabilities={"gpio": 4})]
    candidates = {
        "mcu": [
            ComponentCandidate(
                record_key="mcu/atsamd21@1",
                content_hash="sha256:aa",
                capabilities={"gpio": 6, "power_mw": 40},
                cost=2,
            ),
            ComponentCandidate(
                record_key="mcu/stm32g0@1",
                content_hash="sha256:bb",
                capabilities={"gpio": 8, "power_mw": 30},
                cost=1,
            ),
        ]
    }
    result = bind_all(requirements, candidates)
    assert result.is_ok
    pins = result.danger_ok.pins
    assert len(pins) == 1
    assert pins[0].record_key == "mcu/stm32g0@1"
    # WO-26 D105c: the cause names WHAT was decided, one formatter.
    assert pins[0].cause == "planner(bind mcu)"


def test_capability_screen_rejects_underpowered_candidate() -> None:
    """A candidate below the required minimum is never chosen."""
    requirements = [BlockRequirement(block="mcu", min_capabilities={"gpio": 10})]
    candidates = {
        "mcu": [
            ComponentCandidate(
                record_key="mcu/rp2040@1",
                content_hash="sha256:cc",
                capabilities={"gpio": 8},
                cost=1,
            )
        ]
    }
    result = bind_all(requirements, candidates)
    assert result.is_err
    assert result.danger_err.block == "mcu"


def test_backjump_on_rigged_nogood() -> None:
    """A budget-violating first choice backjumps to the feasible second one.

    Two blocks (`mcu`, `radio`) each have two candidates; the cheapest
    `mcu` candidate alone already saturates the power budget when
    combined with any `radio` candidate, so the search must reject it
    (recording a D75 nogood) and land on the second, higher-cost `mcu`
    candidate that fits.
    """
    requirements = [
        BlockRequirement(block="mcu", min_capabilities={}),
        BlockRequirement(block="radio", min_capabilities={}),
    ]
    candidates = {
        "mcu": [
            ComponentCandidate(
                record_key="mcu/hungry@1",
                content_hash="sha256:11",
                capabilities={"power_mw": 500},
                cost=1,
            ),
            ComponentCandidate(
                record_key="mcu/frugal@1",
                content_hash="sha256:22",
                capabilities={"power_mw": 100},
                cost=2,
            ),
        ],
        "radio": [
            ComponentCandidate(
                record_key="radio/only@1",
                content_hash="sha256:33",
                capabilities={"power_mw": 200},
                cost=1,
            ),
        ],
    }
    budgets = [Budget(capability="power_mw", limit=400)]
    result = bind_all(requirements, candidates, budgets)
    assert result.is_ok, result.danger_err
    pins = {p.block: p.record_key for p in result.danger_ok.pins}
    assert pins["mcu"] == "mcu/frugal@1"
    assert pins["radio"] == "radio/only@1"


def test_no_feasible_binding_reports_nogoods() -> None:
    """When every candidate blows the budget, the search reports the count."""
    requirements = [BlockRequirement(block="mcu", min_capabilities={})]
    candidates = {
        "mcu": [
            ComponentCandidate(
                record_key="mcu/a@1",
                content_hash="sha256:1",
                capabilities={"power_mw": 999},
            ),
            ComponentCandidate(
                record_key="mcu/b@1",
                content_hash="sha256:2",
                capabilities={"power_mw": 999},
            ),
        ]
    }
    budgets = [Budget(capability="power_mw", limit=1)]
    result = bind_all(requirements, candidates, budgets)
    assert result.is_err
    assert result.danger_err.nogoods_considered == 2
