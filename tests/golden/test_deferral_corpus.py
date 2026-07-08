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
from regolith.orchestrator.translate import translate

_DATA_DIR = Path(__file__).parent / "data"

# Kept in step with `test_golden_corpus.py`'s corpus selection (AD-11: this
# suite also runs in the default `make check` gate, so it stays cheap) plus
# the full cubesat system, which carries the corpus's richest claim-form mix
# (within-windows, unit-suffixed bounds, the Kestrel dB link claim).
_CORPUS: dict[str, tuple[str, ...]] = {
    "cubesat": ("examples/cubesat",),
    "gear_reducer": ("examples/mech/gear_reducer.hema",),
    "buck_converter": ("examples/elec/buck_converter.cupr",),
}


def _golden_path(name: str) -> Path:
    return _DATA_DIR / f"deferral_{name}.json"


def _deferral_snapshot(paths: tuple[str, ...]) -> list[dict[str, object]]:
    """One entry per obligation: its claim name/op and the translate verdict."""
    result = compiler.check(paths)
    assert result.is_ok, f"check({paths!r}) returned Err: {result}"
    payload = json.loads(result.danger_ok.payload_json)
    entries: list[dict[str, object]] = []
    for raw in payload["obligations"]:
        obligation = Obligation.model_validate(raw)
        lowered = translate(obligation)
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
