"""Netlist emission: arbitration checks + KiCad writer (WO-24 deliverable 2)."""

from __future__ import annotations

from regolith.realizer.elec.netlist import (
    Component,
    Net,
    NetlistModel,
    Pin,
    check_single_driver,
    emit,
    to_kicad_netlist,
)


def _simple_model() -> NetlistModel:
    return NetlistModel(
        components=(
            Component(ref="U1", record_key="mcu/stm32g0@1", footprint="LQFP:LQFP-32"),
            Component(ref="R1", record_key="passive/10k@1", footprint="R:R_0402"),
        ),
        nets=(
            Net(name="VDD", pins=(Pin(component="U1", pin="1", is_driver=True),)),
            Net(
                name="NET1",
                pins=(
                    Pin(component="U1", pin="2", is_driver=True),
                    Pin(component="R1", pin="1", is_driver=False),
                ),
            ),
        ),
    )


def test_single_driver_check_passes_clean_design() -> None:
    result = check_single_driver(_simple_model())
    assert result.is_ok


def test_single_driver_check_rejects_two_drivers() -> None:
    model = NetlistModel(
        components=(Component(ref="U1", record_key="k@1", footprint="f"),),
        nets=(
            Net(
                name="CONTENDED",
                pins=(
                    Pin(component="U1", pin="1", is_driver=True),
                    Pin(component="U1", pin="2", is_driver=True),
                ),
            ),
        ),
    )
    result = check_single_driver(model)
    assert result.is_err
    assert result.danger_err.net == "CONTENDED"
    assert len(result.danger_err.drivers) == 2


def test_kicad_text_is_deterministic_and_ascii() -> None:
    model = _simple_model()
    text_a = to_kicad_netlist(model)
    text_b = to_kicad_netlist(model)
    assert text_a == text_b
    text_a.encode("ascii")  # raises if non-ASCII sneaks in
    assert "U1" in text_a and "R1" in text_a


def test_content_hash_is_stable_and_pin_shaped() -> None:
    model = _simple_model()
    h1 = model.content_hash()
    h2 = model.content_hash()
    assert h1 == h2
    assert h1.startswith("sha256:")


def test_emit_runs_arbitration_before_writing_text() -> None:
    ok = emit(_simple_model())
    assert ok.is_ok
    text, digest = ok.danger_ok
    assert digest.startswith("sha256:")
    assert "(export" in text

    bad = NetlistModel(
        components=(Component(ref="U1", record_key="k@1", footprint="f"),),
        nets=(
            Net(
                name="BAD",
                pins=(
                    Pin(component="U1", pin="1", is_driver=True),
                    Pin(component="U1", pin="2", is_driver=True),
                ),
            ),
        ),
    )
    err = emit(bad)
    assert err.is_err
