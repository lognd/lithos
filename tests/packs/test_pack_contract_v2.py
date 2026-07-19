"""WO-30 pack contract v2 conformance suite (D94-D97, sec. 8).

Exercises the four contract gaps together with the fixture pack: kind
competition (D94), structured coverage (D95), the payload-ref channel
(D96), and given-resolution + regime tags (D97). These are the cases
feldspar runs from outside (WO-30 deliverable 5).
"""

from __future__ import annotations

from pathlib import Path

from regolith._schema.models import (
    Claim,
    ClaimForm1,
    CoverageAxis,
    CoverageDomain1,
    CoverageDomain2,
    CoverageMethod2,
    CoverageMethod3,
    Form,
    Given,
    Grid,
    KItem,
    Obligation,
    PayloadRef,
    Values,
)
from regolith.harness import (
    ClaimSense,
    DischargeRequest,
    Interval,
    Model,
    ModelRegistry,
    ModelSignature,
    Prediction,
    default_registry,
    load_packs,
)
from regolith.harness.errors import HarnessError
from regolith.harness.registry import NO_MODEL_ID, method_named_kind_violation
from regolith.orchestrator.cache import EvidenceStore
from regolith.orchestrator.discharge import discharge_one
from regolith.orchestrator.payload_store import PayloadStore, resolve_request_payloads
from regolith.orchestrator.translate import translate
from typani.result import Ok, Result

from tests.packs import fixture_pack
from tests.packs.conformance import FakeEntryPoint, registry_with_pack

# -- D94: kind competition ----------------------------------------------------


def test_one_model_registers_under_two_claim_kinds() -> None:
    """A model registered under TWO kinds discharges obligations of both."""
    registry = registry_with_pack("two_kind", "1.0.0", fixture_pack.register_two_kind)
    for kind in (
        fixture_pack.TWO_KIND_CLAIM_KIND_A,
        fixture_pack.TWO_KIND_CLAIM_KIND_B,
    ):
        request = DischargeRequest(
            claim_kind=kind, limit=100.0, inputs={"x": Interval(lo=1.0, hi=2.0)}
        )
        evidence = registry.discharge(request)
        assert evidence.status.value == "discharged", kind
        assert evidence.model_id.startswith("fixture.two_kind"), kind


def test_same_id_under_one_kind_twice_is_still_an_error() -> None:
    """Registering two DIFFERENT models with one id under ONE kind errors."""
    registry = default_registry()
    outcome = load_packs(
        registry,
        entry_points_override=[
            FakeEntryPoint(
                "hostile_same_kind",
                "1.0",
                fixture_pack.register_two_kind_same_kind_duplicate,
            )
        ],
    )
    assert outcome.loaded == ()
    assert len(outcome.skipped) == 1


# frob:tests python/regolith/harness/registry.py::method_named_kind_violation
def test_method_named_kind_is_rejected_with_the_offending_word() -> None:
    """D94: `mech.fea.static_stress` fails the lint, naming `fea`."""
    assert method_named_kind_violation("mech.fea.static_stress") == "fea"
    assert method_named_kind_violation("mech.static_stress") is None

    registry = default_registry()
    outcome = load_packs(
        registry,
        entry_points_override=[
            FakeEntryPoint(
                "hostile_method_kind", "1.0", fixture_pack.register_method_named_kind
            )
        ],
    )
    assert outcome.loaded == ()
    assert len(outcome.skipped) == 1
    error = outcome.skipped[0]
    assert getattr(error, "word", None) == "fea"
    assert getattr(error, "claim_kind", None) == "mech.fea.static_stress"


# -- D95: structured coverage --------------------------------------------------


class _SweepingModel(Model):
    """A model stating grid + enumerated axis coverage (G29/G43)."""

    @property
    def signature(self) -> ModelSignature:
        """Upper-bound claim over `x`."""
        return ModelSignature(
            name="fixture.sweeping",
            claim_kind="fixture.sweeping.metric",
            sense=ClaimSense.upper_bound(),
            inputs=("x",),
        )

    @property
    def version(self) -> str:
        """The fixture model's own version id."""
        return "1.0.0"

    @property
    def cost(self) -> int:
        """Cheapest possible."""
        return 1

    def estimate(self, request: DischargeRequest) -> Result[Prediction, HarnessError]:
        """A 2-D grid axis crossed with an enumerated discrete axis."""
        x = request.inputs["x"]
        axes = (
            CoverageAxis(
                axis="mr",
                domain=CoverageDomain1(interval="[0.5, 1.5]"),
                method=CoverageMethod2(grid=Grid(k=[KItem(4), KItem(8)])),
            ),
            CoverageAxis(
                axis="valve_lineup",
                domain=CoverageDomain2(values=Values(values=["open", "closed"])),
                method=CoverageMethod3.enumerated,
            ),
        )
        return Ok(
            Prediction(
                value=x.hi, eps=0.0, coverage=1.0, coverage_axes=axes, in_domain=True
            )
        )


# frob:tests python/regolith/orchestrator/nogood_cache.py::NogoodCache.save
# frob:tests python/regolith/orchestrator/cache.py::EvidenceStore.save
def test_structured_coverage_round_trips_through_evidence_and_cache(
    tmp_path: Path,
) -> None:
    """A sweeping model's grid+enumerated coverage survives evidence + the
    orchestrator's evidence cache, byte-identically."""
    registry = ModelRegistry(version="model-registry@sweep-test")
    registry.register(_SweepingModel())
    request = DischargeRequest(
        claim_kind="fixture.sweeping.metric",
        limit=100.0,
        inputs={"x": Interval(lo=1.0, hi=2.0)},
    )
    evidence = registry.discharge(request)
    assert len(evidence.coverage.axes) == 2
    assert evidence.coverage.axes[0].axis == "mr"

    store = EvidenceStore()
    key = "k"
    store.put(key, evidence)
    project_root = str(tmp_path)
    saved = store.save(project_root)
    assert saved.is_ok
    loaded = EvidenceStore.load(project_root)
    assert loaded.is_ok
    round_tripped = loaded.danger_ok.get(key)
    assert round_tripped == evidence, "structured coverage must survive persistence"


# -- D96: the payload-ref channel ----------------------------------------------


def test_payload_requiring_model_matches_only_with_the_kind_present() -> None:
    """A model demanding a payload kind is a non-match when it is absent,
    and matches when the request carries it."""
    registry = registry_with_pack(
        "payload", "1.0.0", fixture_pack.register_payload_requiring
    )
    bare_request = DischargeRequest(
        claim_kind=fixture_pack.PAYLOAD_CLAIM_KIND, limit=100.0, inputs={}
    )
    absent_evidence = registry.discharge(bare_request)
    assert absent_evidence.model_id == NO_MODEL_ID
    assert absent_evidence.status.value == "indeterminate"

    carrying_request = DischargeRequest(
        claim_kind=fixture_pack.PAYLOAD_CLAIM_KIND,
        limit=100.0,
        inputs={},
        payloads={
            fixture_pack.PAYLOAD_PORT: PayloadRef(
                kind=fixture_pack.PAYLOAD_KIND,
                digest="blake3:aa",
                origin="test",
            )
        },
    )
    matched_evidence = registry.discharge(carrying_request)
    assert matched_evidence.model_id.startswith("fixture.payload")
    assert matched_evidence.status.value == "discharged"


def test_payload_store_resolve_returns_exact_bytes_and_missing_is_err(
    tmp_path: Path,
) -> None:
    """`resolve(digest)` returns the exact bytes `put` stored; a missing
    digest is an `Err` value."""
    store = PayloadStore(str(tmp_path))
    data = b"topology summary bytes"
    digest = store.put(data)
    resolved = store.resolve(digest)
    assert resolved.is_ok
    assert resolved.danger_ok == data

    missing = store.resolve("blake3:" + "0" * 64)
    assert missing.is_err


def test_resolve_request_payloads_maps_missing_digest_to_err(tmp_path: Path) -> None:
    """A request whose payload digest is unresolvable is an honest `Err`,
    never a partial/silent result."""
    store = PayloadStore(str(tmp_path))
    request = DischargeRequest(
        claim_kind=fixture_pack.PAYLOAD_CLAIM_KIND,
        limit=1.0,
        inputs={},
        payloads={
            "geometry": PayloadRef(
                kind="geometry.realized", digest="blake3:" + "f" * 64, origin="test"
            )
        },
    )
    result = resolve_request_payloads(request, store.resolver())
    assert result.is_err


# -- D97: given resolution + regime tags ---------------------------------------


def test_regime_non_match_falls_to_no_model() -> None:
    """A model requiring a regime tag the request lacks is a non-match."""
    registry = registry_with_pack(
        "regime", "1.0.0", fixture_pack.register_regime_requiring
    )
    request_without_regime = DischargeRequest(
        claim_kind=fixture_pack.REGIME_CLAIM_KIND,
        limit=100.0,
        inputs={"x": Interval(lo=1.0, hi=2.0)},
    )
    evidence = registry.discharge(request_without_regime)
    assert evidence.model_id == NO_MODEL_ID
    assert evidence.status.value == "indeterminate"

    request_with_regime = DischargeRequest(
        claim_kind=fixture_pack.REGIME_CLAIM_KIND,
        limit=100.0,
        inputs={"x": Interval(lo=1.0, hi=2.0)},
        regimes=(fixture_pack.REQUIRED_REGIME,),
    )
    matched = registry.discharge(request_with_regime)
    assert matched.model_id.startswith("fixture.regime")
    assert matched.status.value == "discharged"


def test_unresolved_given_produces_indeterminate_naming_the_given() -> None:
    """An unresolved given (`material: NOT_A_RECORD`) produces an
    indeterminate discharge whose diagnostic names `material`."""
    obligation = Obligation(
        claim=Claim(
            name="stress_check",
            form=ClaimForm1(form=Form.comparison, lhs="stress", op="<", rhs="100"),
            forall=[],
            hints=[],
        ),
        subject_ref="blake3:deadbeef",
        given=Given(
            materials=[],
            loads=["material: NOT_A_RECORD"],
            backing=[],
        ),
        hints=[],
        sweep=None,
    )
    lowered = translate(obligation)
    assert lowered.is_err
    deferral = lowered.danger_err
    assert deferral.reason == "given_unresolved"
    assert "material" in deferral.detail

    store = EvidenceStore()
    result = discharge_one(obligation, registry=default_registry(), store=store)
    assert result.deferral is not None
    assert result.deferral.reason == "given_unresolved"
    assert "material" in result.deferral.detail
    assert result.is_indeterminate
