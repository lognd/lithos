"""The REAL KiCad layout wrapper (WO-24 close-out, WO-42 deliverable 2's
producer): the ``argv`` executable `regolith.realizer.elec.kicad.run_layout`
talks to when `real_kicad_available()` is OPEN.

Runnable as ``python -m regolith.realizer.elec.kicad_wrapper``: reads one
`LayoutRequest` JSON document on stdin, drives real `pcbnew`/`kicad-cli`,
and writes one `LayoutResponse` JSON document to stdout -- the exact wire
discipline `regolith.realizer.elec.kicad`'s module docstring describes.

Honest scope (never faked): this wrapper builds a real `pcbnew.BOARD`,
draws a real rectangular `Edge.Cuts` outline sized from the caller's
``LayoutRequest.outline_w_mm``/``outline_d_mm`` (WO-103: the SAME
design-carried rectangle the fake tier already draws -- the 50mm
placeholder square is retired; importing a richer outline shape, e.g.
a mech DXF export, is a separate, larger integration this dispatch
does not attempt, see charter 38 sec. 1.10), saves it as a real
`.kicad_pcb`, and runs a real `kicad-cli pcb drc` pass against it.
Footprint resolution/placement and routing are NOT attempted here (no
footprint-library resolution machinery exists in this repo yet --
inventing one would be exactly the kind of guessed convention the
project's engineering principles forbid); the response is therefore
always ``status="unrouted"`` -- WO-24's own documented honest outcome
for "autorouting quality is NOT promised" -- never a faked
``"routed"``. The DRC report on the resulting (outline-only,
footprint-free) board is real KiCad output, not a fixture.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from regolith.logging_setup import get_logger

_log = get_logger(__name__)


def _draw_outline(board: Any, w_mm: float, d_mm: float) -> None:
    """Draw a real ``w_mm`` x ``d_mm`` Edge.Cuts rectangle on ``board``
    (real pcbnew), origin at (0, 0) -- the same rect convention the
    fake tier's `.kicad_pcb` text emits (WO-103).
    """
    import pcbnew

    w = pcbnew.FromMM(w_mm)
    d = pcbnew.FromMM(d_mm)
    rect = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_RECT)
    rect.SetStart(pcbnew.VECTOR2I(0, 0))
    rect.SetEnd(pcbnew.VECTOR2I(w, d))
    rect.SetLayer(pcbnew.Edge_Cuts)
    board.Add(rect)


def _draw_identity_text(
    board: Any, name: str, rev: str, w_mm: float, d_mm: float
) -> None:
    """Draw the board-identity silkscreen block (WO-124, charter 41
    sec. 3) as real `pcbnew.PCB_TEXT` items on `F.SilkS` -- KiCad's own
    plotter renders genuine vector strokes on export, no hand-rolled
    font needed for this leg. ``rev`` is honestly `REV: N/A` when no
    design-revision concept is supplied (never fabricated).

    Geometry (height/margin/anchors) is single-sourced in
    `regolith.realizer.elec.identity` (the D238.3 visual-pass fixes:
    inside the outline with margin, charter-41 min height, LEFT/BOTTOM
    justification -- pcbnew's default center anchor was the off-board
    defect)."""
    import pcbnew

    from regolith.realizer.elec.identity import identity_block_layout

    height_mm, lines = identity_block_layout(w_mm, d_mm, name, rev)
    size = pcbnew.VECTOR2I(pcbnew.FromMM(height_mm), pcbnew.FromMM(height_mm))
    for text, x_mm, y_mm in lines:
        if not text:
            continue
        item = pcbnew.PCB_TEXT(board)
        item.SetText(text)
        item.SetTextSize(size)
        item.SetTextThickness(pcbnew.FromMM(0.15 * height_mm))
        item.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
        item.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_BOTTOM)
        item.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x_mm), pcbnew.FromMM(y_mm)))
        item.SetLayer(pcbnew.F_SilkS)
        board.Add(item)


def _build_and_save_board(
    output_pcb_path: str, w_mm: float, d_mm: float, board_name: str, design_hash: str
) -> None:
    """Construct a real, outline-only `pcbnew.BOARD` and save it."""
    import pcbnew

    board = pcbnew.BOARD()
    _draw_outline(board, w_mm, d_mm)
    if board_name or design_hash:
        name_line = f"{board_name} {design_hash}".strip()
        _draw_identity_text(board, name_line, "REV: N/A", w_mm, d_mm)
    pcbnew.SaveBoard(output_pcb_path, board)
    _log.info(
        "kicad_wrapper: saved %.2fmm x %.2fmm outline board to %s",
        w_mm,
        d_mm,
        output_pcb_path,
    )


def _run_drc(pcb_path: str) -> tuple[list[dict[str, str]], bool]:
    """Run a real `kicad-cli pcb drc` pass; returns (violations, ok)."""
    report_path = str(Path(pcb_path).with_suffix(".drc.json"))
    completed = subprocess.run(
        [
            "kicad-cli",
            "pcb",
            "drc",
            "--format",
            "json",
            "--severity-error",
            "--output",
            report_path,
            pcb_path,
        ],
        capture_output=True,
        timeout=60,
        check=False,
    )
    if completed.returncode != 0:
        _log.warning(
            "kicad_wrapper: kicad-cli pcb drc exited %d: %s",
            completed.returncode,
            completed.stderr.decode("ascii", errors="replace"),
        )
        return [], False
    report = json.loads(Path(report_path).read_text(encoding="ascii", errors="replace"))
    violations = [
        {
            "rule": v.get("type", "unknown"),
            "severity": v.get("severity", "error"),
            "message": v.get("description", ""),
        }
        for v in report.get("violations", [])
    ]
    return violations, True


def run(request_json: str) -> str:
    """The wrapper's pure entry point: request JSON in, response JSON out."""
    request = json.loads(request_json)
    output_pcb_path = request["output_pcb_path"]
    w_mm = request["outline_w_mm"]
    d_mm = request["outline_d_mm"]
    board_name = request.get("board_name", "")
    design_hash = request.get("design_hash", "")
    try:
        _build_and_save_board(output_pcb_path, w_mm, d_mm, board_name, design_hash)
    except Exception as exc:  # pragma: no cover - programmer/infra bug surface
        _log.error("kicad_wrapper: board construction failed: %s", exc)
        return json.dumps(
            {
                "status": "unrouted",
                "pcb_path": "",
                "pcb_sha256": "",
                "drc": {"violations": []},
            }
        )

    violations, drc_ran = _run_drc(output_pcb_path)
    pcb_bytes = Path(output_pcb_path).read_bytes()
    pcb_sha256 = f"sha256:{hashlib.sha256(pcb_bytes).hexdigest()}"

    response = {
        # Honest: footprint placement/routing are not attempted (see
        # module docstring) -- this wrapper never claims "routed".
        "status": "unrouted",
        "pcb_path": output_pcb_path,
        "pcb_sha256": pcb_sha256,
        "drc": {"violations": violations if drc_ran else []},
    }
    return json.dumps(response)


def main() -> int:
    """CLI entry point: stdin JSON in, stdout JSON out (the wire discipline)."""
    request_json = sys.stdin.read()
    sys.stdout.write(run(request_json))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
