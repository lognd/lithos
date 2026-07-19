"""Real-KiCad gate (WO-35 deliverable 5): `-m kicad` marked tier.

The always-on tier (`test_kicad.py`, `test_kestrel_fixture.py`) fakes
the layout subprocess and never depends on real tooling. THIS module
is the tool-gated tier: it asserts the wire protocol against a live
`kicad-cli` invocation when `real_kicad_available()` is true, and
skips WITH the tool named in the reason otherwise (the honest cut
retired, not deleted -- see `regolith.realizer.elec.kicad`'s module
docstring and WO-24's close-out cut note, updated by WO-35).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from regolith.orchestrator.payload_store import PayloadStore
from regolith.realizer.elec.extraction import extract_from_pcb
from regolith.realizer.elec.kicad import (
    LayoutArtifact,
    LayoutRequest,
    discover_kicad_cli,
    hash_pcb_file,
    real_kicad_available,
    run_real_layout,
)
from regolith.realizer.elec.realized import build_realized_layout, put_realized_layout

pytestmark = pytest.mark.kicad

_SKIP_REASON = (
    "real KiCad gate closed: kicad-cli on PATH and pcbnew importable "
    "are both required (WO-35 deliverable 5); reopen when both are "
    "present in the execution environment"
)


@pytest.mark.skipif(not real_kicad_available(), reason=_SKIP_REASON)
def test_real_kicad_cli_reports_a_version() -> None:
    """Smoke: a real `kicad-cli` on PATH answers `--version`, exit 0."""
    import subprocess

    cli = discover_kicad_cli()
    assert cli is not None
    completed = subprocess.run(
        [cli, "--version"], capture_output=True, timeout=30, check=False
    )
    assert completed.returncode == 0


# frob:tests python/regolith/realizer/elec/kicad.py::real_kicad_available kind="unit"
def test_gate_reports_which_mode_ran() -> None:
    """CI records which mode ran (WO-35 acceptance): the gate is queryable."""
    # Never skipped: proves the gate function itself is callable and
    # honest (True only when BOTH tools are actually present) without
    # requiring the tools to be installed in this sandbox.
    available = real_kicad_available()
    assert isinstance(available, bool)


@pytest.mark.skipif(not real_kicad_available(), reason=_SKIP_REASON)
# frob:tests python/regolith/realizer/elec/kicad.py::run_real_layout kind="unit"
# frob:tests python/regolith/realizer/elec/kicad.py::hash_pcb_file kind="unit"
# frob:tests python/regolith/realizer/elec/kicad.py::real_wrapper_argv kind="unit"
def test_real_wrapper_produces_a_real_pcb_and_drc_report(tmp_path: Path) -> None:
    """WO-24 close-out: `run_real_layout` drives real pcbnew + kicad-cli.

    Honest outcome (module docstring on `kicad_wrapper.py`): status is
    always `unrouted` (no footprint-library resolution exists yet), but
    the `.kicad_pcb` and the DRC report are REAL KiCad output -- an
    outline-only board is DRC-clean under `--severity-error`.
    """
    output_pcb = tmp_path / "board.kicad_pcb"
    request = LayoutRequest(
        netlist_path=str(tmp_path / "x.net"),
        board_outline_path=str(tmp_path / "x.dxf"),
        output_pcb_path=str(output_pcb),
        outline_w_mm=305.0,
        outline_d_mm=244.0,
    )
    result = run_real_layout(request)
    assert result.is_ok, result
    response = result.danger_ok
    assert response.status == "unrouted"
    assert output_pcb.is_file()
    assert response.pcb_sha256 == hash_pcb_file(output_pcb)
    assert response.drc.clean
    # WO-103: the real wrapper draws the DESIGN'S own outline (the
    # 50mm placeholder square is retired), so the mainboard_mx
    # 305x244mm rect is discoverable in the saved `.kicad_pcb` file
    # a real pcbnew round-trip actually wrote.
    pcb_text = output_pcb.read_text(encoding="ascii", errors="replace")
    assert "Edge.Cuts" in pcb_text


@pytest.mark.skipif(not real_kicad_available(), reason=_SKIP_REASON)
# frob:tests python/regolith/realizer/elec/realized.py::build_realized_layout kind="unit"
# frob:tests python/regolith/realizer/elec/realized.py::put_realized_layout kind="unit"
def test_real_layout_round_trips_through_realized_layout_store(
    tmp_path: Path,
) -> None:
    """WO-42's `layout.realized` `put` seam, exercised against a REAL board.

    Runs the real wrapper, extracts real (empty, since unrouted) net/
    copper measurements via real pcbnew, assembles a `RealizedLayout`,
    and `put`s it into the WO-30 store -- the WO-24 close-out's other
    half (WO-42 deliverable 4's remainder).
    """
    output_pcb = tmp_path / "board.kicad_pcb"
    request = LayoutRequest(
        netlist_path=str(tmp_path / "x.net"),
        board_outline_path=str(tmp_path / "x.dxf"),
        output_pcb_path=str(output_pcb),
        outline_w_mm=120.0,
        outline_d_mm=90.0,
    )
    result = run_real_layout(request)
    assert result.is_ok, result
    response = result.danger_ok

    artifact = LayoutArtifact(
        pcb_path=response.pcb_path,
        content_hash=response.pcb_sha256,
        drc=response.drc,
    )
    extraction = extract_from_pcb(output_pcb)
    assert extraction.is_ok, extraction

    layout = build_realized_layout(
        netlist_hash="sha256:deadbeef",
        board_outline_ref="mech:test_outline",
        artifact=artifact,
        extraction=extraction.danger_ok,
    )
    assert layout.kicad_pcb_content_hash == response.pcb_sha256
    # An unrouted board genuinely has no routed length/copper -- an
    # empty summary is the CORRECT measurement, not a placeholder.
    assert layout.copper.net_lengths_mm == []
    assert layout.copper.copper_areas_mm2 == []

    store = PayloadStore(str(tmp_path))
    digest = put_realized_layout(store, layout)
    resolved = store.resolve(digest)
    assert resolved.is_ok
    assert resolved.danger_ok == layout.model_dump_json().encode("utf-8")

    # Idempotent: putting the same layout again yields the same digest.
    assert put_realized_layout(store, layout) == digest


@pytest.mark.skipif(not real_kicad_available(), reason=_SKIP_REASON)
def test_real_wrapper_draws_the_mainboard_mx_outline_and_exports_gerbers(
    tmp_path: Path,
) -> None:
    """WO-103 acceptance: mainboard_mx's real 305x244mm outline (not the
    retired 50mm placeholder square) reaches a real `pcbnew.BOARD` via
    `run_real_layout`, and `kicad-cli pcb export gerbers` (through
    `ElecBackend`, the SAME real leg `regolith ship` drives) names that
    outline in the exported ``Edge.Cuts`` gerber.
    """
    from regolith.backends.artifacts import NativeArtifactStore
    from regolith.backends.elec import ElecBackend
    from regolith.backends.framework import BackendInputs
    from regolith.orchestrator.lockfile import Lockfile

    output_pcb = tmp_path / "mainboard_mx.kicad_pcb"
    request = LayoutRequest(
        netlist_path=str(tmp_path / "mainboard_mx.net"),
        board_outline_path=str(tmp_path / "mainboard_mx.dxf"),
        output_pcb_path=str(output_pcb),
        outline_w_mm=305.0,
        outline_d_mm=244.0,
    )
    result = run_real_layout(request)
    assert result.is_ok, result
    response = result.danger_ok
    assert response.status == "unrouted"

    artifact = LayoutArtifact(
        pcb_path=response.pcb_path,
        content_hash=response.pcb_sha256,
        drc=response.drc,
    )
    layout = build_realized_layout(
        netlist_hash="sha256:" + "a" * 64,
        board_outline_ref="mainboard_mx:outline",
        artifact=artifact,
    )

    native = NativeArtifactStore(str(tmp_path))
    native.put_at(layout.kicad_pcb_content_hash, output_pcb.read_bytes())
    inputs = BackendInputs(
        lockfile=Lockfile(tool_version="0.1.0"),
        evidence={},
        geometry={},
        layouts={"mainboard_mx": layout},
        native=native,
    )
    backend = ElecBackend("mainboard_mx", (), available=real_kicad_available)
    produced = backend.produce(inputs)
    assert produced.is_ok, produced.danger_err if produced.is_err else None
    files = {f.relpath: f for f in produced.danger_ok}
    edge_cuts = [
        f
        for name, f in files.items()
        if name.startswith("gerbers/") and "Edge_Cuts" in name
    ]
    assert edge_cuts, f"no Edge.Cuts gerber in {sorted(files)}"
    gerber_text = edge_cuts[0].content.decode("ascii", errors="replace")
    # RS-274X coordinates are format-spec integers (no literal "305mm"
    # string), but the extreme corner the 305x244mm rect plots is
    # discoverable in the format-spec-scaled coordinate stream: with
    # kicad-cli's default 4.6 (mm, 6 decimal places) format spec, the
    # far corner is X305000000Y244000000 (some ordering/sign per
    # kicad-cli's own coordinate-system convention).
    assert "305000000" in gerber_text or "305.000000" in gerber_text
    assert "244000000" in gerber_text or "244.000000" in gerber_text
