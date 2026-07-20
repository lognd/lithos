"""WO-158 (T-0028): unit coverage for the E1105 cross-check mechanism
(`demos.demo22_riscv_sim_crosscheck.cross_check_expected_vs_sim`) --
proves the three verdicts (agreement, disagreement, no_overlap) are
each reachable and correctly classified, independent of the full demo
run (which drives the real pipeline + real verilator end to end and is
exercised separately by `tests/test_wo108_demos.py`)."""

from __future__ import annotations

from regolith.backends.harness_pack import ExpectedSignal

from demos.demo22_riscv_sim_crosscheck import cross_check_expected_vs_sim


# frob:ticket T-0028
def _signal(target_path: str) -> ExpectedSignal:
    """A minimal `ExpectedSignal` test fixture over `target_path`, one
    home for every test case in this file to build its input rows."""
    return ExpectedSignal(
        channel=0,
        target_path=target_path,
        kind="signal",
        quantity="signal level",
        expected="8'h11",
        units="",
        provenance={"kind": "record", "ref": "test fixture"},
    )


# frob:ticket T-0028
# frob:tests demos/demo22_riscv_sim_crosscheck.py::cross_check_expected_vs_sim kind="unit"
def test_crosscheck_agreement_when_port_matches_and_sim_clean() -> None:
    """A matching net with no recorded mismatch is `agreement`."""
    rows = cross_check_expected_vs_sim(
        (_signal("Fixture.y"),), frozenset({"y"}), frozenset()
    )
    assert rows[0].verdict == "agreement"
    assert rows[0].net == "y"


# frob:ticket T-0028
# frob:tests demos/demo22_riscv_sim_crosscheck.py::cross_check_expected_vs_sim kind="unit"
def test_crosscheck_disagreement_when_port_matches_but_mismatched() -> None:
    """A matching net with a recorded mismatch is `disagreement`."""
    rows = cross_check_expected_vs_sim(
        (_signal("Fixture.y"),), frozenset({"y"}), frozenset({"y"})
    )
    assert rows[0].verdict == "disagreement"


# frob:ticket T-0028
# frob:tests demos/demo22_riscv_sim_crosscheck.py::cross_check_expected_vs_sim kind="unit"
def test_crosscheck_no_overlap_when_port_absent() -> None:
    """A net the simulated design has no port for is `no_overlap` --
    the honest named absence (D250.3), never a fabricated agreement."""
    sim_ports = frozenset({"pc_in", "pc_next"})
    rows = cross_check_expected_vs_sim(
        (_signal("HartPackage.clk_in"),), sim_ports, frozenset()
    )
    assert rows[0].verdict == "no_overlap"
    assert rows[0].net == "clk_in"
    assert "no port named" in rows[0].detail


# frob:ticket T-0028
# frob:tests demos/demo22_riscv_sim_crosscheck.py::cross_check_expected_vs_sim kind="unit"
def test_crosscheck_classifies_every_row_independently() -> None:
    """Every expected-signal row gets its own verdict; one no_overlap row
    never masks another row's real agreement."""
    rows = cross_check_expected_vs_sim(
        (_signal("A.y"), _signal("B.clk_in")),
        frozenset({"y"}),
        frozenset(),
    )
    assert len(rows) == 2
    assert rows[0].verdict == "agreement"
    assert rows[1].verdict == "no_overlap"
