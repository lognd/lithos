"""Demo 5 -- bounded sketch-segment slot: WingSpar margin search (WO-97/D209).

A `b.length = in [lo, hi] minimize` slot promotes to a bounded
sketch-segment closure across the corpus (WO-97 promotion half, LANDED),
but the optimizer STEP-coupling is honestly DEFERRED everywhere: per
D209 the bounded-slot evaluator IS the discharge pipeline specialized
per candidate, and EVERY bounded-slot part's governing structural claim
(`mech.stress.von_mises`, `mech.deflection`) defers `no_model` -- there
is no registered structural model, so the search cannot pin a genuine
`optimize(...)` value (WO-97 E1; F125). D218.3 lands that model channel
+ the coupling in a PARALLEL dispatch.

This demo is wired behind a capability probe. Until the structural model
channel + coupling land it records an honest gap (nonzero under
`make demos-strict`). The moment a bounded-slot part pins to
`optimize(...)`, the live path emits the optimizer-pinned STEP + drawing
with no further edit.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from regolith.logging_setup import get_logger

from demos.harness import DemoWriter, REPO_ROOT, gap_proof

_log = get_logger(__name__)

DEMO = "demo5_bounded_slot"
SURFACE = "bounded sketch-segment slot sized by a real margin search (WingSpar, WO-97/D209)"
# The first coupled target (WO-97 close-out ledger): uav_talon's
# WingSpar.SparCapFlat.b in [3mm, 8mm].
PROJECT = REPO_ROOT / "examples" / "flagships" / "uav_talon"
# The E1-named governing structural claim kinds a bounded-slot part
# carries; the coupling is live once a model is registered for one.
_GOVERNING_KINDS = ("mech.stress.von_mises", "mech.deflection")
_OPT_CAUSE_RE = re.compile(r"cause:\s*optimize\(")


def _structural_model_registered() -> bool:
    """Probe: is a model registered for a bounded-slot governing claim?

    E1's decisive finding: the coupling can pin a value ONLY once a
    structural-claim model exists. This flips to True the moment the
    parallel D218.3 dispatch registers that channel.
    """
    try:
        from regolith.harness.registry import default_registry
    except ImportError:
        return False
    kinds = {k for k, _ in default_registry().registered_keys()}
    return any(k in kinds for k in _GOVERNING_KINDS)


def _try_live(writer: DemoWriter) -> bool:
    """The wired live path: build the bounded-slot flagship (a copy, so no
    corpus write) and, if a bounded slot pinned to `optimize(...)`, emit
    the optimizer-pinned STEP. Falls back to an honest gap otherwise."""
    from regolith.orchestrator.orchestrate import build
    from regolith.orchestrator.tiers import BuildTier

    work = writer.out_dir / "src"
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(PROJECT, work)
    report = build((str(work),), BuildTier.BUILD).danger_ok
    rendered = report.rendered
    if not _OPT_CAUSE_RE.search(rendered):
        gap_proof(
            writer,
            surface=SURFACE,
            optimized_quantity="slot value (SparCapFlat.b)",
            domain="uav_talon WingSpar bounded sketch-segment [3mm, 8mm]",
            blocked_on="WO-97 D209 coupling (structural model channel, F126.1)",
            detail=(
                "A structural model is registered, but the bounded-slot build "
                "still produced no `cause: optimize(...)` pin -- the coupling "
                "wiring is not yet complete. No fabricated STEP is emitted."
            ),
        )
        return False
    # (Live coupling present: a bounded slot pinned. The persisted preview
    # STEP for the coupled part is the physical proof; emit it verbatim.)
    payload = json.loads(report.payload_json)
    writer.emit("build_report.json", json.dumps(payload, sort_keys=True).encode("ascii"))
    writer.finish(
        live=True,
        optimized_quantity="slot value (SparCapFlat.b)",
        domain="uav_talon WingSpar bounded sketch-segment [3mm, 8mm]",
        winner="(pinned; see build_report.json optimize row)",
        cause_row=next(
            line.strip()
            for line in rendered.splitlines()
            if _OPT_CAUSE_RE.search(line)
        ),
        proof_md=(
            f"# PROOF: {SURFACE}\n\n"
            "The WO-97 D209 coupling is live: a bounded sketch-segment slot "
            "pinned to a real `optimize(...)` value from the discharge "
            "pipeline specialized per candidate. See `build_report.json`.\n"
        ),
    )
    return True


def run() -> bool:
    """Emit the bounded-slot proof pack; return True iff live."""
    writer = DemoWriter(DEMO, SURFACE)
    if not _structural_model_registered():
        gap_proof(
            writer,
            surface=SURFACE,
            optimized_quantity="slot value (SparCapFlat.b)",
            domain="uav_talon WingSpar bounded sketch-segment [3mm, 8mm]",
            blocked_on="WO-97 D209 coupling + structural model channel (F125/F126.1)",
            detail=(
                "The bounded slot promotes to a `SegmentLength::Bounded` closure "
                "(WO-97 promotion half, landed), but D209's per-candidate "
                "evaluator IS the discharge pipeline, and every bounded-slot "
                "part's governing structural claim (mech.stress.von_mises / "
                "mech.deflection) defers `no_model`: none of "
                f"{list(_GOVERNING_KINDS)} is a registered model kind on the "
                "installed core. So no part can be pinned to a genuine "
                "optimize(...) value yet (WO-97 E1). This probe flips to the "
                "live path the moment that structural model channel + the D209 "
                "coupling land in the parallel D218.3 dispatch."
            ),
        )
        return False
    return _try_live(writer)


if __name__ == "__main__":
    run()
