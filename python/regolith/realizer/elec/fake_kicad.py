"""The FAKE-subprocess KiCad layout tier: a deterministic, no-install
``run_layout`` runner (WO-71 continuation slice 2).

`regolith.realizer.elec.kicad`'s own module docstring names the seam
this module fills: "the fake-subprocess tier remains for KiCad-less
environments (the same dependency-injection point WO-20's own adapter
tests use)". Every existing test of that tier (`tests/realizer/elec/
test_kicad.py::_fake_runner`) injects a `runner` callable into
`run_layout` that returns a canned `subprocess.CompletedProcess`; this
module is that SAME pattern promoted out of test-only code so a
non-test caller (the staged build loop, opt-in per board -- see
`ElecBoardInputs.deterministic`) can reach it too.

Honesty contract (unchanged from the real wrapper,
`kicad_wrapper.py`'s own documented posture): this tier never claims
``status="routed"`` -- no netlist is bound and no footprint is placed,
so ``"unrouted"`` is the only honest status, exactly like the real
wrapper's own "autorouting quality is NOT promised" cut. No DRC pass
runs (there is no real `kicad-cli` invocation here), so the DRC report
is always empty -- this is NOT a claim of DRC-clean, only the honest
absence of a check; a caller wanting a real DRC verdict must go through
`real_kicad_available()`'s real tier instead.

The one thing this tier DOES do for real: draw a genuine rectangular
``Edge.Cuts`` outline sized from the caller's actual
``request.outline_w_mm``/``outline_d_mm`` (WO-103: the SAME field the
real wrapper's wire protocol reads, no longer the real wrapper's old
fixed 50mm placeholder square) and write it as a real, valid,
parseable `.kicad_pcb` S-expression file -- so the content hash and
file this module emits are not fixtures, they are the genuine (if
minimal) board outline the `impl BoardOutline<w=..., d=...> for self
as outline` corpus body declares.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Callable
from pathlib import Path

from typani.result import Result

from regolith.logging_setup import get_logger
from regolith.realizer.elec.errors import LayoutFailed, ToolUnavailable
from regolith.realizer.elec.identity import (
    MIN_TEXT_HEIGHT_MM,
    identity_block_layout,
)
from regolith.realizer.elec.kicad import LayoutRequest, LayoutResponse, run_layout

_log = get_logger(__name__)

# A logging-only label (never spawned): `run_layout` only reads
# `argv[0]` for its log lines, since the actual work happens in the
# injected `runner`, not a real subprocess.
# frob:doc docs/modules/py-realizer.md#elec-fake-kicad
FAKE_WRAPPER_ARGV: tuple[str, ...] = ("fake-kicad-layout",)


_FULL_LAYER_TABLE = (
    "  (layers\n"
    '    (0 "F.Cu" signal)\n'
    '    (31 "B.Cu" signal)\n'
    '    (34 "B.Paste" user)\n'
    '    (35 "F.Paste" user)\n'
    '    (36 "B.SilkS" user "B.Silkscreen")\n'
    '    (37 "F.SilkS" user "F.Silkscreen")\n'
    '    (38 "B.Mask" user)\n'
    '    (39 "F.Mask" user)\n'
    '    (44 "Edge.Cuts" user)\n'
    '    (45 "Margin" user)\n'
    '    (46 "B.CrtYd" user "B.Courtyard")\n'
    '    (47 "F.CrtYd" user "F.Courtyard")\n'
    '    (48 "B.Fab" user)\n'
    '    (49 "F.Fab" user)\n'
    "  )\n"
)


def _gr_text(
    text: str,
    x_mm: float,
    y_mm: float,
    layer: str,
    uuid_suffix: str,
    height_mm: float = 1.0,
) -> str:
    """One real `.kicad_pcb gr_text` item: KiCad's own plotter renders
    this as genuine vector strokes on export (no hand-rolled font
    needed for this leg -- WO-124 deliverable 2).

    Anchored LEFT/BOTTOM at ``(x_mm, y_mm)`` -- KiCad's default CENTER
    anchor is exactly the D238.3 off-board defect (half the identity
    text hung past x=0 on the shipped mainboard silkscreen)."""
    safe = text.replace('"', "'")
    return (
        f'  (gr_text "{safe}"\n'
        f"    (at {x_mm:.4f} {y_mm:.4f})\n"
        f'    (layer "{layer}")\n'
        f'    (uuid "00000000-0000-0000-0000-00000000{uuid_suffix:>04}")\n'
        "    (effects\n"
        f"      (font (size {height_mm:.4f} {height_mm:.4f}) "
        f"(thickness {0.15 * height_mm:.4f}))\n"
        "      (justify left bottom)\n"
        "    )\n"
        "  )\n"
    )


def _kicad_pcb_text(
    w_mm: float,
    d_mm: float,
    *,
    identity_lines: tuple[str, str] = ("", ""),
    refdes: tuple[tuple[str, float, float], ...] = (),
) -> str:
    """A minimal, valid `.kicad_pcb` S-expression: one `Edge.Cuts`
    rectangle sized ``w_mm`` x ``d_mm``, origin at (0, 0), the full
    standard KiCad layer table (WO-124: the earlier 3-layer table
    silently dropped silkscreen/mask/paste/fab from a real-`kicad-cli`
    re-export -- verified on-host), and the board-identity silkscreen
    text (name + design short-hash, honest `REV: N/A` -- no revision
    concept exists in the realized surface yet) plus any placement
    refdes text (the labeling seam; empty today).

    Deliberately still minimal otherwise (no nets, no footprints) --
    this tier's honest scope is the board OUTLINE + identity/labeling
    only, matching the real wrapper's own "footprint resolution/
    placement and routing are NOT attempted here" cut.

    The layer table uses the real `.kicad_pcb` `(layers ...)` form
    (WO-105 ship fix): the earlier `layer_stack` spelling was not
    loadable by real `kicad-cli` (10.0.4 "Failed to load board", exit
    3), which broke the ship gerber export the day a project's spec
    opted a board into this tier -- verified: the `layers` form both
    loads and plots gerbers.
    """
    body = [
        "(kicad_pcb (version 20221018) (generator regolith-fake-kicad)\n",
        "  (general (thickness 1.6))\n",
        _FULL_LAYER_TABLE,
        "  (gr_rect\n",
        "    (start 0 0)\n",
        f"    (end {w_mm:.4f} {d_mm:.4f})\n",
        '    (layer "Edge.Cuts")\n',
        "    (width 0.05)\n",
        "  )\n",
    ]
    name_line, rev_line = identity_lines
    if name_line or rev_line:
        # WO-124 D238.3 visual-pass geometry: inside the outline with a
        # real margin, charter-41-compliant height, left/bottom anchor
        # -- single-sourced in `identity.identity_block_layout` so this
        # leg and the pcbnew leg cannot drift apart.
        height_mm, lines = identity_block_layout(w_mm, d_mm, name_line, rev_line)
        for idx, (text, x, y) in enumerate(lines, start=1):
            if text:
                body.append(
                    _gr_text(text, x, y, "F.SilkS", f"{idx:x}", height_mm=height_mm)
                )
    for idx, (ref, x, y) in enumerate(refdes, start=3):
        body.append(
            _gr_text(ref, x, y, "F.SilkS", f"{idx:x}", height_mm=MIN_TEXT_HEIGHT_MM)
        )
    body.append(")\n")
    return "".join(body)


def _fake_runner(
    w_mm: float, d_mm: float, identity_lines: tuple[str, str] = ("", "")
) -> Callable[..., subprocess.CompletedProcess[bytes]]:
    """Build the injectable `runner` `run_layout` expects: writes the
    real outline file as its one side effect, then returns the
    canned `LayoutResponse` as stdout -- same shape as
    `tests/realizer/elec/test_kicad.py::_fake_runner`.
    """

    def runner(
        argv: list[str],
        *,
        input: bytes,  # noqa: A002 (matches the legacy runner's own kwarg name)
        capture_output: bool,
        timeout: float,
        check: bool,
    ) -> subprocess.CompletedProcess[bytes]:
        del capture_output, timeout, check  # unused: pure fake
        request = json.loads(input.decode("ascii"))
        output_pcb_path = request["output_pcb_path"]
        text = _kicad_pcb_text(w_mm, d_mm, identity_lines=identity_lines)
        # Create the board output directory if the caller has not: a
        # first `build --release --spec` on a fresh checkout has no
        # `.regolith/board/` yet, and the real wrapper's kicad-cli
        # makes its own parent, so the fake tier must match or it
        # fails with FileNotFoundError on the very first ship (WO-106).
        out = Path(output_pcb_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="ascii")
        pcb_sha256 = f"sha256:{hashlib.sha256(text.encode('ascii')).hexdigest()}"
        response = LayoutResponse(
            status="unrouted",
            pcb_path=output_pcb_path,
            pcb_sha256=pcb_sha256,
        )
        _log.info(
            "fake-kicad: wrote %.2fmm x %.2fmm outline-only board to %s",
            w_mm,
            d_mm,
            output_pcb_path,
        )
        return subprocess.CompletedProcess(
            args=argv,
            returncode=0,
            stdout=response.model_dump_json().encode("ascii"),
            stderr=b"",
        )

    return runner


# frob:doc docs/modules/py-realizer.md#elec-fake-kicad
def run_fake_layout(
    request: LayoutRequest,
) -> Result[LayoutResponse, ToolUnavailable | LayoutFailed]:
    """Run one deterministic, no-install layout pass through
    `run_layout`'s own injectable-runner seam (never a real subprocess,
    never gated on `real_kicad_available()` -- this tier does not need
    KiCad at all).

    ``request.outline_w_mm``/``outline_d_mm`` are the ONE source of
    outline geometry (WO-103): the same fields the real leg's wire
    protocol reads, so a caller never supplies dimensions twice.
    ``request.board_name``/``design_hash`` (WO-124, optional wire
    fields) draw the board-identity silkscreen block when supplied.
    """
    identity = (
        (f"{request.board_name} {request.design_hash}".strip(), "REV: N/A")
        if request.board_name or request.design_hash
        else ("", "")
    )
    return run_layout(
        FAKE_WRAPPER_ARGV,
        request,
        runner=_fake_runner(
            request.outline_w_mm, request.outline_d_mm, identity_lines=identity
        ),
    )
