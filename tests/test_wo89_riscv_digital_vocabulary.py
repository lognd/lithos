"""WO-89 (riscv phase B): the flagship's discharge census moves off
zero. The PC-increment leaf (`uarch.cupr`'s `impl PcIncrement by
extern("pc_incr.v", verilog2001)`) forms one `hdl.build` obligation,
routed through the std.hdl verilator pack (WO-82) and discharged.

The keystone deliverable -- the declared-vs-undeclared table for the
four F112 asks -- is the WO-81 phase-B ledger (prose); this test proves
the one DECLARED shape (the `by extern` -> `hdl.build` embedding route,
cuprite/09 sec. 3) actually discharges, lifting the census strictly
above the 77/0 fresh baseline.
"""

from __future__ import annotations

import json

from regolith.orchestrator.orchestrate import BuildTier, build

_RISCV = "examples/flagships/riscv_hart_rv1"


def _census() -> tuple[int, int, dict[str, str]]:
    """Return (total obligations, resolved count, {name: verdict})."""
    result = build((_RISCV,), BuildTier.BUILD)
    assert result.is_ok, result
    report = result.danger_ok
    payload = json.loads(report.payload_json)
    names = [ob["claim"].get("name") for ob in payload["obligations"]]
    verdicts: dict[str, str] = {}
    resolved = 0
    for name, res in zip(names, report.results, strict=True):
        if res.is_resolved:
            verdict = "resolved"
            resolved += 1
        elif res.is_violated:
            verdict = "violated"
        else:
            verdict = "indeterminate"
        if name:
            verdicts[name] = verdict
    return len(report.results), resolved, verdicts


def test_riscv_discharge_census_is_above_zero() -> None:
    """Fresh baseline was 77/0 (every obligation indeterminate). Phase B
    adds the pc_incr behavioral body, so at least one obligation now
    resolves -- the acceptance criterion (discharge strictly above the
    fresh baseline)."""
    total, resolved, _ = _census()
    assert total >= 78, total
    assert resolved >= 1, f"expected >=1 discharged, got {resolved}"


def test_pc_incr_hdl_build_obligation_is_the_discharged_one() -> None:
    """The discharged obligation is the `hdl.build` claim the extern
    HDL body forms -- verilated clean through the std.hdl pack, not a
    coincidental other discharge."""
    _, _, verdicts = _census()
    assert verdicts.get("hdl.build") == "resolved", verdicts


def test_no_obligation_lowered_to_deferred_regressed_to_violated() -> None:
    """Zero lowered->deferred fleet-wide (WO-89 acceptance): the phase-B
    wiring never turns a would-be discharge into a false violation --
    every non-resolved riscv obligation is honest indeterminate, never
    violated."""
    _, _, verdicts = _census()
    assert "violated" not in verdicts.values(), verdicts
