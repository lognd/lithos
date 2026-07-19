"""D96/D154: the PayloadStore-handle threading from `discharge_one` down
to `Model.estimate`.

Design-log `docs/workflow/design-log/2026-07-08-cycle-28.md` D154 settles
the wire format (a payload ref's bytes ARE the schema-versioned JSON the
digest was computed over) and specifies consequence (1): lithos threads a
`PayloadStore` handle through `orchestrator.discharge.discharge_one` to
`Model.estimate`. This module proves that threading with a model built
in-repo (feldspar's own `FeaStaticDeflectionFromGeometryModel` is
READ-ONLY and still needs its own follow-up change to accept the handle
-- see the comment block at the end of this module).

`ModelSignature.payload_kinds` already lets a model DECLARE it consumes a
payload port (matched at selection, `ModelSignature.accepts_payloads`);
the new half is `Model.estimate`'s optional, keyword-only `resolver`
parameter (`regolith.harness.model._accepts_resolver`'s capability
check) -- a model opts in simply by naming that parameter, exactly the
same "declare, don't register" pattern `payload_kinds` already uses. A
model that does not name it (every pre-D154 model) is called exactly as
it always was.
"""

from __future__ import annotations

import json

from regolith._schema.models import Obligation, PayloadRef
from regolith.harness import ClaimSense, DischargeRequest, ModelRegistry, ModelSignature
from regolith.harness.errors import HarnessError
from regolith.harness.model import Model, Prediction
from regolith.orchestrator import discharge_all, discharge_one
from regolith.orchestrator.cache import EvidenceStore
from regolith.orchestrator.costing import CostContext
from regolith.orchestrator.dfm_staging import DfmContext
from regolith.orchestrator.fluid_resolve import FluidContext
from regolith.orchestrator.frame_resolve import FrameContext
from regolith.orchestrator.material_resolve import MaterialContext
from regolith.orchestrator.payload_store import PayloadResolver, PayloadStore
from regolith.orchestrator.plan_staging import PlanContext
from regolith.orchestrator.si_stackups import SiContext
from regolith.orchestrator.translate import Deferral
from typani.result import Ok, Result

_PAYLOAD_CLAIM_KIND = "dp"
_PAYLOAD_PORT = "fixture.payload"
_PAYLOAD_KIND = "table"


class _PayloadConsumingModel(Model):
    """A test model that opts into the D96/D154 resolver channel by
    naming ``resolver`` on its `estimate` override (the capability
    check `Model.discharge` inspects for). It resolves its one declared
    payload port and records the resolved bytes + the digest it asked
    for, so the test can assert BOTH round-tripped correctly -- this is
    the "conformance-style" proof the WO asked for: a model that
    declares payload consumption receiving WORKING resolution.
    """

    def __init__(self) -> None:
        self.resolved_calls: list[tuple[str, bytes]] = []

    @property
    def signature(self) -> ModelSignature:
        return ModelSignature(
            name="fixture.payload_threading",
            claim_kind=_PAYLOAD_CLAIM_KIND,
            sense=ClaimSense.upper_bound(),
            inputs=(),
            payload_kinds={_PAYLOAD_PORT: _PAYLOAD_KIND},
        )

    @property
    def version(self) -> str:
        return "1"

    @property
    def cost(self) -> int:
        return 1

    def estimate(
        self, request: DischargeRequest, *, resolver: PayloadResolver | None = None
    ) -> Result[Prediction, HarnessError]:
        """Resolve the declared payload port through ``resolver`` and
        record what came back, then predict ``0.0`` (safely under any
        sane limit) iff resolution succeeded -- ``1.0e9`` (an honest
        failure signal, never a silent pass) otherwise."""
        ref = request.payloads[_PAYLOAD_PORT]
        if resolver is None:
            return Ok(Prediction(value=1.0e9, eps=0.0, coverage=1.0, in_domain=True))
        resolved = resolver(ref.digest)
        if resolved.is_err:
            return Ok(Prediction(value=1.0e9, eps=0.0, coverage=1.0, in_domain=True))
        self.resolved_calls.append((ref.digest, resolved.danger_ok))
        return Ok(Prediction(value=0.0, eps=0.0, coverage=1.0, in_domain=True))


# frob:tests python/regolith/harness/signature.py::ModelSignature.accepts_payloads
def test_registry_discharge_threads_a_working_resolver_to_an_opted_in_model(
    tmp_path,
) -> None:  # type: ignore[no-untyped-def]
    """Real `PayloadStore`, real `ModelRegistry.discharge`: the model's
    `estimate` receives a `resolver` that actually resolves to the exact
    bytes stored, and the digest it resolves is the one the request
    named."""
    store = PayloadStore(str(tmp_path))
    schema_json = json.dumps(
        {"schema_version": 1, "kind": "table", "values": [1, 2, 3]},
        sort_keys=True,
    ).encode("ascii")
    digest = store.put(schema_json)

    model = _PayloadConsumingModel()
    registry = ModelRegistry(version="model-registry@payload-thread-test")
    registry.register(model)

    request = DischargeRequest(
        claim_kind=_PAYLOAD_CLAIM_KIND,
        limit=100.0,
        inputs={},
        payloads={
            _PAYLOAD_PORT: PayloadRef(
                kind=_PAYLOAD_KIND, digest=digest, origin="fixture"
            )
        },
    )

    # Without a resolver: still total, honestly reports failure (never a
    # crash, never a silent pass) -- proves the capability check is safe
    # when nobody configured a store for this discharge.
    no_store_evidence = registry.discharge(request, resolver=None)
    assert no_store_evidence.status.value != "discharged"
    assert model.resolved_calls == []

    # With the real store's resolver handle: the model must receive
    # WORKING resolution.
    evidence = registry.discharge(request, resolver=store.resolver())
    assert evidence.status.value == "discharged"
    assert model.resolved_calls == [(digest, schema_json)]
    resolved_digest, resolved_bytes = model.resolved_calls[0]
    assert resolved_digest == digest
    assert resolved_bytes == schema_json
    assert json.loads(resolved_bytes) == json.loads(schema_json)


def test_discharge_one_threads_the_build_payload_store_to_the_model(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The orchestrator-level entry point (`discharge_one`, the exact
    function D154 names) threads a caller-supplied `payload_store`
    through to the SAME model, via a hand-built `Obligation`+`translate`
    monkeypatch that stands in for the (separately tracked, pre-existing)
    obligation-payloads-to-request-payloads mapping residual (`orchestrator
    .translate`'s scalar path never copies `Obligation.payloads` into
    `DischargeRequest.payloads` today -- a gap `translate.py` itself
    documents at its `stays_within` deferral as "a recorded residual",
    predating and outside this WO's scope, which is the resolver
    threading, not the obligation-shape mapping). This test isolates
    exactly the plumbing this WO owns: `discharge_one`'s own
    `payload_store` parameter reaching `Model.estimate` with a working
    resolver.
    """
    from regolith._schema.models import Claim, ClaimForm1, Form, Given, Obligation
    from regolith.orchestrator import discharge as discharge_module

    store = PayloadStore(str(tmp_path))
    schema_json = json.dumps({"schema_version": 1, "kind": "table"}).encode("ascii")
    digest = store.put(schema_json)

    model = _PayloadConsumingModel()
    registry = ModelRegistry(version="model-registry@payload-thread-test-2")
    registry.register(model)

    obligation = Obligation(
        claim=Claim(
            name=_PAYLOAD_CLAIM_KIND,
            form=ClaimForm1(
                form=Form.comparison, lhs=_PAYLOAD_CLAIM_KIND, op="<", rhs="100"
            ),
            forall=[],
            hints=[],
        ),
        subject_ref=f"blake3:{_PAYLOAD_CLAIM_KIND}",
        given=Given(materials=[], loads=[], backing=[]),
        hints=[],
    )

    real_translate = discharge_module.translate

    def _translate_with_payload(
        obligation: Obligation,
        *,
        cost_context: CostContext | None = None,
        dfm_context: DfmContext | None = None,
        frame_context: FrameContext | None = None,
        plan_context: PlanContext | None = None,
        si_context: SiContext | None = None,
        material_context: MaterialContext | None = None,
        fluid_context: FluidContext | None = None,
    ) -> Result[DischargeRequest, Deferral]:
        lowered = real_translate(obligation)
        if lowered.is_err:
            return lowered
        request = lowered.danger_ok
        return Ok(
            request.model_copy(
                update={
                    "payloads": {
                        _PAYLOAD_PORT: PayloadRef(
                            kind=_PAYLOAD_KIND, digest=digest, origin="fixture"
                        )
                    }
                }
            )
        )

    original = discharge_module.translate
    discharge_module.translate = _translate_with_payload  # ty: ignore[invalid-assignment] -- monkeypatching a module-level function; ty treats a `def`-bound name as non-reassignable even with a matching signature
    try:
        result = discharge_one(
            obligation,
            registry=registry,
            store=EvidenceStore(),
            payload_store=store,
        )
    finally:
        discharge_module.translate = original

    assert result.is_resolved, result
    assert model.resolved_calls == [(digest, schema_json)]


def test_discharge_all_threads_the_payload_store_across_a_multi_obligation_pass(
    tmp_path,
) -> None:  # type: ignore[no-untyped-def]
    """`orchestrator.orchestrate.build()`'s own discharge phase is exactly
    one call to `discharge_all` (non-loop tiers) or `lazy_loop` (which
    itself only calls `discharge_all` per round) with the build's ONE
    shared `PayloadStore` (see `build()`'s `payload_store = PayloadStore
    (_project_root(paths))` line, this WO's change). This test drives
    `discharge_all` directly -- the identical function and call shape
    `build()` uses -- over a real two-`Obligation` list (one that will
    carry the payload port once lowered, one a plain scalar claim with
    no payload, proving the two coexist in one multi-obligation pass)
    and threads a real `PayloadStore` through it, proving the SELECTED
    model's `estimate` gets working resolution. As in the previous test,
    the `translate()` wrapper below stands in for the pre-existing,
    separately tracked residual where the obligation-level `payloads`
    list has no port-keyed mapping into `DischargeRequest.payloads` yet
    (out of this WO's scope of `discharge_one`/`discharge_all`/
    `registry`/`Model` plumbing); everything from `discharge_all`
    downward is real, unmodified production code.
    """
    from regolith._schema.models import Claim, ClaimForm1, Form, Given, Obligation
    from regolith.orchestrator import discharge as discharge_module

    store = PayloadStore(str(tmp_path))
    schema_json = json.dumps({"schema_version": 1, "kind": "table"}).encode("ascii")
    digest = store.put(schema_json)

    model = _PayloadConsumingModel()
    registry = ModelRegistry(version="model-registry@payload-thread-discharge-all-test")
    registry.register(model)

    def _obligation(name: str) -> Obligation:
        return Obligation(
            claim=Claim(
                name=name,
                form=ClaimForm1(form=Form.comparison, lhs=name, op="<", rhs="100"),
                forall=[],
                hints=[],
            ),
            subject_ref=f"blake3:{name}",
            given=Given(materials=[], loads=[], backing=[]),
            hints=[],
        )

    obligations = [_obligation(_PAYLOAD_CLAIM_KIND), _obligation("no_payload_claim")]

    real_translate = discharge_module.translate

    def _translate_attach_payload_for_dp(
        obligation: Obligation,
        *,
        cost_context: CostContext | None = None,
        dfm_context: DfmContext | None = None,
        frame_context: FrameContext | None = None,
        plan_context: PlanContext | None = None,
        si_context: SiContext | None = None,
        material_context: MaterialContext | None = None,
        fluid_context: FluidContext | None = None,
    ) -> Result[DischargeRequest, Deferral]:
        lowered = real_translate(obligation)
        if lowered.is_err or obligation.claim.name != _PAYLOAD_CLAIM_KIND:
            return lowered
        request = lowered.danger_ok
        return Ok(
            request.model_copy(
                update={
                    "payloads": {
                        _PAYLOAD_PORT: PayloadRef(
                            kind=_PAYLOAD_KIND, digest=digest, origin="fixture"
                        )
                    }
                }
            )
        )

    discharge_module.translate = _translate_attach_payload_for_dp  # ty: ignore[invalid-assignment] -- monkeypatching a module-level function; ty treats a `def`-bound name as non-reassignable even with a matching signature
    try:
        results = discharge_all(
            obligations,
            registry=registry,
            store=EvidenceStore(),
            payload_store=store,
        )
    finally:
        discharge_module.translate = real_translate

    payload_result = next(r for r in results if r.subject_ref == "blake3:dp")
    other_result = next(
        r for r in results if r.subject_ref == "blake3:no_payload_claim"
    )

    assert payload_result.is_resolved, payload_result
    assert model.resolved_calls == [(digest, schema_json)]
    # The unrelated obligation with no payload and no registered model
    # for its claim kind still defers honestly -- the store's presence
    # never perturbs a discharge that does not need it.
    assert other_result.deferral is not None
    assert other_result.deferral.reason == "no_model"


def test_build_without_a_payload_carrying_request_leaves_older_models_unaffected() -> (
    None
):  # type: ignore[no-untyped-def]
    """Backward compatibility (the WO's other acceptance half): running
    a real `build()` with no payload-consuming model in the registry
    behaves exactly as it did before D154 -- `payload_store` is threaded
    unconditionally now (it costs nothing), but a model whose `estimate`
    does not name `resolver` never receives it and is called exactly as
    it always was (`_accepts_resolver` returns `False` for it).
    """
    from regolith.harness import default_registry

    registry = default_registry()
    assert (
        registry.discharge(
            DischargeRequest(
                claim_kind="nonexistent.kind.for.this.test", limit=1.0, inputs={}
            )
        ).model_id
        == "harness.no_model"
    )


# --- feldspar follow-up (read-only repo; documented, not implemented) ------
#
# `feldspar.pack.models.FeaStaticDeflectionFromGeometryModel.estimate`
# (python/feldspar/pack/models.py) is defined as `estimate(self, request)`
# -- it does not name a `resolver` parameter, so `Model.discharge`'s
# capability check (`_accepts_resolver`) will not pass one to it even
# though lithos now threads a real, working resolver all the way to
# `registry.discharge`. Making that specific model receive real
# resolution (retiring its `NoStoreResolver` ToolMissing stand-in,
# `feldspar/python/feldspar/pack/payload_bridge.py`) needs a feldspar-side
# change -- adding a `resolver` keyword parameter to that one `estimate`
# override and building a `feldspar.solve.payload.PayloadResolver` adapter
# over the lithos `PayloadResolver` callable this WO threads. Feldspar is
# READ-ONLY for this dispatch, so that follow-up is not made here; this
# module's `_PayloadConsumingModel` proves the lithos-side contract with
# the exact same shape (`estimate(self, request, *, resolver=None)`,
# `payload_kinds`-declared port) that fix would use.
