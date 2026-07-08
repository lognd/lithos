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

from pydantic import BaseModel, ConfigDict, Field
from typani.result import Err, Ok, Result

from regolith._schema.models import CoverageAxis, Evidence, PayloadRef
from regolith.harness.errors import DomainError, HarnessError, InputError
from regolith.harness.evidence import build_evidence
from regolith.harness.quantity import Interval, f64_to_bits
from regolith.harness.signature import ModelSignature


class DischargeRequest(BaseModel):
    """The structured discharge input the orchestrator hands a model.

    It is the harness image of an obligation (regolith/07 sec. 2): the
    claim kind + demanded window (``limit``, via the signature's sense)
    and the ``given:`` inputs as intervals the model evaluates at their
    worst corner. Extracting this from a serialized ``Obligation`` (whose
    quantity expressions are text until the orchestrator resolves them)
    is orchestrator territory; the harness consumes the resolved form.

    ``payloads`` (D96, sec. 8.3) is the generalized hash-pinned payload
    channel (port name -> ``PayloadRef``); ``regimes`` (D97, sec. 8.4)
    are the validity-domain tags LOWERING asserts from claim-kind
    construction (``linear_elastic``, ``static``, ...). Both are total,
    honest matching inputs: a model demanding a payload/regime the
    request does not carry is a non-match, never an assumption.
    """

    model_config = ConfigDict(frozen=True)

    claim_kind: str
    limit: float
    inputs: Mapping[str, Interval]
    deterministic: bool = True
    settings_digest: str = ""
    payloads: Mapping[str, PayloadRef] = Field(default_factory=dict)
    regimes: tuple[str, ...] = ()

    def input_ports(self) -> frozenset[str]:
        """The input port names this request supplies."""
        return frozenset(self.inputs)

    def payload_ports(self) -> Mapping[str, str]:
        """The payload port names this request supplies -> their kind."""
        return {name: ref.kind for name, ref in self.payloads.items()}

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
    """A model's worst-corner estimate of a claim's quantity.

    ``solver_version`` and ``settings_digest`` are the channel an
    out-of-process solver's wire response uses to reach the ONE shared
    discharge/hash path (AD-19/INV-10): the solver binary's version is
    always folded into the evidence hash, and a non-``None``
    ``settings_digest`` overrides the request's digest. In-process
    models leave both at their defaults.
    """

    model_config = ConfigDict(frozen=True)

    value: float
    eps: float
    coverage: float = 1.0
    coverage_axes: tuple[CoverageAxis, ...] = ()
    in_domain: bool = True
    solver_version: str = ""
    settings_digest: str | None = None


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
        self,
        request: DischargeRequest,
        *,
        registry_version: str,
        pack_name: str = "regolith",
        pack_version: str | None = None,
    ) -> Result[Evidence, HarnessError]:
        """Run :meth:`estimate` and apply the single margin rule.

        Returns an ``Evidence`` value (never raises for user-recoverable
        conditions): a missing input is an ``Err(InputError)``, an
        out-of-domain corner an ``Err(DomainError)``; the registry maps
        those to explicit indeterminate evidence so nothing silently
        passes. ``pack_name``/``pack_version`` identify the model pack
        this model was registered from (AD-19); the defaults are the
        built-in identity ``("regolith", registry_version)``.
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
        # A wire response's own settings digest (INV-10) overrides the
        # request's; in-process models predict `None` and keep it.
        settings_digest = (
            prediction.settings_digest
            if prediction.settings_digest is not None
            else request.settings_digest
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
                coverage_axes=prediction.coverage_axes,
                cost=self.cost,
                in_domain=prediction.in_domain,
                deterministic=request.deterministic,
                registry_version=registry_version,
                inputs_digest=request.inputs_digest(),
                settings_digest=settings_digest,
                pack_name=pack_name,
                pack_version=pack_version,
                solver_version=prediction.solver_version,
            )
        )
