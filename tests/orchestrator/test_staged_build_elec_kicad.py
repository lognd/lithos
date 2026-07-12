"""The elec leg of WO-42's staged build loop, real-KiCad tier (`-m kicad`).

WO-24's close-out named this gap plainly: "wiring an elec leg into
WO-42's staged-build loop (deliverable 5) is a separate future
dispatch, mech-only today." This module closes it: a real `.cupr`
staged build (`staged_build` over `examples/hdl/counter.cupr`, a real
compiled corpus member, not a hand-built `StagedBuildReport`) realizes
a caller-supplied elec board through the real-KiCad wrapper, puts a
`RealizedLayout` (`layout.realized`) into the WO-30 payload store, and
folds it into `StagedBuildReport.realized_inputs`; `ship()` then
derives `BackendInputs.layouts` from that same report and the elec
backend's real `kicad-cli export` tier runs against the pinned
`.kicad_pcb` bytes.

Same discipline as `test_kicad_real.py`: skipped WITH the tool named
in the reason when `real_kicad_available()` is closed, never faked.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from regolith._schema.models import RealizedLayout
from regolith.backends.artifacts import NativeArtifactStore
from regolith.backends.elec import ElecBackend
from regolith.backends.ship import ship
from regolith.orchestrator import ElecBoardInputs, StagedBuildReport, staged_build
from regolith.orchestrator.lockfile import Lockfile
from regolith.orchestrator.tiers import BuildTier
from regolith.realizer.elec.kicad import LayoutRequest, real_kicad_available

pytestmark = pytest.mark.kicad

_SKIP_REASON = (
    "real KiCad gate closed: kicad-cli on PATH and pcbnew importable "
    "are both required (WO-35 deliverable 5); reopen when both are "
    "present in the execution environment"
)

_REAL_CUPR_MEMBER = "examples/hdl/counter.cupr"


@pytest.mark.skipif(not real_kicad_available(), reason=_SKIP_REASON)
def test_staged_build_elec_leg_produces_layout_realized(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """A real `.cupr` staged build carries `layout.realized` end to end."""
    request = LayoutRequest(
        netlist_path=str(tmp_path / "board.net"),
        board_outline_path=str(tmp_path / "outline.dxf"),
        output_pcb_path=str(tmp_path / "board.kicad_pcb"),
        outline_w_mm=96.0,
        outline_d_mm=90.0,
    )
    boards = {
        "kestrel_obc": ElecBoardInputs(
            netlist_hash="blake3:" + "a" * 64,
            board_outline_ref="kestrel_pc104",
            request=request,
        )
    }

    result = staged_build((_REAL_CUPR_MEMBER,), BuildTier.BUILD, elec_boards=boards)
    assert result.is_ok, result.danger_err
    report = result.danger_ok

    layout_inputs = [
        ri for ri in report.realized_inputs if ri.kind == "layout.realized"
    ]
    assert len(layout_inputs) == 1
    realized_layout_input = layout_inputs[0]
    assert realized_layout_input.subject == "kestrel_obc"

    layout = RealizedLayout.model_validate_json(realized_layout_input.payload_bytes)
    assert layout.netlist_hash == "blake3:" + "a" * 64
    assert layout.board_outline_ref == "kestrel_pc104"
    assert layout.kicad_pcb_content_hash.startswith("sha256:")
    # WO-24's honest cut: no footprint/routing machinery exists yet, so
    # the real wrapper always reports unrouted -- never faked "routed".
    assert Path(request.output_pcb_path).is_file()

    lock_rows = [row for row in report.lock_rows if row.slot == "kestrel_obc.layout"]
    assert len(lock_rows) == 1
    assert lock_rows[0].value == realized_layout_input.digest
    assert lock_rows[0].cause == "realizer(elec)"

    # `ship --build`'s own path: consume the ALREADY-produced report
    # (never re-running staged_build), derive `layouts` from its
    # `realized_inputs`, and drive the elec backend's real kicad-cli
    # export tier against the pinned `.kicad_pcb` bytes. The report is
    # round-tripped through the exact `--build DIR` disk serialization
    # (`build` writes `report.model_dump_json()`, `ship --build` reads
    # it back via `model_validate_json`, `python/regolith/cli/app.py`)
    # so the `layout.realized` payload bytes are proven to survive it.
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "build_report.json").write_bytes(
        report.model_dump_json().encode("utf-8")
    )
    reloaded = StagedBuildReport.model_validate_json(
        (build_dir / "build_report.json").read_text()
    )
    assert reloaded.realized_inputs == report.realized_inputs

    native = NativeArtifactStore(str(tmp_path))
    native.put_at(
        layout.kicad_pcb_content_hash, Path(request.output_pcb_path).read_bytes()
    )
    backend = ElecBackend("kestrel_obc", ())
    out_dir = tmp_path / "out"
    shipped = ship(
        (_REAL_CUPR_MEMBER,),
        {"elec": backend},
        str(out_dir),
        lockfile=Lockfile(tool_version="0.1.0"),
        native=native,
        prebuilt=reloaded,
    )
    assert shipped.is_ok, shipped.danger_err
    manifest = shipped.danger_ok
    relpaths = {f.relpath for f in manifest.files}
    assert "elec/bom.csv" in relpaths
    assert "elec/panel.json" in relpaths
    assert any(p.startswith("elec/gerbers/") for p in relpaths)
    assert any(p.startswith("elec/drill/") for p in relpaths)
    assert any(p.startswith("elec/pos/") for p in relpaths)


@pytest.mark.skipif(
    real_kicad_available(),
    reason="proves the honest-skip arm; only meaningful when the gate is "
    "actually closed",
)
def test_staged_build_elec_leg_skips_honestly_when_kicad_unavailable(
    tmp_path,
) -> None:  # type: ignore[no-untyped-def]
    """A closed real-KiCad gate leaves the elec subject pending, never faked."""
    request = LayoutRequest(
        netlist_path=str(tmp_path / "board.net"),
        board_outline_path=str(tmp_path / "outline.dxf"),
        output_pcb_path=str(tmp_path / "board.kicad_pcb"),
        outline_w_mm=96.0,
        outline_d_mm=90.0,
    )
    boards = {
        "kestrel_obc": ElecBoardInputs(
            netlist_hash="blake3:" + "a" * 64,
            board_outline_ref="kestrel_pc104",
            request=request,
        )
    }
    result = staged_build((_REAL_CUPR_MEMBER,), BuildTier.BUILD, elec_boards=boards)
    assert result.is_ok, result.danger_err
    report = result.danger_ok
    assert report.realized_inputs == ()
    assert report.lock_rows == ()
