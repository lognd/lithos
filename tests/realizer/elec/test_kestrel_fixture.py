"""End-to-end bind -> netlist -> (faked) layout DRC fixture (WO-24 acceptance 1).

Uses the simplest Kestrel board shape (`examples/cubesat/kestrel.cupr`
composes `obc: ObcPcb` and `adcs: AdcsPcb`, each an MCU + passives
board -- the WO says "pick the simplest Kestrel board there"): this
fixture binds an OBC-shaped MCU block against a small inline registry
of stm32g0/atsamd21-style candidates, emits a netlist, and runs the
layout DRC model against a FAKED clean DRC report.

Scope note (see `docs/implementation/work-orders/WO-24-PLAN.md`): the bridge from
a real lowered `.cupr` build to this fixture's `BlockRequirement`/
`ComponentCandidate` inputs does not exist yet (cut, orchestrator/
WO-19-WO-26 territory); this exercises the WO-24 realizer ENGINE
end-to-end on a hand-built, registry-shaped input. The real
`.kicad_pcb` placement/routing step is the KiCad-unavailable cut
(`regolith.realizer.elec.kicad` module docstring); DRC-clean here is a
fake wire response through the same `run_layout` code path a real
`kicad-cli` wrapper would answer.
"""

from __future__ import annotations

from regolith.harness.model import DischargeRequest
from regolith.harness.quantity import Interval
from regolith.realizer.elec.binding import (
    BlockRequirement,
    Budget,
    ComponentCandidate,
    bind_all,
)
from regolith.realizer.elec.kicad import (
    VIOLATION_COUNT,
    LayoutDrcModel,
    LayoutRequest,
    run_layout,
)
from regolith.realizer.elec.netlist import Component, Net, NetlistModel, Pin, emit


def _requirements() -> list[BlockRequirement]:
    return [
        BlockRequirement(block="obc_mcu", min_capabilities={"gpio": 20, "ram_kb": 32}),
        BlockRequirement(block="adcs_mcu", min_capabilities={"gpio": 12, "ram_kb": 16}),
    ]


def _candidates() -> dict[str, list[ComponentCandidate]]:
    return {
        "obc_mcu": [
            ComponentCandidate(
                record_key="mcu/stm32g0@1",
                content_hash="sha256:" + "a" * 64,
                capabilities={"gpio": 26, "ram_kb": 36, "power_mw": 45},
                cost=1,
            ),
        ],
        "adcs_mcu": [
            ComponentCandidate(
                record_key="mcu/atsamd21@1",
                content_hash="sha256:" + "b" * 64,
                capabilities={"gpio": 20, "ram_kb": 32, "power_mw": 35},
                cost=1,
            ),
        ],
    }


def _budgets() -> list[Budget]:
    # Kestrel's own reserve (kestrel.cupr `reserves: power: 150mW avg`),
    # scaled down for this fixture to a value both boards fit under.
    return [Budget(capability="power_mw", limit=100)]


def _netlist(record_of: dict[str, str]) -> NetlistModel:
    return NetlistModel(
        components=(
            Component(
                ref="U_OBC", record_key=record_of["obc_mcu"], footprint="LQFP:LQFP-32"
            ),
            Component(
                ref="U_ADCS", record_key=record_of["adcs_mcu"], footprint="QFN:QFN-32"
            ),
        ),
        nets=(
            Net(
                name="VDD_3V3",
                pins=(Pin(component="U_OBC", pin="VDD", is_driver=True),),
            ),
            Net(
                name="I2C_SCL",
                pins=(
                    Pin(component="U_OBC", pin="PB6", is_driver=True),
                    Pin(component="U_ADCS", pin="PA22", is_driver=False),
                ),
            ),
        ),
    )


def _run_once() -> tuple[dict[str, str], str, str]:
    """One full bind -> netlist -> hash pass; returns (pins, text, hash)."""
    bound = bind_all(_requirements(), _candidates(), _budgets())
    assert bound.is_ok, bound.danger_err
    record_of = {p.block: p.record_key for p in bound.danger_ok.pins}
    emitted = emit(_netlist(record_of))
    assert emitted.is_ok, emitted.danger_err
    text, digest = emitted.danger_ok
    return record_of, text, digest


def test_kestrel_bind_and_netlist_pick_expected_records() -> None:
    record_of, _text, digest = _run_once()
    assert record_of["obc_mcu"] == "mcu/stm32g0@1"
    assert record_of["adcs_mcu"] == "mcu/atsamd21@1"
    assert digest.startswith("sha256:")


def test_kestrel_rerun_is_a_no_op_cache_hit() -> None:
    """Re-running with unchanged inputs reproduces byte-identical artifacts.

    Stands in for "re-running with an unchanged lockfile is a no-op":
    every artifact this WO can produce without KiCad (bindings,
    netlist text, content hash) is content-addressed and deterministic,
    so a second run is indistinguishable from a cache hit.
    """
    first = _run_once()
    second = _run_once()
    assert first == second


def test_kestrel_layout_drc_clean_via_faked_kicad_wire() -> None:
    """DRC-clean discharge through the real code path, faked wire response.

    Documents the cut plainly: this proves the DRC-evidence mapping
    logic, not a real KiCad routing run (unavailable in this sandbox).
    """
    import json
    import subprocess

    def fake_runner(argv, input, capture_output, timeout, check):  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(
            args=argv,
            returncode=0,
            stdout=json.dumps(
                {
                    "status": "routed",
                    "pcb_path": "/tmp/kestrel_obc.kicad_pcb",
                    "pcb_sha256": "sha256:" + "c" * 64,
                    "drc": {"violations": []},
                }
            ).encode("ascii"),
            stderr=b"",
        )

    request = LayoutRequest(
        netlist_path="/tmp/kestrel_obc.net",
        board_outline_path="/tmp/kestrel_pc104.dxf",
        output_pcb_path="/tmp/kestrel_obc.kicad_pcb",
    )
    layout = run_layout(("kicad-layout-wrapper",), request, runner=fake_runner)
    assert layout.is_ok
    response = layout.danger_ok
    assert response.status == "routed"
    assert response.drc.clean

    model = LayoutDrcModel()
    discharge_request = DischargeRequest(
        claim_kind="elec.layout.drc_clean",
        limit=0.5,
        inputs={VIOLATION_COUNT: Interval.point(float(response.drc.error_count))},
    )
    evidence = model.discharge(discharge_request, registry_version="test")
    assert evidence.is_ok
    assert evidence.danger_ok.status.value == "discharged"
