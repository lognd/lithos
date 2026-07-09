"""The std.cost reference estimator models (WO-54 deliverable 5;
toolchain/27 sec. 1.4, AD-19/AD-29).

Three ordinary :class:`Model`s compete under the ONE `mfg.cost` claim
kind (D94 kind competition); the request's payload PORTS pick the
right basis: the orchestrator (`regolith.orchestrator.costing`) stages
one cost-inputs `table` document per cost obligation and publishes its
digest under `cost_inputs` plus one marker port per NON-EMPTY quantity
basis (`cost_bom` / `cost_frame` / `cost_flownet`), so a model whose
basis is absent is a signature non-match, never a guess.

Each model resolves the doc through the ordinary D96 ``resolver``
channel, prices every profile the doc carries (one, or every swept D95
axis point), and predicts the WORST (highest) profile total -- the
per-profile axis is recorded as structured coverage (D95 sec. 8.2,
`enumerated`). The estimate arithmetic lives in ONE home
(:mod:`regolith.harness.models.cost_common`), shared with the
orchestrator's estimate-payload producer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import ValidationError
from typani.result import Err, Ok, Result

from regolith._schema.models import (
    CoverageAxis,
    CoverageDomain2,
    CoverageMethod3,
    ItemizedEstimate,
    Values,
)
from regolith.harness.errors import DomainError, HarnessError
from regolith.harness.model import DischargeRequest, Model, Prediction
from regolith.harness.models.cost_common import (
    CLAIM_KIND,
    COST_INPUTS_KIND,
    COST_INPUTS_PORT,
    CostInputsDoc,
    CostProfileInputs,
    EstimateError,
    bom_estimate,
    civil_takeoff_estimate,
    fluid_bom_estimate,
)
from regolith.harness.signature import ClaimSense, ModelSignature
from regolith.logging_setup import get_logger

if TYPE_CHECKING:
    from regolith.orchestrator.payload_store import PayloadResolver

_log = get_logger(__name__)

# The per-basis marker ports (see the module docstring): each carries
# the SAME doc digest as `cost_inputs`; their presence encodes which
# quantity bases the staged doc actually populated.
BOM_PORT = "cost_bom"
FRAME_PORT = "cost_frame"
FLOWNET_PORT = "cost_flownet"

class _CostEstimatorModel(Model):
    """The shared std.cost estimator spine: resolve the doc, price every
    profile via the subclass's basis function, predict the worst total."""

    _name: str
    _basis_port: str
    _domain: tuple[str, ...]

    def _estimate_profile(
        self, doc: CostInputsDoc, profile: CostProfileInputs
    ) -> Result[ItemizedEstimate, EstimateError]:
        """The subclass's basis arithmetic (one of `cost_common`'s three
        estimate functions). Not implemented on the spine is a
        programmer bug, so an exception is the right failure mode."""
        raise NotImplementedError

    @property
    def signature(self) -> ModelSignature:
        """Upper-bound `mfg.cost` claim over this basis's payload ports."""
        return ModelSignature(
            name=self._name,
            claim_kind=CLAIM_KIND,
            sense=ClaimSense.upper_bound(),
            inputs=(),
            domain=self._domain,
            payload_kinds={
                COST_INPUTS_PORT: COST_INPUTS_KIND,
                self._basis_port: COST_INPUTS_KIND,
            },
        )

    @property
    def version(self) -> str:
        """Model version (bump on any pricing-rule change; INV-1)."""
        return "1"

    @property
    def cost(self) -> int:
        """Record arithmetic only: the cheapest tier."""
        return 1

    def estimate(
        self,
        request: DischargeRequest,
        *,
        resolver: PayloadResolver | None = None,
    ) -> Result[Prediction, HarnessError]:
        """Price every profile in the staged doc; worst total is the value."""
        ref = request.payloads.get(COST_INPUTS_PORT)
        if ref is None:  # pragma: no cover -- signature match guarantees it
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=f"request carries no {COST_INPUTS_PORT!r} payload",
                )
            )
        if resolver is None:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message="no payload store resolver configured for this discharge",
                )
            )
        resolved = resolver(ref.digest)
        if resolved.is_err:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=(
                        f"cost-inputs payload {ref.digest} did not resolve: "
                        f"{resolved.danger_err.message}"
                    ),
                )
            )
        try:
            doc = CostInputsDoc.model_validate_json(resolved.danger_ok)
        except ValidationError as exc:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message=f"cost-inputs payload is not a CostInputsDoc: {exc}",
                )
            )
        if not doc.profiles:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message="cost-inputs doc carries no profiles",
                )
            )

        worst = float("-inf")
        for profile in doc.profiles:
            estimated = self._estimate_profile(doc, profile)
            if estimated.is_err:
                abstain = estimated.danger_err
                return Err(
                    DomainError(
                        model_id=self.model_id,
                        message=f"{abstain.reason}: {abstain.detail}",
                    )
                )
            total = estimated.danger_ok.total
            worst = max(worst, total.hi)
        _log.debug(
            "%s: subject=%s profiles=%s worst_total=%g",
            self.model_id,
            doc.subject,
            [p.name for p in doc.profiles],
            worst,
        )
        # The per-profile axis is structured coverage (D95 sec. 8.2):
        # every discrete point was enumerated. The record intervals'
        # spread already rides the totals (the hi corner is predicted),
        # so no separate model error is charged.
        axes = (
            (
                CoverageAxis(
                    axis="profile",
                    domain=CoverageDomain2(
                        values=Values(values=[p.name for p in doc.profiles])
                    ),
                    method=CoverageMethod3.enumerated,
                ),
            )
            if len(doc.profiles) > 1
            else ()
        )
        return Ok(
            Prediction(value=worst, eps=0.0, coverage=1.0, coverage_axes=axes)
        )


class CostElecBomModel(_CostEstimatorModel):
    """Elec BOM x pricing breaks (toolchain/27 sec. 1.4; the `parts:`
    BOM basis; per-joint assembly + fab table are declared exclusions
    until a joint-count/fab basis exists -- WO-54 close-out ledger)."""

    _name = "cost_elec_bom"
    _basis_port = BOM_PORT
    _domain = ("cost", "bom", "pricing_breaks")

    def _estimate_profile(
        self, doc: CostInputsDoc, profile: CostProfileInputs
    ) -> Result[ItemizedEstimate, EstimateError]:
        """Price the `parts:` BOM lines (one home: `cost_common`)."""
        return bom_estimate(doc, profile)


class CostFluidBomModel(_CostEstimatorModel):
    """Fluid BOM over component records (toolchain/27 sec. 1.4; the
    flownet-edge basis; un-recorded pipe runs are declared exclusions)."""

    _name = "cost_fluid_bom"
    _basis_port = FLOWNET_PORT
    _domain = ("cost", "bom", "flownet")

    def _estimate_profile(
        self, doc: CostInputsDoc, profile: CostProfileInputs
    ) -> Result[ItemizedEstimate, EstimateError]:
        """Price the flownet-edge component lines (one home: `cost_common`)."""
        return fluid_bom_estimate(doc, profile)


class CostCivilTakeoffModel(_CostEstimatorModel):
    """Civil member-length takeoff x unit-cost records (toolchain/27
    sec. 1.4; the landed FramePayload surface; supports/areas/
    connections are declared exclusions -- WO-54 close-out ledger)."""

    _name = "cost_civil_takeoff"
    _basis_port = FRAME_PORT
    _domain = ("cost", "takeoff", "frame")

    def _estimate_profile(
        self, doc: CostInputsDoc, profile: CostProfileInputs
    ) -> Result[ItemizedEstimate, EstimateError]:
        """Price the member-length takeoff (one home: `cost_common`)."""
        return civil_takeoff_estimate(doc, profile)
