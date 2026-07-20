"""Tests for the `power_oneline` one-line diagram track (WO-137,
F-WO137-1, T-0064): the `power_oneline` `DrawingModel` producer
(`regolith.backends.drawings.producers.power_oneline`) and its
`PowerOnelineBackend` (svg + json emission, WO-160/AD-45
`tier="deterministic"`).

The fixture-driving test below hand-builds a `PowerNetPayload` that
mirrors `examples/flagships/factory_p1/power.cupr`'s real `PlantMain`
net VERBATIM (same bus ids/voltages/phases, same branch ids/kinds/
ratings, same load ids/kva/motor fields) rather than sourcing it
through a live `staged_build` compile: `regolith-api::BuildPayload`
carries no `power_nets` field yet (crates-side wiring for F-WO137-1 is
a separate, in-flight ticket -- `grep`-confirmed absent from
`crates/regolith-api/src/session.rs` and the `regolith._core` PyO3
surface at the time this test was written), so there is no
`report.realized_inputs`/`report.final.payload_json` channel a
Python-side test could read a real compiled `PowerNetPayload` from
today. This fixture is therefore the closest honest proxy available:
every value below is copied from the real `.cupr` declaration, not
invented.
"""

from __future__ import annotations

from regolith._schema.models import (
    Apparatus,
    Apparatus1,
    Apparatus2,
    Apparatus3,
    Branch,
    BranchKind1,
    BranchKind2,
    BranchKind3,
    BranchKind4,
    BranchKind5,
    BranchKind6,
    BranchParams1,
    BranchParams2,
    BranchParams3,
    BranchParams4,
    Bus,
    Load,
    MotorFields,
    PowerNetPayload,
    RecordRef,
    ScalarInterval,
    StandardFamily2,
)
from regolith.backends.artifacts import NativeArtifactStore
from regolith.backends.drawings.producers import power_oneline
from regolith.backends.drawings.renderer import render_svg
from regolith.backends.framework import BackendInputs
from regolith.backends.power_oneline import PowerOnelineBackend
from regolith.orchestrator.lockfile import Lockfile


# frob:ticket T-0064
def _interval(lo: float, hi: float, unit: str) -> ScalarInterval:
    return ScalarInterval(lo=lo, hi=hi, unit=unit)


# frob:ticket T-0064
def _factory_p1_power_net() -> PowerNetPayload:
    """`PlantMain` (`examples/flagships/factory_p1/power.cupr`),
    transcribed field-for-field: 6 buses, 13 branches (one of every
    `BranchKind`/params shape the schema declares), 3 loads (two
    motors, one lighting)."""
    buses = [
        Bus(id="MainSvc", nominal_voltage=_interval(13200, 13200, "V"), phases=3),
        Bus(id="Genset", nominal_voltage=_interval(480, 480, "V"), phases=3),
        Bus(id="Tie", nominal_voltage=_interval(13200, 13200, "V"), phases=3),
        Bus(id="MainBus", nominal_voltage=_interval(480, 480, "V"), phases=3),
        Bus(id="PanelA", nominal_voltage=_interval(480, 480, "V"), phases=3),
        Bus(id="MccA", nominal_voltage=_interval(480, 480, "V"), phases=3),
    ]
    branches = [
        Branch(
            id="svc",
            a="MainSvc",
            b="Tie",
            kind=BranchKind1.service,
            params=BranchParams1(
                apparatus=Apparatus.source,
                voltage=_interval(13200, 13200, "V"),
                available_fault_current=_interval(25000, 25000, "A"),
                x_over_r=_interval(6.6, 6.6, "1"),
            ),
        ),
        Branch(
            id="gen",
            a="Genset",
            b="Tie",
            kind=BranchKind2.generator,
            params=BranchParams1(
                apparatus=Apparatus.source, voltage=_interval(480, 480, "V")
            ),
        ),
        Branch(
            id="main_bkr",
            a="Tie",
            b="MainBus",
            kind=BranchKind6.protective_device,
            params=BranchParams4(
                apparatus=Apparatus3.protective_device,
                frame=_interval(2000, 2000, "A"),
                interrupting_rating=_interval(65000, 65000, "A"),
            ),
        ),
        Branch(
            id="xfmr_feed",
            a="MainBus",
            b="MainBus",
            kind=BranchKind3.transformer,
            params=BranchParams2(
                apparatus=Apparatus1.transformer,
                kva=_interval(1000, 1000, "kVA"),
                pct_z=_interval(5.75, 5.75, "1"),
                taps=[],
            ),
        ),
        Branch(
            id="panel_feed",
            a="MainBus",
            b="PanelA",
            kind=BranchKind4.feeder,
            params=BranchParams3(
                apparatus=Apparatus2.feeder,
                conductor=RecordRef(digest="fake:cu_4_0awg", name="cu_4_0awg"),
                length=_interval(45, 45, "m"),
                standard_family=StandardFamily2.nec,
            ),
        ),
        Branch(
            id="panel_bkr",
            a="PanelA",
            b="PanelA",
            kind=BranchKind6.protective_device,
            params=BranchParams4(
                apparatus=Apparatus3.protective_device,
                frame=_interval(225, 225, "A"),
                interrupting_rating=_interval(25000, 25000, "A"),
            ),
        ),
        Branch(
            id="light_feed",
            a="PanelA",
            b="LightingLoad",
            kind=BranchKind4.feeder,
            params=BranchParams3(
                apparatus=Apparatus2.feeder,
                conductor=RecordRef(digest="fake:cu_10awg", name="cu_10awg"),
                length=_interval(20, 20, "m"),
            ),
        ),
        Branch(
            id="mcc_bus",
            a="MainBus",
            b="MccA",
            kind=BranchKind5.busway,
            params=BranchParams3(
                apparatus=Apparatus2.feeder,
                conductor=RecordRef(digest="fake:cu_4_0awg", name="cu_4_0awg"),
                length=_interval(15, 15, "m"),
            ),
        ),
        Branch(
            id="mcc_fuse",
            a="MccA",
            b="MccA",
            kind=BranchKind6.protective_device,
            params=BranchParams4(
                apparatus=Apparatus3.protective_device,
                frame=_interval(800, 800, "A"),
                interrupting_rating=_interval(100000, 100000, "A"),
            ),
        ),
        Branch(
            id="press_feed",
            a="MccA",
            b="PressMotor",
            kind=BranchKind4.feeder,
            params=BranchParams3(
                apparatus=Apparatus2.feeder,
                conductor=RecordRef(digest="fake:cu_2_0awg", name="cu_2_0awg"),
                length=_interval(30, 30, "m"),
            ),
        ),
        Branch(
            id="press_relay",
            a="PressMotor",
            b="PressMotor",
            kind=BranchKind6.protective_device,
            params=BranchParams4(
                apparatus=Apparatus3.protective_device, frame=_interval(100, 100, "A")
            ),
        ),
        Branch(
            id="conv_feed",
            a="MccA",
            b="ConveyorMotor",
            kind=BranchKind4.feeder,
            params=BranchParams3(
                apparatus=Apparatus2.feeder,
                conductor=RecordRef(digest="fake:cu_6awg", name="cu_6awg"),
                length=_interval(25, 25, "m"),
            ),
        ),
        Branch(
            id="conv_fuse",
            a="ConveyorMotor",
            b="ConveyorMotor",
            kind=BranchKind6.protective_device,
            params=BranchParams4(
                apparatus=Apparatus3.protective_device,
                frame=_interval(60, 60, "A"),
                interrupting_rating=_interval(25000, 25000, "A"),
            ),
        ),
    ]
    loads = [
        Load(
            id="PressMotor",
            bus="MccA",
            connected_kva=_interval(45, 45, "kVA"),
            continuous=True,
            **{"class": "motor"},
            motor=MotorFields(hp_kw=_interval(37, 37, "kW"), code_letter="G"),
        ),
        Load(
            id="ConveyorMotor",
            bus="MccA",
            connected_kva=_interval(15, 15, "kVA"),
            continuous=True,
            **{"class": "motor"},
            motor=MotorFields(hp_kw=_interval(11, 11, "kW"), code_letter="F"),
        ),
        Load(
            id="LightingLoad",
            bus="PanelA",
            connected_kva=_interval(20, 20, "kVA"),
            continuous=False,
            **{"class": "lighting"},
        ),
    ]
    return PowerNetPayload(branches=branches, buses=buses, loads=loads)


# frob:ticket T-0064
# frob:tests python/regolith/backends/drawings/producers.py::power_oneline kind="unit"
def test_deterministic_bytes_x2() -> None:
    """Projecting + rendering the same payload twice yields byte-
    identical `DrawingModel` JSON and SVG (D165 "mechanical, not
    aesthetic" -- no solver, no hidden clock/RNG)."""
    power = _factory_p1_power_net()
    model_a = power_oneline("PlantMain", power)
    model_b = power_oneline("PlantMain", power)
    assert model_a.model_dump_json(by_alias=True) == model_b.model_dump_json(
        by_alias=True
    )
    assert render_svg(model_a) == render_svg(model_b)


# frob:ticket T-0064
# frob:tests python/regolith/backends/drawings/producers.py::power_oneline kind="unit"
def test_key_labels_present() -> None:
    """Bus name/voltage/phases, branch apparatus/rating, and load kva/
    motor-marker labels all land in the rendered svg text."""
    power = _factory_p1_power_net()
    model = power_oneline("PlantMain", power)
    svg = render_svg(model).decode("utf-8")

    # Bus identity + nominal voltage/phases (INV-34: via DimensionedValue).
    assert "MainBus" in svg
    assert "480 V" in svg
    assert "3ph" in svg
    assert "13200 V" in svg

    # Branch apparatus kind + a key rating.
    assert "transformer" in svg
    assert "kVA=1000 kVA" in svg
    assert "protective_device" in svg
    assert "frame=2000 A" in svg

    # Load connected kva + motor marker.
    assert "PressMotor" in svg
    assert "45 kVA" in svg
    assert "M(37 kW)" in svg
    assert "LightingLoad" in svg


# frob:ticket T-0064
# frob:tests python/regolith/backends/drawings/producers.py::power_oneline kind="unit"
def test_bus_without_loads_omits_terminal() -> None:
    """A bus with no declared load (e.g. `MainSvc`) contributes no
    terminal symbol/annotation -- never a fabricated placeholder load."""
    power = _factory_p1_power_net()
    model = power_oneline("PlantMain", power)
    sheet = model.sheets[0]
    # `MainSvc` gets exactly ONE annotation (its own bus label); a bus
    # carrying a terminal load would additionally get a "<id> <kva> kVA"
    # load annotation sharing the same leading id.
    matches = [a.text for a in sheet.annotations if a.text.startswith("MainSvc")]
    assert matches == ["MainSvc  13200 V  3ph"]


# frob:ticket T-0064
# frob:tests python/regolith/backends/drawings/producers.py::power_oneline kind="unit"
def test_branch_kind_source_label() -> None:
    """A `service` branch (`BranchParams1`) labels its declared voltage/
    fault current/x-over-r, honestly omitting an undeclared field."""
    power = PowerNetPayload(
        buses=[
            Bus(id="A", nominal_voltage=_interval(120, 120, "V"), phases=1),
            Bus(id="B", nominal_voltage=_interval(120, 120, "V"), phases=1),
        ],
        branches=[
            Branch(
                id="svc",
                a="A",
                b="B",
                kind=BranchKind1.service,
                params=BranchParams1(apparatus=Apparatus.source),
            )
        ],
        loads=[],
    )
    model = power_oneline("edge_source", power)
    texts = [a.text for a in model.sheets[0].annotations]
    assert any(t == "svc (service): apparatus=source" for t in texts)


# frob:ticket T-0064
# frob:tests python/regolith/backends/drawings/producers.py::power_oneline kind="unit"
def test_branch_kind_feeder_label() -> None:
    """A `feeder` branch (`BranchParams3`) labels its declared length."""
    power = PowerNetPayload(
        buses=[
            Bus(id="A", nominal_voltage=_interval(480, 480, "V"), phases=3),
            Bus(id="B", nominal_voltage=_interval(480, 480, "V"), phases=3),
        ],
        branches=[
            Branch(
                id="f1",
                a="A",
                b="B",
                kind=BranchKind4.feeder,
                params=BranchParams3(
                    apparatus=Apparatus2.feeder,
                    conductor=RecordRef(digest="fake:d", name="n"),
                    length=_interval(10, 10, "m"),
                ),
            )
        ],
        loads=[],
    )
    model = power_oneline("edge_feeder", power)
    texts = [a.text for a in model.sheets[0].annotations]
    assert any("L=10 m" in t for t in texts)


# frob:ticket T-0064
# frob:tests python/regolith/backends/drawings/producers.py::power_oneline kind="unit"
def test_load_without_motor_has_no_marker() -> None:
    """A non-motor load never carries the `M(...)` marker (honest
    absence, not a zero-filled motor block)."""
    power = PowerNetPayload(
        buses=[Bus(id="A", nominal_voltage=_interval(480, 480, "V"), phases=3)],
        branches=[],
        loads=[
            Load(
                id="L1",
                bus="A",
                connected_kva=_interval(5, 5, "kVA"),
                continuous=False,
            )
        ],
    )
    model = power_oneline("edge_load", power)
    texts = [a.text for a in model.sheets[0].annotations]
    assert any(t.startswith("L1 5 kVA") for t in texts)
    assert not any("M(" in t for t in texts)


# frob:ticket T-0064
def _inputs(tmp_path, subject: str, power: PowerNetPayload | None) -> BackendInputs:  # noqa: ANN001
    return BackendInputs(
        lockfile=Lockfile(tool_version="test"),
        evidence={},
        geometry={},
        layouts={},
        native=NativeArtifactStore(str(tmp_path)),
        power_nets={} if power is None else {subject: power},
    )


# frob:ticket T-0064
# frob:tests python/regolith/backends/power_oneline.py::PowerOnelineBackend.produce kind="unit"
def test_backend_missing_power_net_refuses(tmp_path) -> None:  # noqa: ANN001
    inputs = _inputs(tmp_path, "PlantMain", None)
    result = PowerOnelineBackend("PlantMain").produce(inputs)
    assert result.is_err
    assert result.danger_err.kind == "power_net_ir_unavailable"


# frob:ticket T-0064
# frob:tests python/regolith/backends/power_oneline.py::PowerOnelineBackend.produce kind="unit"
def test_backend_emits_svg_and_json(tmp_path) -> None:  # noqa: ANN001
    power = _factory_p1_power_net()
    inputs = _inputs(tmp_path, "PlantMain", power)
    result = PowerOnelineBackend("PlantMain").produce(inputs)
    assert result.is_ok
    files = result.danger_ok
    relpaths = {f.relpath for f in files}
    assert relpaths == {
        "power_oneline/power_oneline.svg",
        "power_oneline/power_oneline.json",
    }
    for f in files:
        assert f.provenance is not None
        assert f.provenance.tier == "deterministic"
