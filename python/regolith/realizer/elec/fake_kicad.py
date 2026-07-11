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
``Edge.Cuts`` outline sized from the caller's actual ``w_mm``/``d_mm``
(unlike the real wrapper's fixed 50mm placeholder square) and write it
as a real, valid, parseable `.kicad_pcb` S-expression file -- so the
content hash and file this module emits are not fixtures, they are the
genuine (if minimal) board outline the `impl BoardOutline<w=..., d=...>
for self as outline` corpus body declares.
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
from regolith.realizer.elec.kicad import LayoutRequest, LayoutResponse, run_layout

_log = get_logger(__name__)

# A logging-only label (never spawned): `run_layout` only reads
# `argv[0]` for its log lines, since the actual work happens in the
# injected `runner`, not a real subprocess.
FAKE_WRAPPER_ARGV: tuple[str, ...] = ("fake-kicad-layout",)


def _kicad_pcb_text(w_mm: float, d_mm: float) -> str:
    """A minimal, valid `.kicad_pcb` S-expression: one `Edge.Cuts`
    rectangle sized ``w_mm`` x ``d_mm``, origin at (0, 0).

    Deliberately minimal (no nets, no footprints, no layer stack beyond
    the one this outline needs) -- this tier's honest scope is the
    board OUTLINE only, matching the real wrapper's own "footprint
    resolution/placement and routing are NOT attempted here" cut.
    """
    return (
        "(kicad_pcb (version 20221018) (generator regolith-fake-kicad)\n"
        "  (general (thickness 1.6))\n"
        '  (layer_stack (layer 0 "F.Cu" signal) (layer 31 "B.Cu" signal))\n'
        "  (gr_rect\n"
        "    (start 0 0)\n"
        f"    (end {w_mm:.4f} {d_mm:.4f})\n"
        '    (layer "Edge.Cuts")\n'
        "    (width 0.05)\n"
        "  )\n"
        ")\n"
    )


def _fake_runner(
    w_mm: float, d_mm: float
) -> Callable[..., subprocess.CompletedProcess[bytes]]:
    """Build the injectable `runner` `run_layout` expects: writes the
    real outline file as its one side effect, then returns the
    canned `LayoutResponse` as stdout -- same shape as
    `tests/realizer/elec/test_kicad.py::_fake_runner`.
    """

    def runner(
        argv: list[str],
        *,
        input: bytes,  # noqa: A002 (matches subprocess.run's own kwarg name)
        capture_output: bool,
        timeout: float,
        check: bool,
    ) -> subprocess.CompletedProcess[bytes]:
        del capture_output, timeout, check  # unused: pure fake
        request = json.loads(input.decode("ascii"))
        output_pcb_path = request["output_pcb_path"]
        text = _kicad_pcb_text(w_mm, d_mm)
        Path(output_pcb_path).write_text(text, encoding="ascii")
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


def run_fake_layout(
    request: LayoutRequest, *, w_mm: float, d_mm: float
) -> Result[LayoutResponse, ToolUnavailable | LayoutFailed]:
    """Run one deterministic, no-install layout pass through
    `run_layout`'s own injectable-runner seam (never a real subprocess,
    never gated on `real_kicad_available()` -- this tier does not need
    KiCad at all).
    """
    return run_layout(FAKE_WRAPPER_ARGV, request, runner=_fake_runner(w_mm, d_mm))
