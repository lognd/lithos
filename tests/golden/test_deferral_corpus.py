"""Deferral-list golden: every corpus obligation's `orchestrator.translate`
outcome, asserted as data (WO-26 acceptance).

Each claim-form lowering step (unit-suffix resolution, `within [lo, hi]`
windows, ...) either turns a named obligation's deferral into a resolvable
`DischargeRequest` or leaves it deferred for a NAMED, honest reason. This
suite makes both directions loud: a claim that starts discharging silently
shrinks the deferral list (progress, reviewed in the golden diff); a claim
that stops discharging grows it back (a regression the diff also catches).
It is deliberately a SEPARATE golden from `test_golden_corpus.py` (which
freezes the compiler's structural output) -- this one freezes the
orchestrator's lowering behavior over the same corpus.

Regeneration: never hand-edit. Run
`REGOLITH_UPDATE_GOLDEN=1 pytest tests/golden/test_deferral_corpus.py`
and diff-review the change like any other generated artifact.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from regolith import compiler
from regolith._schema.models import Obligation
from regolith.orchestrator.frame_resolve import load_frame_context
from regolith.orchestrator.translate import translate

from .test_golden_corpus import _SDR_CLEAN_PATHS

_DATA_DIR = Path(__file__).parent / "data"

# Kept in step with `test_golden_corpus.py`'s corpus selection (AD-11: this
# suite also runs in the default `make check` gate, so it stays cheap) plus
# the full cubesat system, which carries the corpus's richest claim-form mix
# (within-windows, unit-suffixed bounds, the Kestrel dB link claim).
_CORPUS: dict[str, tuple[str, ...]] = {
    "cubesat": ("examples/systems/cubesat",),
    "gear_reducer": ("examples/tracks/hematite/gear_reducer.hema",),
    "buck_converter": ("examples/tracks/cuprite/buck_converter.cupr",),
    # Cycle-23 stress corpus (D119/D120) -- selection shared with the
    # golden suite so the two corpora cannot drift apart.
    "sdr_transceiver": _SDR_CLEAN_PATHS,
    "hdl": ("examples/hdl",),
    # Cycle-23 stress corpus (D119) -- selection shared with the golden
    # suite so the two corpora cannot drift apart.
    "cnc_router": ("examples/systems/cnc_router",),
    # Cycle-23 stress corpus (D119) -- selection shared with the golden
    # suite so the two corpora cannot drift apart.
    "espresso_machine": ("examples/systems/espresso_machine",),
    # WO-33 deliverable 5: the honest indeterminate-chain property --
    # a compute claim (the field producer) defers as `non_scalar_claim`
    # and its sibling projection (the consumer) defers as
    # `unsupported_op`, never a silent discharge. Same selection as
    # the structural golden above so the two corpora cannot drift
    # apart.
    "regen_chamber": ("examples/tracks/hematite/regen_chamber.hema",),
    "suspension_link": ("examples/tracks/hematite/suspension_link.hema",),
    # D148 follow-up (cycle 27) -- selection shared with the golden
    # suite so the two corpora cannot drift apart.
    "manifold": ("examples/tracks/hematite/manifold.hema",),
    "dune_buggy": ("examples/systems/dune_buggy",),
    # WO-28 deliverable 6 -- selection shared with the golden suite:
    # the deferred rule obligations (hole edge distance awaiting the
    # WO-22 measured facts; bend relief behind its `.where` filter)
    # frozen as honest indeterminates.
    "sheet_bracket": (
        "examples/tracks/hematite/sheet_bracket.hema",
        "examples/tracks/hematite/std_sheet_metal.hema",
    ),
    # WO-48 close-out follow-up (frame-chain completion, cycle 28/29):
    # the five ratified calcite corpus designs, now translated WITH a
    # `frame_context` (std.civil section/material resolution) threaded
    # in, unlike every other entry above (frame-less corpora pass
    # `frame_context=None` harmlessly -- `load_frame_context` returns
    # `Ok(None)` for any build whose payload carries no `frames`).
    # Every one of these designs' `civil.utilization`/`mech.deflection`
    # claims stays indeterminate, but the reasons are now SPECIFIC
    # (`frame_section_free`, `frame_member_not_found`, `no_frame_model`)
    # rather than the pre-resolution blanket `unsupported_op` -- see
    # the WO-48 cut ledger's "frame-chain completion" section for why a
    # real numeric verdict is not reachable for this corpus (every
    # deflection-governing member is a `section: free` L3 search
    # variable).
    "footbridge": ("examples/tracks/calcite/footbridge.calx",),
    "bus_shelter": ("examples/tracks/calcite/bus_shelter.calx",),
    "pole_barn": ("examples/tracks/calcite/pole_barn.calx",),
    "retaining_wall": ("examples/tracks/calcite/retaining_wall.calx",),
    "small_office": ("examples/systems/small_office",),
}

# std.civil section/material record search path for the calcite corpus
# entries' `frame_context` (the same relative-to-cwd posture
# `test_pattern_libraries.py`/`test_cost_build.py` already use for
# `stdlib/`).
_STDLIB_PATH: tuple[str, ...] = ("stdlib",)


def _golden_path(name: str) -> Path:
    return _DATA_DIR / f"deferral_{name}.json"


def _deferral_snapshot(paths: tuple[str, ...]) -> list[dict[str, object]]:
    """One entry per obligation: its claim name/op and the translate verdict.

    Threads a `frame_context` (WO-48 close-out follow-up) built from
    this build's own payload + `stdlib/`'s std.civil records for every
    corpus entry -- harmless (`Ok(None)`) for a build with no `frames`.
    """
    result = compiler.check(paths)
    assert result.is_ok, f"check({paths!r}) returned Err: {result}"
    payload = json.loads(result.danger_ok.payload_json)
    frame_ctx_result = load_frame_context(
        ".", build_payload=payload, record_search_paths=_STDLIB_PATH
    )
    assert frame_ctx_result.is_ok, frame_ctx_result
    frame_context = frame_ctx_result.danger_ok
    entries: list[dict[str, object]] = []
    for raw in payload["obligations"]:
        obligation = Obligation.model_validate(raw)
        lowered = translate(obligation, frame_context=frame_context)
        if lowered.is_ok:
            request = lowered.danger_ok
            verdict: dict[str, object] = {
                "status": "lowered",
                "claim_kind": request.claim_kind,
                "limit": request.limit,
            }
        else:
            deferral = lowered.danger_err
            verdict = {"status": "deferred", "reason": deferral.reason}
        entries.append(
            {
                "name": obligation.claim.name,
                "op": obligation.claim.form.op
                if hasattr(obligation.claim.form, "op")
                else None,
                "verdict": verdict,
            }
        )
    entries.sort(key=lambda e: (str(e["name"]), str(e["op"])))
    return entries


@pytest.mark.parametrize("name", sorted(_CORPUS))
def test_deferral_corpus(name: str) -> None:
    """Current lowering behavior for one corpus member matches its golden."""
    snapshot = _deferral_snapshot(_CORPUS[name])
    golden_path = _golden_path(name)

    if os.environ.get("REGOLITH_UPDATE_GOLDEN") == "1":
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
        pytest.skip(f"REGOLITH_UPDATE_GOLDEN=1: rewrote {golden_path}")

    assert golden_path.exists(), (
        f"no golden file at {golden_path}; regenerate with REGOLITH_UPDATE_GOLDEN=1"
    )
    expected = json.loads(golden_path.read_text())
    assert snapshot == expected, (
        f"deferral-list drift for {name!r} -- if this is an intended lowering "
        "change (progress OR regression), regenerate with "
        "REGOLITH_UPDATE_GOLDEN=1 and review the diff honestly"
    )
