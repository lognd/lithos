"""WO-83 slice A acceptance: the `test <name>:` grammar/CST + the
lowering surface that exposes parsed test declarations to Python.

Charter `docs/spec/toolchain/37-design-testing.md` (D190) names the
five `expect:` forms and the scenario vocabulary; this WO's slice A is
grammar + lowering only -- the runner (`regolith test`, deliverable 3)
is a separate later dispatch (slice B). This test proves the proof bar
stated in the WO: the `examples/tracks/hematite/spar_bracket_wo83.
test.hema` fixture parses, and its lowered structure round-trips
through `compiler.check` to Python as `BuildPayload.tests` (a new
SCHEMA_VERSION field/type, per the D168 train rule -- taken, not
deferred, since no existing generic declaration surface carried this).
"""

from __future__ import annotations

import json

from regolith import compiler
from regolith._schema.models import TestDeclPayload, TestExpectationPayload

FIXTURE_DIR = "examples/tracks/hematite"


def test_test_decl_lowers_and_round_trips_to_python() -> None:
    """`check()` over the WO-83 fixture pair surfaces one `TestDeclPayload`
    whose scenario/expect structure matches what the source declares."""
    result = compiler.check((FIXTURE_DIR,))
    assert result.is_ok, result
    outcome = result.danger_ok

    payload = json.loads(outcome.payload_json)
    tests_raw = payload["tests"]
    assert isinstance(tests_raw, list)

    matches = [t for t in tests_raw if t["name"] == "mount_bore_case"]
    assert len(matches) == 1, tests_raw
    test_entry = matches[0]

    # Round-trips into the generated pydantic model (AD-5 -- the
    # payload's WIRE shape is exactly the schema this WO bumped for).
    decl = TestDeclPayload.model_validate(test_entry)
    assert decl.name == "mount_bore_case"
    assert decl.subject_file.endswith("spar_bracket_wo83.test.hema")

    # `scenario:`'s three declared entries (locked pin, seed, budget).
    assert len(decl.scenario_entries) == 3
    assert any(e.startswith("locked: material") for e in decl.scenario_entries)
    assert any(e.startswith("seed = 7") for e in decl.scenario_entries)
    assert any(e.startswith("budget_evals = 20") for e in decl.scenario_entries)

    # `expect:`'s five forms (charter 37 sec. 1), in source order.
    assert [e.form for e in decl.expectations] == [
        "diagnostic",
        "verdict",
        "value",
        "count",
        "winner",
    ]
    assert isinstance(decl.expectations[0], TestExpectationPayload)
    assert decl.expectations[0].tail == "E0501 on SparBracket.mount"
    assert decl.expectations[1].tail == "Structural.mount_dia = discharged"
    assert decl.expectations[2].tail == "mount.dia within [5mm, 6.5mm] cause bearing"
    assert decl.expectations[3].tail == "SparBracket.holes = 1"
    assert (
        decl.expectations[4].tail
        == "mount.section = registry(std.fasteners.m6_clearance)"
    )


def test_test_file_discovery_extension_is_the_one_registry() -> None:
    """The `.test.<ext>` discovery convention is registered in
    `regolith-syntax`'s ONE extension registry -- proven here by asking
    the real compiled core to recognize the fixture pair via an
    ordinary directory check (no second copy of the convention on the
    Python side, per the tripwire)."""
    result = compiler.check((f"{FIXTURE_DIR}/spar_bracket_wo83.test.hema",))
    assert result.is_ok, result
    outcome = result.danger_ok
    payload = json.loads(outcome.payload_json)
    assert any(t["name"] == "mount_bore_case" for t in payload["tests"])
