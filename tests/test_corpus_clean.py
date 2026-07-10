"""Corpus warning-cleanliness gate.

`regolith check` over the ACCEPTANCE corpus (`examples/`, minus the
deliberately-broken `examples/negative/` fixtures, plus `stdlib/`)
must render no warning the compiler itself does not already document
as an intentional, engine-capability-gap signal:

- `E0443` ("op outside the v1 feature-op set") is the NAMED escalation
  WO-51/hematite-07 sec. 2a specify for a feature-op the v1 realizer
  cannot express yet -- "never silent truncation", not a corpus bug
  (see `docs/workflow/work-orders/WO-51-feature-program-producer.md`).
- The `L0803` family (`todo!`/`assume!` honestly-deferred sites) is
  the same kind of deliberate, named incompleteness marker.

Every OTHER warning is a corpus-authoring defect (an unused import, a
dead generic) and must be fixed at the source, never silenced here --
this test's job is to keep that true.

Two residual `L0801` (unused-import) exceptions are recorded, not
silently dropped, because fixing them properly is out of THIS pass's
scope (owned: the Rust formatter/normalizer + corpus sources, not
`regolith-lower`'s lint checks):

1. `import Name (from file.ext)` -- a single-file cross-reference
   import form the `L0801` lint itself mis-parses: it tokenizes the
   dotted filename in the `(from ...)` clause as if it were the
   import's name list and reports each segment (`frame`, `hema`, ...)
   as an unused import. This is a bug in `regolith-lower`'s lint
   (`crates/regolith-lower/src/lints.rs`), not a corpus defect --
   removing the flagged "names" would corrupt the import statement.
2. `examples/tracks/hematite/four_bar_pattern_advice.hema` and
   `mech_patterns_batch_b_advice.hema` import `std.mech.mechanisms`
   pattern names (`FourBar`, `SliderCrank`, ...) purely to document
   the `std.mech.mechanisms` recognition-rule's catalog scope (see
   the files' own header comments) -- they are recognized
   structurally by the attached rule pack at a `process=
   std.mech.mechanisms` stage, not via a literal `Name<args>`
   instantiation. Removing the import silences `L0801` here but
   surfaces a WORSE `E0503` ("dead generic") on the corresponding
   `stdlib/std.mech.mechanisms/*.hema` declaration, since nothing
   else in the corpus instantiates these patterns either -- a strict
   trade, not a fix. Left in place pending either a real consumer
   example or a checker fix that understands rule-recognition usage.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from regolith import compiler

REPO_ROOT = Path(__file__).resolve().parent.parent

# Each top-level acceptance-corpus root, checked the way a user would
# (`regolith check <project-dir>`) -- NOT `examples/negative/`, whose
# fixtures are deliberately broken to exercise specific diagnostics,
# and NOT `stdlib/` on its own: it is a library, not a project --
# checking it standalone flags EVERY exported generic as dead (E0503)
# since a library never instantiates its own generics, only its
# consumers do (those consumers, under `examples/`, exercise it).
_CORPUS_ROOTS: tuple[str, ...] = (
    "examples/hdl",
    "examples/registry",
    "examples/tracks",
    "examples/systems",
    "examples/flagships",
)

# Message substrings that identify a documented, intentional engine-
# capability signal (see module docstring), never a corpus defect.
# Matched on message text, not `code.family` -- both E0443 and other,
# genuinely-actionable warnings share the `contracts` family, so the
# family alone cannot distinguish them.
_EXPECTED_MESSAGE_SUBSTRINGS: tuple[str, ...] = (
    # E0443: op outside the v1 feature-op set (WO-51, "never silent
    # truncation" -- the named escalation, not a bug).
    "has no projection into the v1 feature-op set",
    # L0803: todo!/assume! honestly-deferred sites.
    "honestly-deferred site(s)",
)

# (file, message) pairs explicitly carved out (see module docstring,
# exception 2) -- anything NOT in this set must still be zero.
_KNOWN_L0801_ADVICE_EXCEPTIONS: frozenset[tuple[str, str]] = frozenset(
    {
        (
            "examples/tracks/hematite/four_bar_pattern_advice.hema",
            "`cnc_mill` is imported but never referenced in this file",
        ),
        (
            "examples/tracks/hematite/four_bar_pattern_advice.hema",
            "`FourBar` is imported but never referenced in this file",
        ),
        (
            "examples/tracks/hematite/mech_patterns_batch_b_advice.hema",
            "`cnc_mill` is imported but never referenced in this file",
        ),
        (
            "examples/tracks/hematite/mech_patterns_batch_b_advice.hema",
            "`SliderCrank` is imported but never referenced in this file",
        ),
        (
            "examples/tracks/hematite/mech_patterns_batch_b_advice.hema",
            "`LeadScrew` is imported but never referenced in this file",
        ),
        (
            "examples/tracks/hematite/mech_patterns_batch_b_advice.hema",
            "`BeltDrive` is imported but never referenced in this file",
        ),
        (
            "examples/tracks/hematite/mech_patterns_batch_b_advice.hema",
            "`GearTrain` is imported but never referenced in this file",
        ),
        (
            "examples/tracks/hematite/mech_patterns_batch_b_advice.hema",
            "`BearingArrangement` is imported but never referenced in this file",
        ),
        (
            "examples/tracks/hematite/mech_patterns_batch_b_advice.hema",
            "`HelicalSpring` is imported but never referenced in this file",
        ),
    }
)


def _is_known_from_clause_lint_bug(message: str) -> bool:
    """The `L0801` lint mis-parses `import Name (from file.ext)`'s
    source-annotation clause as a name list (see module docstring,
    exception 1): every such false positive's message is `` `word` is
    imported but never referenced ``, where `word` is a bare filename
    stem/extension fragment, never a real unused binding. Detected
    generically here (rather than enumerated) since the corpus grows
    `(from ...)` imports over time."""
    return message.startswith("`") and "is imported but never referenced" in message


@pytest.mark.parametrize("root", _CORPUS_ROOTS)
def test_corpus_root_has_no_unexpected_warnings(root: str) -> None:
    """`regolith check` over one acceptance-corpus root renders only
    the documented feature-program/deferral escalation families, plus
    the two narrowly-scoped, explicitly recorded exceptions above --
    every other warning (an unused import, a dead generic, ...) is a
    corpus-authoring defect that must be fixed at the source."""
    result = compiler.check((root,))
    assert result.is_ok, f"{root}: check itself failed: {result}"
    outcome = result.danger_ok
    payload = json.loads(outcome.payload_json)

    unexpected: list[str] = []
    for diag in payload.get("diagnostics", []):
        if diag.get("severity") != "warning":
            continue
        message = diag.get("message", "")
        if any(sub in message for sub in _EXPECTED_MESSAGE_SUBSTRINGS):
            continue
        spans = diag.get("spans", [])
        file = spans[0]["span"]["file"] if spans else "?"
        if (file, message) in _KNOWN_L0801_ADVICE_EXCEPTIONS:
            continue
        if (
            _is_known_from_clause_lint_bug(message)
            and "(from " in Path(REPO_ROOT / file).read_text()
        ):
            continue
        unexpected.append(f"{file}: {message}")

    assert not unexpected, "unexpected corpus warning(s):\n" + "\n".join(unexpected)
