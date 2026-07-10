"""WO-62 D171/AD-32 deliverable 3: the feature-coverage ledger.

The mech realizer's honesty posture (WO-22: "a partial solid is
unrepresentable") extends from per-part deferral to a PUBLISHED,
drift-checked capability surface: for every hematite `then:`
constructor word the corpus spells, is it one the v1 op set REALIZES
or a NAMED skip (Rust `regolith-lower::feature_program::project_op`
emits `E0443`, contracts family offset 43, naming the exact
constructor)? An op outside this ledger is never silently truncated --
`E0443` always names it -- but the ledger is what "declarative mech
may claim to realize" IS, per the charter (`docs/spec/toolchain/
30-geometry-lowering.md` sec. 1 item 3): coverage growth is a
reviewable ledger diff, never silent interpreter drift.

Single source of truth: `regolith-sem::EntityKind::from_constructor_word`
(the Hole/Bend constructor-word lists) plus `regolith-lower::
feature_program::project_op`'s literal `"Blank"`/`"Pocket"` arms (Rust,
AD-2 layering -- this Python module does not re-derive it, it MIRRORS
it as committed data, same posture as `python/regolith/_schema/`
mirroring the Rust schemars export). The realizes/skips split below is
verified against a LIVE run of the real compiler over the full corpus
by `tests/realizer/mech/test_coverage.py` (the schema-check pattern
applied to capability, WO-62 d3): that test's derivation is the
"derived from code" half, this ledger is the "committed" half, and a
diff between them is a definitional drift.
"""

from __future__ import annotations

#: Constructor word -> outcome. `"realizes"` op classes are the v1
#: FeatureProgram projection surface (`regolith-lower::feature_program
#: ::project_op`): hole-shaped constructors (`regolith-sem::EntityKind
#: ::from_constructor_word`'s Hole arm), `Bend` (its Bend arm), and the
#: literal `Blank`/`Pocket` profile-consumer rows (WO-51). Every other
#: entry is a named skip -- `"skips(E0443)"` -- for a constructor the
#: real corpus (`examples/`) currently spells outside that set; each
#: was independently confirmed reachable by
#: `tests/realizer/mech/test_coverage.py::
#: test_ledger_matches_the_live_corpus_derivation`.
FEATURE_COVERAGE_LEDGER: dict[str, str] = {
    # Hole-shaped (regolith-sem EntityKind::Hole constructor words).
    "Bore": "realizes",
    "CBore": "realizes",
    "Drill": "realizes",
    "Ream": "realizes",
    "Pierce": "realizes",
    "CSink": "realizes",
    "Countersink": "realizes",
    "ThreadedHole": "realizes",
    "TappedHole": "realizes",
    "Tap": "realizes",
    "PilotHole": "realizes",
    # Sheet forming (regolith-sem EntityKind::Bend).
    "Bend": "realizes",
    # Profile consumers (WO-51 literal project_op arms).
    "Blank": "realizes",
    "Pocket": "realizes",
    # Named skips: every constructor the current corpus spells outside
    # the v1 op set (WO-62 d3 acceptance -- every corpus skip listed).
    "Boss": "skips(E0443)",
    "Casting": "skips(E0443)",
    "Chamfer": "skips(E0443)",
    "Contour": "skips(E0443)",
    "Disk": "skips(E0443)",
    "Draft": "skips(E0443)",
    "Face": "skips(E0443)",
    "FaceMill": "skips(E0443)",
    "FacePad": "skips(E0443)",
    # WO-90: multi-line weld constructor calls now capture whole (the
    # bracket-continuation fix), so they reach the feature-op projection
    # and skip honestly (E0443) as recognized-but-unsupported ops instead
    # of being truncated fragments.
    "FilletWeld": "skips(E0443)",
    "FlyWeight": "skips(E0443)",
    "ForgedBlank": "skips(E0443)",
    "GrooveWeld": "skips(E0443)",
    "HelicalCompression": "skips(E0443)",
    "Hem": "skips(E0443)",
    "Journal": "skips(E0443)",
    "Keyseat": "skips(E0443)",
    "Mirror": "skips(E0443)",
    "Notch": "skips(E0443)",
    "RackPinion": "skips(E0443)",
    "Rib": "skips(E0443)",
    "Shaft": "skips(E0443)",
    "Sheave": "skips(E0443)",
    "Slot": "skips(E0443)",
    "Spline": "skips(E0443)",
    "SpunRim": "skips(E0443)",
    "SpurGear": "skips(E0443)",
    "SurfaceHarden": "skips(E0443)",
    "Taper": "skips(E0443)",
    "Thread": "skips(E0443)",
    "Turn": "skips(E0443)",
    "Wall": "skips(E0443)",
    "Weld": "skips(E0443)",
    "fixture": "skips(E0443)",
}

#: Constructor words the v1 `FeatureProgram` projection realizes.
SUPPORTED_CTORS: frozenset[str] = frozenset(
    ctor for ctor, outcome in FEATURE_COVERAGE_LEDGER.items() if outcome == "realizes"
)

#: Constructor words the current corpus spells that the v1 set names
#: as an honest skip (`E0443`).
SKIPPED_CTORS: frozenset[str] = frozenset(
    ctor for ctor, outcome in FEATURE_COVERAGE_LEDGER.items() if outcome != "realizes"
)
