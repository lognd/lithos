"""In-repo exercise of the WO-20 pack protocol + subprocess adapter.

Pins every WO-20 acceptance criterion: entry-point discovery and
end-to-end discharge through ``orchestrator.build`` over real source;
loud duplicate-model-id rejection (no partial load, named in the build
report); the subprocess solver's discharge and each adapter failure arm
mapping to ``harness.adapter_error`` INDETERMINATE (distinct from
violated, never an exception); and the AD-19/INV-1 extension -- a pack
version bump re-keys exactly its own evidence.
"""

from __future__ import annotations

from pathlib import Path

from regolith.harness import (
    ADAPTER_ERROR_ID,
    DischargeRequest,
    Interval,
    ModelRegistry,
    PackInfo,
    SubprocessSolverModel,
    default_registry,
    load_packs,
)
from regolith.harness.models import register_all
from regolith.harness.plugin import (
    BadRegisterSignature,
    DuplicateModelId,
    EntryPointRaised,
)
from regolith.orchestrator.cache import EvidenceStore, obligation_cache_key
from regolith.orchestrator.orchestrate import build
from regolith.orchestrator.tiers import BuildTier

from tests.packs import fixture_pack
from tests.packs.conformance import (
    FakeEntryPoint,
    assert_pack_conforms,
    registry_with_pack,
)

# -- shared fixtures --------------------------------------------------------

# A synthetic request the fixture pack's in-process echo model matches.
_ECHO_REQUEST = DischargeRequest(
    claim_kind=fixture_pack.ECHO_CLAIM_KIND,
    limit=100.0,
    inputs={"x": Interval(lo=1.0, hi=2.0)},
)

# A synthetic request the fixture pack's SUBPROCESS solver model matches.
_SOLVER_REQUEST = DischargeRequest(
    claim_kind=fixture_pack.SOLVER_CLAIM_KIND,
    limit=100.0,
    inputs={"x": Interval(lo=1.0, hi=2.0)},
)

# A `.hema` source whose lowered obligation the fixture pack discharges:
# the claim's lhs is the pack's claim kind and `loads:` pins its input.
_FIXTURE_SOURCE = (
    "part widget:\n"
    "    loads:\n"
    "        x: [1, 2]\n"
    "    require FixtureMetric:\n"
    f"        {fixture_pack.ECHO_CLAIM_KIND}: <= 100\n"
)


def _fixture_registry(version: str = "1.0.0") -> ModelRegistry:
    """Built-ins + the fixture pack at ``version`` via fake entry points."""
    return registry_with_pack("fixture", version, fixture_pack.register)


# -- discovery + composition (acceptance 1) ---------------------------------


def test_fixture_pack_passes_the_conformance_suite() -> None:
    """The in-repo fixture pack conforms to the pack protocol contract."""
    assert_pack_conforms(
        name="fixture",
        version="1.0.0",
        register=fixture_pack.register,
        request=_ECHO_REQUEST,
    )


def test_load_packs_composes_deterministically_sorted_by_name() -> None:
    """Packs merge after built-ins in sorted-by-name order (D-B).

    Built via `register_all` directly (not `default_registry`, which
    also discovers whatever REAL `regolith.model_packs` distributions
    happen to be installed in the environment -- feldspar, since
    WO-27): this test's built-in/pack split must stay exact regardless
    of what real packs are present on the machine running the suite.
    """
    registry = ModelRegistry()
    register_all(registry)
    outcome = load_packs(
        registry,
        entry_points_override=[
            FakeEntryPoint("zircon", "1.0", _register_named("zircon")),
            FakeEntryPoint("apatite", "1.0", _register_named("apatite")),
        ],
    )
    assert [p.name for p in outcome.loaded] == ["apatite", "zircon"]
    pack_models = [
        m
        for m in registry.all_models()
        if registry.pack_of(m.model_id)[0] != "regolith"
    ]
    assert [registry.pack_of(m.model_id)[0] for m in pack_models] == [
        "apatite",
        "zircon",
    ]


def _register_named(name: str) -> object:
    """A register callable adding one uniquely-named trivial model."""

    def _register(registry: ModelRegistry) -> None:
        spec = fixture_pack.solver_spec()
        renamed = spec.model_copy(
            update={"signature": spec.signature.model_copy(update={"name": name})}
        )
        registry.register(SubprocessSolverModel(renamed))

    return _register


def test_fixture_pack_discharges_end_to_end_via_build(tmp_path: Path) -> None:
    """Acceptance 1: a discovered pack's model discharges a real-source
    obligation through ``orchestrator.build``."""
    path = tmp_path / "widget.hema"
    path.write_text(_FIXTURE_SOURCE, encoding="ascii")
    report = build((str(path),), BuildTier.BUILD, registry=_fixture_registry())
    report_ok = report.danger_ok
    assert report_ok.obligations_discharged >= 1
    fixture_ids = [
        r.evidence.model_id
        for r in report_ok.results
        if r.evidence is not None and r.evidence.model_id.startswith("fixture.echo")
    ]
    assert fixture_ids, "the fixture pack's model must have produced the evidence"
    assert report_ok.pack_errors == ()


def test_duplicate_model_id_pack_is_rejected_loudly() -> None:
    """Acceptance 1: a duplicate-model-id pack is skipped with the named
    diagnostic; NO partial load; the build report names it."""
    registry = default_registry()
    outcome = load_packs(
        registry,
        entry_points_override=[
            FakeEntryPoint("fixture", "1.0.0", fixture_pack.register),
            # Sorted after "fixture"; collides with its echo model id.
            FakeEntryPoint("hostile", "9.9.9", fixture_pack.register_duplicate),
        ],
    )
    assert [p.name for p in outcome.loaded] == ["fixture"]
    assert len(outcome.skipped) == 1
    error = outcome.skipped[0]
    assert isinstance(error, DuplicateModelId)
    assert error.pack == "hostile"
    assert error.model_id == "fixture.echo@1.0.0"
    # No partial load: nothing in the registry is attributed to hostile.
    assert all(
        registry.pack_of(m.model_id)[0] != "hostile" for m in registry.all_models()
    )
    # Named in the build report surface (the registry carries it there).
    assert registry.pack_errors == (error,)


def test_raising_and_noncallable_packs_are_skipped_as_values() -> None:
    """A pack whose register raises, and one whose target is not callable,
    each become explicit PackLoadError values -- never exceptions."""
    registry = default_registry()
    outcome = load_packs(
        registry,
        entry_points_override=[
            FakeEntryPoint("broken", "0.1", fixture_pack.register_raising),
            FakeEntryPoint("wrong", "0.1", object()),
        ],
    )
    assert outcome.loaded == ()
    kinds = {type(e) for e in outcome.skipped}
    assert kinds == {EntryPointRaised, BadRegisterSignature}
    assert all(e.pack in {"broken", "wrong"} for e in outcome.skipped)


# -- subprocess adapter (acceptance 2) ---------------------------------------


def test_subprocess_solver_discharges_an_obligation() -> None:
    """Acceptance 2: the fixture SUBPROCESS solver discharges through the
    one shared margin rule, folding its solver_version."""
    registry = _fixture_registry()
    evidence = registry.discharge(_SOLVER_REQUEST)
    assert evidence.status.value == "discharged"
    assert evidence.model_id == "fixture.solver@1.0.0"


def test_adapter_failure_arms_are_indeterminate_adapter_error() -> None:
    """Acceptance 2: kill / timeout / garbage / version-skew / spawn
    failure each yield `harness.adapter_error` INDETERMINATE evidence --
    asserted distinct from violated -- and never raise."""
    failing_specs = {
        "nonzero exit": fixture_pack.solver_spec("exit2"),
        "timeout": fixture_pack.solver_spec("hang", timeout_s=0.5),
        "garbage stdout": fixture_pack.solver_spec("garbage"),
        "schema version skew": fixture_pack.solver_spec("bad-schema"),
        "spawn failure": fixture_pack.solver_spec().model_copy(
            update={"argv": ("/nonexistent/fixture-solver-binary",)}
        ),
    }
    for arm, spec in failing_specs.items():
        registry = ModelRegistry(version="model-registry@adapter-test")
        registry.register(SubprocessSolverModel(spec))
        evidence = registry.discharge(_SOLVER_REQUEST)
        assert evidence.model_id == ADAPTER_ERROR_ID, arm
        assert evidence.status.value == "indeterminate", arm
        assert evidence.status.value != "violated", arm


# -- AD-19 keying (acceptance 3, the INV-1 extension) -------------------------


def test_pack_version_bump_rekeys_only_its_own_evidence(tmp_path: Path) -> None:
    """Acceptance 3: bumping the fixture pack's version changes the
    evidence cache key AND evidence hash for ITS model's obligation, and
    leaves a built-in-discharged obligation's key/hash untouched."""
    fixture_src = tmp_path / "widget.hema"
    fixture_src.write_text(_FIXTURE_SOURCE, encoding="ascii")
    builtin_src = tmp_path / "beam.hema"
    builtin_src.write_text(
        "part flange:\n"
        "    loads:\n"
        "        force: [10, 20]\n"
        "        length: [0.1, 0.1]\n"
        "        e_modulus: [200e9, 200e9]\n"
        "        i_area: [1e-8, 1e-8]\n"
        "    require Deflection:\n"
        "        mech.beam.cantilever_deflection: <= 1\n",
        encoding="ascii",
    )

    def _run(version: str) -> dict[str, tuple[str, str]]:
        registry = _fixture_registry(version)
        keys: dict[str, tuple[str, str]] = {}
        cases = (
            ("fixture", fixture_src, "fixture.echo"),
            ("builtin", builtin_src, "beam_cantilever_deflection_eb"),
        )
        for name, src, model_prefix in cases:
            report = build((str(src),), BuildTier.BUILD, registry=registry).danger_ok
            matches = [
                r
                for r in report.results
                if r.evidence is not None
                and r.evidence.model_id.startswith(model_prefix)
            ]
            assert matches, f"no {model_prefix!r} evidence in the {name} build"
            evidence = matches[0].evidence
            assert evidence is not None
            keys[name] = (matches[0].key, evidence.hash)
        return keys

    v1, v2 = _run("1.0.0"), _run("2.0.0")
    # The fixture pack's evidence re-keys AND re-hashes on the bump ...
    assert v1["fixture"][0] != v2["fixture"][0], "cache key must fold pack version"
    assert v1["fixture"][1] != v2["fixture"][1], "evidence hash must fold pack version"
    # ... and no other: the built-in-discharged obligation is untouched.
    assert v1["builtin"] == v2["builtin"], "built-in evidence must not re-key"


def test_pack_version_bump_is_a_guaranteed_cache_miss() -> None:
    """The re-key is a real invalidation: evidence cached under pack v1
    is a MISS under v2 (stale pack evidence can never be reused)."""
    store = EvidenceStore()
    registry_v1 = _fixture_registry("1.0.0")

    from regolith._schema.models import (  # local: only this test builds one
        Claim,
        ClaimForm1,
        Form,
        Given,
        Obligation,
    )

    obligation = Obligation(
        claim=Claim(
            name=None,
            form=ClaimForm1(
                form=Form.comparison,
                lhs=fixture_pack.ECHO_CLAIM_KIND,
                op="<=",
                rhs="100",
            ),
            forall=[],
            hints=[],
        ),
        subject_ref="blake3:fixture",
        given=Given(materials=[], loads=["x: [1, 2]"], backing=[]),
        hints=[],
        sweep=None,
    )
    from regolith.orchestrator.discharge import discharge_one

    first = discharge_one(obligation, registry=registry_v1, store=store)
    assert first.from_cache is False
    again = discharge_one(obligation, registry=registry_v1, store=store)
    assert again.from_cache is True, "same pack version must be a cache hit"
    bumped = discharge_one(obligation, registry=_fixture_registry("2.0.0"), store=store)
    assert bumped.from_cache is False, "a pack bump must be a cache miss"
    assert bumped.key != first.key


def test_obligation_cache_key_folds_pack_identity_like_rust() -> None:
    """The Python key mirrors `Obligation::evidence_cache_key_for_pack`:
    the pack pair is a key input, defaulting to the built-in identity."""
    from regolith._schema.models import Claim, ClaimForm1, Form, Given, Obligation

    ob = Obligation(
        claim=Claim(
            name="stress",
            form=ClaimForm1(form=Form.comparison, lhs="stress", op="<", rhs="1"),
            forall=[],
            hints=[],
        ),
        subject_ref="blake3:aa",
        given=Given(materials=[], loads=[], backing=[]),
        hints=[],
        sweep=None,
    )
    rv = "model-registry@1"
    base = obligation_cache_key(ob, rv)
    assert base == obligation_cache_key(
        ob, rv, pack_name="regolith", pack_version=rv
    ), "the default key is the pack-aware key at the built-in identity"
    assert base != obligation_cache_key(ob, rv, pack_name="fixture", pack_version="1")
    assert obligation_cache_key(
        ob, rv, pack_name="fixture", pack_version="1"
    ) != obligation_cache_key(ob, rv, pack_name="fixture", pack_version="2")


# -- discovery record ---------------------------------------------------------


def test_loaded_pack_info_is_recorded_on_the_registry() -> None:
    """`default_registry`-style composition records PackInfo for reports."""
    registry = _fixture_registry("3.2.1")
    assert PackInfo(name="fixture", version="3.2.1") in registry.packs
    assert registry.pack_errors == ()
