"""INV-10 Reproducibility (substrate/13-invariants.md).

Ledger statement:
    **Given (source, lockfile, tool versions): all decisions and evidence
    identities are bit-reproducible; numerical evidence values are
    reproducible per each model's declared `deterministic:` flag, with
    seeds/settings folded into evidence hash inputs otherwise.**

Mechanism provided by: WO-19 (the `regolith-lower` pipeline is a pure
function of source text -- no IO, no `Err`, sorted file order,
canonical snapshot hashing per AD-18). This module is part of the
WO-17 invariant suite: the implementation's contract with the spec. A
spec change that alters INV-10's proof argument must change this
module in the same commit.

Test (ledger): double-build diff on lockfile + evidence keys. Here:
two independent `check()` calls over `examples/cubesat/` through the
facade must agree byte-for-byte on `payload_json` and on the derived
obligation-key set.
"""

from __future__ import annotations

import json

from regolith import compiler

from tests.golden import _util


def test_inv_10_double_build_is_byte_identical() -> None:
    """Two independent `check()` calls over the same corpus produce
    byte-identical `payload_json` -- the strongest form of the
    reproducibility guarantee available at the facade boundary."""
    first = compiler.check(("examples/cubesat",))
    second = compiler.check(("examples/cubesat",))

    assert first.is_ok
    assert second.is_ok

    first_outcome = first.danger_ok
    second_outcome = second.danger_ok

    assert first_outcome.payload_json == second_outcome.payload_json
    assert first_outcome.ok == second_outcome.ok
    assert first_outcome.rendered == second_outcome.rendered


def test_inv_10_obligation_keys_are_stable_across_builds() -> None:
    """Obligation identity (INV-1's content-addressed key) must not
    wobble between two builds of identical input -- a narrower check
    than byte-identity, phrased in terms of the decision identities
    the ledger statement calls out explicitly."""
    first = compiler.check(("examples/cubesat",)).danger_ok
    second = compiler.check(("examples/cubesat",)).danger_ok

    first_keys = _util.obligation_keys(json.loads(first.payload_json))
    second_keys = _util.obligation_keys(json.loads(second.payload_json))

    assert first_keys
    assert first_keys == second_keys
