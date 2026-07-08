"""INV-21 Resolution provenance (regolith/13-invariants.md).

Ledger statement:
    **Every number the designer did not write literally appears in the
    lockfile with its resolving cause.**

Mechanism provided by: WO-04 (the Cause-typed resolution API) + WO-19
(the lowering pipeline emits a Cause-typed resolution for every
non-literal value source it reaches). This module is part of the WO-17
invariant suite: the implementation's contract with the spec. A spec
change that alters INV-21's proof argument must change this module in
the same commit.

Positive property, now testable end-to-end: over the corpus, every
resolution the build emits carries one of the eight enumerated causes
(dfm/drc, obligation, budget, topology, planner, extern, derived-intent,
policy). The deliberate-violation direction (a causeless resolution)
stays unrepresentable by construction -- `Resolution` has no cause-less
constructor -- so there is nothing to negatively fixture.
"""

from __future__ import annotations

import json

from regolith import compiler

# The eight cause kinds INV-21 enumerates (serde snake_case tags).
_VALID_CAUSES = {
    "dfm",
    "drc",
    "obligation",
    "budget",
    "topology",
    "planner",
    "extern",
    "derived_intent",
    "policy",
}


def test_inv_21_every_resolution_carries_a_valid_cause() -> None:
    """Each resolution in the build payload names one of the eight
    enumerated causes; a causeless resolution is unrepresentable."""
    outcome = compiler.check(("examples/systems/cubesat",))
    assert outcome.is_ok
    payload = json.loads(outcome.danger_ok.payload_json)

    resolutions = payload["resolutions"]
    # The corpus is literal-heavy, but at least one non-literal value
    # source is lowered -- so this is a non-vacuous check.
    assert resolutions, "expected at least one resolved (non-literal) value"

    for resolution in resolutions:
        cause = resolution["cause"]
        assert cause["cause"] in _VALID_CAUSES, cause
        # The reference string is mandatory provenance (WHY it resolved).
        assert cause["ref"]
