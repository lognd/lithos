"""Tests for `HdlBackend` (WO-102 deliverable 2).

The riscv_hart_rv1 flagship (WO-89) already discharges a real
`hdl.build` obligation through the std.hdl verilator pack against its
`pc_incr.v` source -- this is the "riscv_hart_rv1 ships an `hdl/`
family (tier report + source manifest; behavioral-tier evidence
present)" acceptance fixture the WO body names, built from the REAL
discharge, not a fake.
"""

from __future__ import annotations

import json
from pathlib import Path

from regolith.backends.artifacts import NativeArtifactStore
from regolith.backends.framework import BackendInputs
from regolith.backends.hdl import (
    HdlBackend,
    HdlBuildProducts,
    HdlSourceFile,
    HdlTierRow,
)
from regolith.backends.quantity import DimensionedValue
from regolith.orchestrator.lockfile import Lockfile

_RISCV = Path("examples/flagships/riscv_hart_rv1")


def _inputs(*, hdl: dict[str, HdlBuildProducts]) -> BackendInputs:
    return BackendInputs(
        lockfile=Lockfile(tool_version="0.1.0"),
        evidence={},
        geometry={},
        layouts={},
        native=NativeArtifactStore("/tmp/unused-hdl-native"),
        hdl=hdl,
    )


def _riscv_products() -> HdlBuildProducts:
    """The REAL `pc_incr.v` source + the discharged `hdl.build` evidence
    (WO-89), read off the actual flagship build -- no fabricated rows.
    """
    from regolith.orchestrator.orchestrate import BuildTier, build

    result = build((str(_RISCV),), BuildTier.BUILD)
    assert result.is_ok, result
    report = result.danger_ok
    payload = json.loads(report.payload_json)
    names = [ob["claim"].get("name") for ob in payload["obligations"]]
    evidence = None
    for name, res in zip(names, report.results, strict=True):
        if name == "hdl.build" and res.evidence is not None:
            evidence = res.evidence
            break
    assert evidence is not None, "expected a discharged hdl.build obligation"

    from regolith.harness.quantity import bits_to_f64

    source = (_RISCV / "pc_incr.v").read_bytes()
    return HdlBuildProducts(
        sources=(HdlSourceFile(filename="pc_incr.v", content=source),),
        tiers=(
            HdlTierRow(
                claim="hdl.build",
                status=evidence.status.value,
                model_id=evidence.model_id,
                value=DimensionedValue.dimensionless(bits_to_f64(evidence.value_bits)),
                margin=DimensionedValue.dimensionless(
                    bits_to_f64(evidence.margin_bits)
                ),
                tool="verilator",
                tool_version=evidence.model_id.split("verilator", 1)[-1],
            ),
        ),
    )


def test_hdl_backend_ships_riscv_source_and_tier_report() -> None:
    products = _riscv_products()
    inputs = _inputs(hdl={"riscv_hart_rv1": products})

    produced = HdlBackend().produce(inputs)
    assert produced.is_ok, produced
    files = {f.relpath: f for f in produced.danger_ok}

    assert (
        files["hdl/riscv_hart_rv1/src/pc_incr.v"].content
        == (_RISCV / "pc_incr.v").read_bytes()
    )
    manifest = json.loads(files["hdl/riscv_hart_rv1/source_manifest.json"].content)
    assert manifest["sources"][0]["filename"] == "pc_incr.v"

    tiers = json.loads(files["hdl/riscv_hart_rv1/tier_report.json"].content)
    row = tiers["tiers"][0]
    assert row["claim"] == "hdl.build"
    assert row["status"] == "discharged"
    # Behavioral-tier evidence present, not fabricated: it round-trips
    # exactly what the real WO-89 discharge produced.
    assert "verilator" in row["model_id"]

    # No synthesis tier ever ran (no such model exists in std.hdl) --
    # a named absence, never an invented netlist.
    assert tiers["netlist"]["present"] is False
    assert "no synthesis-to-netlist model" in tiers["netlist"]["reason"]
    assert not any(p.endswith(("netlist.v", ".vh")) for p in files)


def test_hdl_backend_absent_tier_named_not_crash() -> None:
    """A subject with only `hdl.build` evidence names `hdl.sim_assert`/
    `hdl.equiv_directed` as absent-with-reason, never a crash."""
    products = HdlBuildProducts(
        sources=(
            HdlSourceFile(filename="core.v", content=b"module core; endmodule\n"),
        ),
        tiers=(
            HdlTierRow(
                claim="hdl.build",
                status="discharged",
                model_id="hdl_build@1+verilator5.047",
                value=DimensionedValue.dimensionless(0.0),
                margin=DimensionedValue.dimensionless(0.0),
                tool="verilator",
                tool_version="5.047",
            ),
        ),
    )
    inputs = _inputs(hdl={"toy_core": products})
    produced = HdlBackend().produce(inputs)
    assert produced.is_ok, produced
    files = {f.relpath: f for f in produced.danger_ok}
    tiers = json.loads(files["hdl/toy_core/tier_report.json"].content)
    absent_claims = {row["claim"] for row in tiers["absent_tiers"]}
    assert absent_claims == {"hdl.sim_assert", "hdl.equiv_directed"}
    for row in tiers["absent_tiers"]:
        assert row["reason"]


def test_hdl_backend_legitimate_netlist_ships_when_supplied() -> None:
    products = HdlBuildProducts(
        sources=(),
        tiers=(),
        netlist=b"module gate_level; endmodule\n",
        netlist_filename="core_netlist.v",
    )
    inputs = _inputs(hdl={"toy_core": products})
    produced = HdlBackend().produce(inputs)
    assert produced.is_ok
    files = {f.relpath: f for f in produced.danger_ok}
    assert (
        files["hdl/toy_core/core_netlist.v"].content
        == b"module gate_level; endmodule\n"
    )
    tiers = json.loads(files["hdl/toy_core/tier_report.json"].content)
    assert tiers["netlist"]["present"] is True


def test_hdl_backend_no_subjects_ships_nothing() -> None:
    produced = HdlBackend().produce(_inputs(hdl={}))
    assert produced.is_ok
    assert produced.danger_ok == ()
