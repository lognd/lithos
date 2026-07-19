"""Workload-realization identity model (EOPEN-15 rule 3, INV-26 default).

Discharges the demand-implication obligation the compiler emits for a
rule-3 DERIVED realization edge (`regolith-lower/src/claims.rs::
realization_obligation`, tagged `cause: derived(intent <name>)`): an
unrealized compute intent is completed by allocating a workload whose
demands are the intent's demands COPIED VERBATIM (cuprite/05 sec. 1 rule
3). That copy is a structural identity -- the derived workload's demand
vector equals the intent's by construction, so "workload implies intent"
is always sound for a derived edge, with zero margin to charge (no model
error: nothing was estimated, only copied).

A DECLARED (non-derived) realization edge's implication is a genuine
claim over independent quantities (rule 2's rate/state/latency compare)
that this pack does NOT discharge: the intent's own demand quantities are
not threaded through an obligation today (`intents:` bodies are opaque
islands, WO-05; `docs/audit/TRIAGE.md`), so a declared edge is left to
the orchestrator's honest deferral (no numeric request can be formed) --
never a silent pass. Only the derived, identity-sound case reaches this
model; :mod:`regolith.orchestrator.translate` is what tells them apart.
"""

from __future__ import annotations

from typani.result import Ok, Result

from regolith.harness.errors import HarnessError
from regolith.harness.model import DischargeRequest, Model, Prediction
from regolith.harness.signature import ClaimSense, ModelSignature

# One home for the claim kind this pack discharges (translate.py routes
# every `implies`-form realization obligation it recognizes as derived
# here; no other module may hard-code this string).
# frob:doc docs/modules/py-harness.md#models
CLAIM_KIND = "harness.workload_realization"


# frob:doc docs/modules/py-harness.md#models
class WorkloadRealizationModel(Model):
    """Identity discharge for a rule-3 derived workload/intent edge."""

    @property
    # frob:doc docs/modules/py-harness.md#models
    def signature(self) -> ModelSignature:
        """No inputs required: a derived edge's demand vector needs no data.

        The comparison is `value == limit` (verbatim copy); the pair is
        chosen as `1.0`/`1.0` (an arbitrary matching constant -- there is
        no physical quantity here, only a structural identity) so the
        shared margin rule (`regolith.harness.evidence`) discharges it
        with an exact-zero margin, never a fabricated pass.
        """
        return ModelSignature(
            name="workload_realization_identity",
            claim_kind=CLAIM_KIND,
            sense=ClaimSense.upper_bound(),
            inputs=(),
            domain=("cuprite", "computer_track", "derived_workload"),
        )

    @property
    # frob:doc docs/modules/py-harness.md#models
    def version(self) -> str:
        """Model version (bump on any change to the identity rule; INV-1)."""
        return "1"

    @property
    # frob:doc docs/modules/py-harness.md#models
    def cost(self) -> int:
        """Cheapest tier: no computation, only structural identity."""
        return 0

    # frob:doc docs/modules/py-harness.md#models
    def estimate(self, request: DischargeRequest) -> Result[Prediction, HarnessError]:
        """Predict the identity value: always equal to the request's limit.

        A derived workload's demand vector IS the intent's by construction
        (rule 3), so the predicted quantity exactly equals the limit the
        orchestrator threads for a derived edge -- zero error, full
        coverage, always in domain. Sound because nothing was estimated:
        the compiler already proved the vectors identical by copying one
        from the other.
        """
        return Ok(
            Prediction(value=request.limit, eps=0.0, coverage=1.0, in_domain=True)
        )
