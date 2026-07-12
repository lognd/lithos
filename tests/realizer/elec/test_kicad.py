"""Layout adapter `realizer.elec.kicad` (WO-24 deliverable 3).

Real KiCad tooling is unavailable in this sandbox (verified: no
`kicad-cli` on PATH, `pcbnew` not importable -- see the module
docstring cut note in `regolith.realizer.elec.kicad`). These tests
exercise the wire protocol and outcome-mapping logic against a FAKE
subprocess runner, the same dependency-injection seam
`regolith.harness.adapter` itself is tested through.
"""

from __future__ import annotations

import json
import subprocess

from regolith.harness.model import DischargeRequest
from regolith.harness.quantity import Interval
from regolith.realizer.elec.errors import LayoutFailed, ToolUnavailable
from regolith.realizer.elec.kicad import (
    VIOLATION_COUNT,
    LayoutDrcModel,
    LayoutRequest,
    discover_kicad_cli,
    run_layout,
)


def test_discover_kicad_cli_reports_absence() -> None:
    """The gate reports closed when the tool is missing (injected absence --
    never an assertion about the host environment, which may have KiCad)."""
    assert discover_kicad_cli(which_fn=lambda name: None) is None


def test_discover_kicad_cli_uses_injected_finder() -> None:
    found = discover_kicad_cli(which_fn=lambda name: f"/usr/bin/{name}")
    assert found == "/usr/bin/kicad-cli"


def _fake_runner(stdout_obj: object, returncode: int = 0):  # type: ignore[no-untyped-def]
    def runner(argv, input, capture_output, timeout, check):  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(
            args=argv,
            returncode=returncode,
            stdout=json.dumps(stdout_obj).encode("ascii"),
            stderr=b"layout: routed ok\n",
        )

    return runner


def _request() -> LayoutRequest:
    return LayoutRequest(
        netlist_path="/tmp/x.net",
        board_outline_path="/tmp/x.dxf",
        output_pcb_path="/tmp/x.kicad_pcb",
        outline_w_mm=100.0,
        outline_d_mm=80.0,
    )


def test_run_layout_tool_unavailable_maps_to_value() -> None:
    def missing_runner(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise FileNotFoundError("no such file: kicad-layout-wrapper")

    result = run_layout(("kicad-layout-wrapper",), _request(), runner=missing_runner)
    assert result.is_err
    assert isinstance(result.danger_err, ToolUnavailable)


def test_run_layout_drc_clean_routed() -> None:
    response = {
        "status": "routed",
        "pcb_path": "/tmp/x.kicad_pcb",
        "pcb_sha256": "sha256:deadbeef",
        "drc": {"violations": []},
    }
    result = run_layout(("wrapper",), _request(), runner=_fake_runner(response))
    assert result.is_ok
    assert result.danger_ok.status == "routed"
    assert result.danger_ok.drc.clean


def test_run_layout_drc_violation_cites_rule() -> None:
    response = {
        "status": "routed",
        "pcb_path": "/tmp/x.kicad_pcb",
        "pcb_sha256": "sha256:deadbeef",
        "drc": {
            "violations": [
                {
                    "rule": "clearance",
                    "severity": "error",
                    "message": "0.1mm < 0.15mm min",
                }
            ]
        },
    }
    result = run_layout(("wrapper",), _request(), runner=_fake_runner(response))
    assert result.is_ok
    drc = result.danger_ok.drc
    assert not drc.clean
    assert drc.violations[0].rule == "clearance"


def test_run_layout_unrouted_is_indeterminate_shape() -> None:
    response = {
        "status": "unrouted",
        "pcb_path": "",
        "pcb_sha256": "",
        "drc": {"violations": []},
    }
    result = run_layout(("wrapper",), _request(), runner=_fake_runner(response))
    assert result.is_ok
    assert result.danger_ok.status == "unrouted"


def test_run_layout_nonzero_exit_is_layout_failed() -> None:
    result = run_layout(("wrapper",), _request(), runner=_fake_runner({}, returncode=1))
    assert result.is_err
    assert isinstance(result.danger_err, LayoutFailed)


def test_layout_drc_model_discharges_on_zero_violations() -> None:
    model = LayoutDrcModel()
    request = DischargeRequest(
        claim_kind="elec.layout.drc_clean",
        limit=0.5,
        inputs={VIOLATION_COUNT: Interval.point(0.0)},
    )
    evidence = model.discharge(request, registry_version="test")
    assert evidence.is_ok
    assert evidence.danger_ok.status.value == "discharged"


def test_layout_drc_model_violates_on_nonzero_violations() -> None:
    model = LayoutDrcModel()
    request = DischargeRequest(
        claim_kind="elec.layout.drc_clean",
        limit=0.5,
        inputs={VIOLATION_COUNT: Interval.point(1.0)},
    )
    evidence = model.discharge(request, registry_version="test")
    assert evidence.is_ok
    assert evidence.danger_ok.status.value == "violated"
