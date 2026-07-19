"""Demo 1 -- discrete `select` surface: ebi_decode (WO-56).

`examples/tracks/cuprite/ebi_decode.cupr` declares

    impl AddressDecodeGlue by select(nor_glue, cpld, mcu_chip_selects)

the sixth impl strategy (D161). This demo runs the REAL pipeline:

    real .cupr -> compiler.check -> BuildPayload.choice_points
    -> domains_from_choice_points -> optimize_discrete
    -> winner_lock_row (INV-21 `cause: optimize(...)`)

exactly the landed WO-56 chain (`tests/test_wo56_ebi_decode.py`), then
emits the physical proof: the pinned `regolith.lock`, the optimization
trace sheet (SVG + PDF), and -- to prove the winner is genuinely
policy-driven, not hardcoded -- a POLICY-FLIP variant whose reversed
cost order flips which candidate wins.
"""

from __future__ import annotations

import json

from regolith import compiler, core_version
from regolith.backends.drawings.producers import opt_trace
from regolith.backends.drawings.renderer import render_svg
from regolith.backends.drawings.renderer_pdf import render_pdf
from regolith.logging_setup import get_logger
from regolith.orchestrator.lockfile import (
    Lockfile,
    LockSection,
)
from regolith.orchestrator.lockfile import (
    render as render_lockfile,
)
from regolith.orchestrator.nogood_cache import NogoodCache
from regolith.orchestrator.optimize import (
    domains_from_choice_points,
    optimize_discrete,
    store_trace,
    winner_lock_row,
)
from regolith.orchestrator.payload_store import PayloadStore

from demos.harness import DemoWriter, artifact_table

_log = get_logger(__name__)

# frob:doc docs/modules/demos.md#demo-proof-pack-shape
DEMO = "demo1_select_ebi_decode"
# frob:doc docs/modules/demos.md#demo-proof-pack-shape
SURFACE = "discrete select() choice point (ebi_decode, WO-56)"
# frob:doc docs/modules/demos.md#demo-proof-pack-shape
SOURCE = "examples/tracks/cuprite/ebi_decode.cupr"
# frob:doc docs/modules/demos.md#demo-proof-pack-shape
SUBJECT = "decoder_board.AddressDecodeGlue"

# The declared, closed-form per-candidate cost table (regolith/12 sec. 4
# policy surface; the SAME table `tests/test_wo56_ebi_decode.py` uses).
# nor_glue = two 74HC parts (highest); cpld = one part; mcu_chip_selects
# = no added part (the MCU already carries the FSMC controller, lowest).
# frob:doc docs/modules/demos.md#demo-proof-pack-shape
COST_BASE = {SUBJECT: {"nor_glue": 2.40, "cpld": 1.10, "mcu_chip_selects": 0.0}}
# The policy flip: reverse the preference (nor_glue now cheapest).
# frob:doc docs/modules/demos.md#demo-proof-pack-shape
COST_FLIP = {SUBJECT: {"nor_glue": 0.0, "cpld": 1.10, "mcu_chip_selects": 2.40}}


def _real_choice_points() -> dict[str, dict[str, object]]:
    """`compiler.check` the real source and pull its lowered choice points."""
    result = compiler.check((SOURCE,))
    if result.is_err:
        raise RuntimeError(f"ebi_decode: check failed: {result.danger_err}")
    outcome = result.danger_ok
    if not outcome.ok:
        raise RuntimeError("ebi_decode.cupr did not check clean")
    payload = json.loads(outcome.payload_json)
    choice_points = payload["choice_points"]
    if not choice_points:
        raise RuntimeError("ebi_decode.cupr lowered no ChoicePoint")
    return choice_points


def _search(choice_points, cost_table, store):
    """Run the real discrete driver; return (trace, winner_row, digest)."""
    domains, evaluator, screen, objective = domains_from_choice_points(
        choice_points, cost_table
    )
    trace = optimize_discrete(
        domains,
        evaluator,
        objective,
        seed=0,
        budget_evals=100,
        screen=screen,
        nogood_cache=NogoodCache(),
    )
    digest = store_trace(store, trace)
    row = winner_lock_row(trace, SUBJECT, "cost", digest).danger_ok
    return trace, row, digest


def _winner_candidate(trace) -> str:
    winner = trace.candidates[trace.winner]
    return dict(item.root for item in winner.assignment)[SUBJECT]


# frob:doc docs/modules/demos.md#demo-proof-pack-shape
def run() -> bool:
    """Emit the ebi_decode proof pack; return True (this surface is live)."""
    writer = DemoWriter(DEMO, SURFACE)
    choice_points = _real_choice_points()
    store = PayloadStore(str(writer.out_dir))

    base_trace, base_row, base_digest = _search(choice_points, COST_BASE, store)
    flip_trace, flip_row, _ = _search(choice_points, COST_FLIP, store)

    base_winner = _winner_candidate(base_trace)
    flip_winner = _winner_candidate(flip_trace)
    _log.info("ebi_decode: base winner=%s flip winner=%s", base_winner, flip_winner)

    # The pinned lockfile -- the `cause: optimize(...)` row, verbatim.
    lockfile = Lockfile(
        tool_version=core_version(),
        sections=(LockSection(name="", rows=(base_row,)),),
    )
    lock_text = render_lockfile(lockfile)
    writer.emit("regolith.lock", lock_text.encode("ascii"))

    # The optimization-trace sheet: candidate table + convergence + winner.
    model = opt_trace(SUBJECT, base_trace)
    writer.emit("opt_trace.svg", render_svg(model))
    writer.emit("opt_trace.pdf", render_pdf(model))

    # The policy-flip evidence: the reversed-cost lockfile row.
    flip_lock = Lockfile(
        tool_version=core_version(),
        sections=(LockSection(name="", rows=(flip_row,)),),
    )
    writer.emit("regolith.flip.lock", render_lockfile(flip_lock).encode("ascii"))

    cause_row = base_row.cause
    proof = "\n".join(
        [
            f"# PROOF: {SURFACE}",
            "",
            "- optimized quantity: **cost** (declared closed-form per-candidate table)",
            f"- domain: `{SUBJECT}` over `select(nor_glue, cpld, mcu_chip_selects)`",
            f"  lowered from real source `{SOURCE}` (a REAL "
            "`BuildPayload.choice_points` entry, not a fixture)",
            f"- winner: **{base_winner}** (cost 0.0 -- the MCU's built-in FSMC "
            "controller adds no part)",
            "- cause row (verbatim from `regolith.lock`):",
            "",
            "```",
            base_row.value + "    cause: " + cause_row,
            "```",
            "",
            "## Policy-flip proof (the winner is genuinely searched, not hardcoded)",
            "",
            f"Reversing the declared cost preference flips the winner to "
            f"**{flip_winner}**:",
            "",
            "```",
            flip_row.value + "    cause: " + flip_row.cause,
            "```",
            "",
            "See `regolith.flip.lock` for the full reversed-cost pin.",
            "",
            "## Where a human SEES it",
            "",
            "`opt_trace.svg` / `opt_trace.pdf` -- the optimization-trace sheet: "
            "every evaluated candidate with its cost, the convergence polyline, "
            "and the winner annotation citing the trace digest "
            f"`{base_digest}`.",
            "",
            "## Artifacts",
            "",
            artifact_table(writer.rows),
        ]
    )
    writer.finish(
        live=True,
        optimized_quantity="cost",
        domain=f"{SUBJECT} over select(nor_glue, cpld, mcu_chip_selects)",
        winner=base_winner,
        cause_row=base_row.value + "    cause: " + cause_row,
        proof_md=proof,
    )
    return True


if __name__ == "__main__":
    run()
