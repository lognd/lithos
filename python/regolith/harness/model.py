"""The model protocol and the generic discharge driver.

A model is a closed-form (or, later, numeric/planner) predictor for one
claim kind. Every model shares ONE discharge path: it estimates the
claim's quantity at its worst corner (INV-9), declares its worst-case
error and coverage, and the base :meth:`Model.discharge` turns that into
an ``Evidence`` value via the single margin rule in
:mod:`regolith.harness.evidence`. Subclasses implement only the physics
(:meth:`Model.estimate`); the discharge/hashing/status logic is not
theirs to reimplement (NO DUPLICATION).
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict
from typani.result import Err, Ok, Result

from regolith._schema.models import Evidence
from regolith.harness.errors import DomainError, HarnessError, InputError
from regolith.harness.evidence import build_evidence
from regolith.harness.quantity import Interval, f64_to_bits
from regolith.harness.signature import ModelSignature


class DischargeRequest(BaseModel):
    """The structured discharge input the orchestrator hands a model.

    It is the harness image of an obligation (substrate/07 sec. 2): the
    claim kind + demanded window (``limit``, via the signature's sense)
    and the ``given:`` inputs as intervals the model evaluates at their
    worst corner. Extracting this from a serialized ``Obligation`` (whose
    quantity expressions are text until the orchestrator resolves them)
    is orchestrator territory; the harness consumes the resolved form.
    """

    model_config = ConfigDict(frozen=True)

    claim_kind: str
    limit: float
    inputs: Mapping[str, Interval]
    deterministic: bool = True
    settings_digest: str = ""

    def input_ports(self) -> frozenset[str]:
        """The input port names this request supplies."""
        return frozenset(self.inputs)

    def inputs_digest(self) -> str:
        """A canonical, deterministic digest of the resolved inputs.

        Feeds the evidence hash (INV-10): the endpoints are hashed as
        exact ``f64`` bits so text formatting cannot move the address.
        """
        canonical = {
            name: [f64_to_bits(iv.lo), f64_to_bits(iv.hi)]
            for name, iv in sorted(self.inputs.items())
        }
        canonical["__limit__"] = [f64_to_bits(self.limit), f64_to_bits(self.limit)]
        return json.dumps(canonical, sort_keys=True, separators=(",", ":"))


class Prediction(BaseModel):
    """A model's worst-corner estimate of a claim's quantity."""

    model_config = ConfigDict(frozen=True)

    value: float
    eps: float
    coverage: float = 1.0
    in_domain: bool = True


class Model(ABC):
    """A verification model: signature + physics + shared discharge path."""

    @property
    @abstractmethod
    def signature(self) -> ModelSignature:
        """The claim kind, sense, and inputs this model matches."""

    @property
    @abstractmethod
    def version(self) -> str:
        """The model's own version id (part of ``model_id``)."""

    @property
    @abstractmethod
    def cost(self) -> int:
        """Relative discharge cost (cheapest model wins ties, INV -- BE)."""

    @property
    def model_id(self) -> str:
        """The stable discharge model id recorded in evidence."""
        return f"{self.signature.name}@{self.version}"

    @abstractmethod
    def estimate(self, request: DischargeRequest) -> Result[Prediction, HarnessError]:
        """Compute the claim's quantity at its worst corner (INV-9)."""

    def discharge(
        self, request: DischargeRequest, *, registry_version: str
    ) -> Result[Evidence, HarnessError]:
        """Run :meth:`estimate` and apply the single margin rule.

        Returns an ``Evidence`` value (never raises for user-recoverable
        conditions): a missing input is an ``Err(InputError)``, an
        out-of-domain corner an ``Err(DomainError)``; the registry maps
        those to explicit indeterminate evidence so nothing silently
        passes.
        """
        missing = self.signature.missing(request.input_ports())
        if missing:
            return Err(
                InputError(
                    model_id=self.model_id,
                    missing=missing,
                    message=f"missing required inputs {missing!r}",
                )
            )
        estimated = self.estimate(request)
        if estimated.is_err:
            return Err(estimated.danger_err)
        prediction = estimated.danger_ok
        if not prediction.in_domain:
            return Err(
                DomainError(
                    model_id=self.model_id,
                    message="request falls outside the model's validity domain",
                )
            )
        return Ok(
            build_evidence(
                model_id=self.model_id,
                claim_kind=self.signature.claim_kind,
                sense_upper=self.signature.sense.upper,
                value=prediction.value,
                eps=prediction.eps,
                limit=request.limit,
                coverage=prediction.coverage,
                cost=self.cost,
                in_domain=prediction.in_domain,
                deterministic=request.deterministic,
                registry_version=registry_version,
                inputs_digest=request.inputs_digest(),
                settings_digest=request.settings_digest,
            )
        )
