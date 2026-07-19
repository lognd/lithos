"""WO-78 deliverable 5: the SI table sheet (charter 35 sec. 1.5/3(d)).

Producer-level assertions follow `test_drawings.py`'s WO-50 house
style (determinism, SVG validity, attribution completeness); the
row-derivation half runs the REAL si_board build (feldspar-gated, the
WO-27 posture) and freezes the derived rows as a reviewed JSON golden
(`tests/golden/data/si_sheet_si_board.json`,
`REGOLITH_UPDATE_GOLDEN=1` to regenerate) -- the sheet is
golden-enrolled corpus data, not just unit-tested shape.
"""

from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from regolith.backends.drawings.producers import SiSheetRow, si_table
from regolith.backends.drawings.renderer import render_svg
from regolith.backends.parity import ProvenanceClass, classify_cause

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SI_BOARD = str(REPO_ROOT / "examples" / "tracks" / "cuprite" / "si_board.cupr")
_GOLDEN = REPO_ROOT / "tests" / "golden" / "data" / "si_sheet_si_board.json"

_ROWS = (
    SiSheetRow(
        claim="clk_z0.lo",
        net="clk",
        target=">= 45",
        stackup="jlc04161h_7628",
        layer="outer",
        geometry="w=0.00036",
        computed="50.1737",
        margin="4.03",
        status="discharged",
        model_id="elec_si_microstrip_z0_lo@1",
        cause="obligation(clk_z0.lo) evidence=abc123def456",
    ),
    SiSheetRow(
        claim="clk_rs",
        net="clk",
        target=">= 33",
        stackup="-",
        layer="-",
        geometry="scheme=series",
        computed="35",
        margin="2",
        status="discharged",
        model_id="elec_si_series_termination_rs@1",
        cause="obligation(clk_rs) evidence=def456abc123",
    ),
)


class TestSiTableProducer:
    # frob:tests python/regolith/backends/drawings/producers.py::si_table kind="unit"
    def test_deterministic_across_two_runs(self) -> None:
        a = si_table("SiBoard", _ROWS).model_dump_json(by_alias=True)
        b = si_table("SiBoard", _ROWS).model_dump_json(by_alias=True)
        assert a == b

    def test_svg_is_valid_xml_and_carries_the_rows(self) -> None:
        model = si_table("SiBoard", _ROWS)
        svg = render_svg(model).decode("ascii")
        root = ET.fromstring(svg)
        assert root.tag.endswith("svg")
        assert "elec_si_microstrip_z0_lo@1" in svg
        assert "jlc04161h_7628" in svg

    def test_every_row_is_attributed(self) -> None:
        """AD-27: an unattributable number on a sheet is
        unrepresentable -- every row carries model id + cause, and the
        cause classifies into a real parity provenance class."""
        model = si_table("SiBoard", _ROWS)
        table = model.sheets[0].tables[0]
        cause_col = table.columns.index("cause")
        model_col = table.columns.index("model")
        for row in table.rows:
            assert row.cells[cause_col], row
            assert row.cells[model_col], row
            cause = row.cells[cause_col]
            assert classify_cause(cause) == ProvenanceClass.derived, cause


# frob:tests python/regolith/backends/ship.py::si_rows_from_report kind="unit"
def test_si_rows_derive_from_the_real_build_and_match_the_golden() -> None:
    """The row derivation over the corpus board's own build: subject
    keyed by the declaring scope, computed values from the evidence bit
    channel, every row attributed. Frozen as a JSON golden, reviewed
    like any generated artifact."""
    pytest.importorskip(
        "feldspar",
        reason="the SI sheet's evidence-bearing rows need the pack "
        "(the WO-27 skip-if-absent posture)",
    )
    from regolith.backends.ship import si_rows_from_report
    from regolith.orchestrator.orchestrate import (
        BuildTier,
        StagedBuildReport,
        build,
    )

    stdlib = (str(REPO_ROOT / "stdlib"),)
    result = build(
        (_SI_BOARD,), BuildTier.BUILD, si_record_paths=stdlib, cost_record_paths=stdlib
    )
    assert result.is_ok, result
    report = StagedBuildReport(final=result.danger_ok, iterations=1)

    derived = si_rows_from_report(report)
    assert set(derived) == {"SiBoard"}, set(derived)
    rows = derived["SiBoard"]
    assert len(rows) == 9  # 2 + 2 impedance halves + 5 termination sizings

    by_claim = {row.claim: row for row in rows}
    z0 = by_claim["clk_z0.lo"]
    assert z0.net == "clk"
    assert z0.stackup == "jlc04161h_7628"
    assert float(z0.computed) == pytest.approx(50.17, abs=0.05)
    assert z0.status == "discharged"
    assert z0.model_id == "elec_si_microstrip_z0_lo@1"
    rs = by_claim["clk_rs"]
    assert float(rs.computed) == pytest.approx(35.0)
    for row in rows:
        assert row.cause.startswith("obligation(")
        assert classify_cause(row.cause) == ProvenanceClass.derived

    # Golden enrollment: evidence hashes are content addresses over the
    # request (stable across runs of the same source + records), so the
    # full row set freezes byte-for-byte.
    snapshot = [row.model_dump() for row in rows]
    if os.environ.get("REGOLITH_UPDATE_GOLDEN") == "1":
        _GOLDEN.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
        pytest.skip(f"REGOLITH_UPDATE_GOLDEN=1: rewrote {_GOLDEN}")
    assert _GOLDEN.exists(), (
        f"no golden at {_GOLDEN}; regenerate with REGOLITH_UPDATE_GOLDEN=1"
    )
    assert snapshot == json.loads(_GOLDEN.read_text()), (
        "SI sheet row drift -- if intended, regenerate with "
        "REGOLITH_UPDATE_GOLDEN=1 and review the diff honestly"
    )
