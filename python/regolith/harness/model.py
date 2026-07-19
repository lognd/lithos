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

import inspect
import json
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field
from typani.result import Err, Ok, Result

from regolith._schema.models import CoverageAxis, Evidence, PayloadRef
from regolith.harness.errors import DomainError, HarnessError, InputError
from regolith.harness.evidence import build_evidence
from regolith.harness.quantity import Interval, f64_to_bits
from regolith.harness.signature import ModelSignature

if TYPE_CHECKING:
    # Type-only: `orchestrator.payload_store` imports `DischargeRequest`
    # from this module, so a runtime import here would be circular
    # (registry.py's `plugin.py` TYPE_CHECKING import is the same
    # precedent). `estimate`'s `resolver` parameter is annotated with
    # this alias only for readers; nothing at runtime depends on it.
    from regolith.orchestrator.payload_store import PayloadResolver

# D96/D154: the capability-check marker name every payload-consuming
# `Model.estimate` override must use for its resolver parameter so
# `_accepts_resolver` can detect it without a registry of opt-in models.
_RESOLVER_PARAM = "resolver"


# frob:doc docs/modules/py-harness.md#model
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

    ``model_pin`` (WO-80 deliverable 2/3; ``regolith/12`` sec. 2 rung 5)
    is the claim's ``model=<ident>`` forced-discharge-model identifier,
    if any -- ``regolith.orchestrator.translate.translate`` threads it
    from ``Obligation.claim.model_pin`` (the Rust lowering's typed field,
    WO-80 deliverable 1/2) onto every request uniformly. ``None`` is the
    un-pinned baseline: ordinary cost-ordered selection.
    """

    model_config = ConfigDict(frozen=True)

    claim_kind: str
    limit: float
    inputs: Mapping[str, Interval]
    deterministic: bool = True
    settings_digest: str = ""
    payloads: Mapping[str, PayloadRef] = Field(default_factory=dict)
    regimes: tuple[str, ...] = ()
    model_pin: str | None = None

    # frob:doc docs/modules/py-harness.md#model
    # frob:waive TEST001 reason="thin accessor, tested transitively via discharge tests"
    def input_ports(self) -> frozenset[str]:
        """The input port names this request supplies."""
        return frozenset(self.inputs)

    # frob:doc docs/modules/py-harness.md#model
    # frob:waive TEST001 reason="thin accessor, tested transitively via discharge tests"
    def payload_ports(self) -> Mapping[str, str]:
        """The payload port names this request supplies -> their kind."""
        return {name: ref.kind for name, ref in self.payloads.items()}

    # frob:doc docs/modules/py-harness.md#model
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


# frob:doc docs/modules/py-harness.md#model
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


def _accepts_resolver(estimate_method: Callable[..., object]) -> bool:
    """True iff a concrete ``estimate`` override names the ``resolver``
    parameter (D96/D154's capability check).

    This is the same "declares its own opt-in" pattern
    ``ModelSignature.payload_kinds``/``accepts_payloads`` already uses
    for payload-port matching -- a model consumes a channel by NAMING
    it, never by a separate registry flag that could desync. A model
    whose ``estimate`` accepts ``**kwargs`` also counts (it can receive
    anything); one that only names ``request`` does not.
    """
    try:
        params = inspect.signature(estimate_method).parameters
    except (TypeError, ValueError):  # pragma: no cover -- defensive only
        return False
    if _RESOLVER_PARAM in params:
        return True
    return any(p.kind is p.VAR_KEYWORD for p in params.values())


# frob:doc docs/modules/py-harness.md#model
class Model(ABC):
    """A verification model: signature + physics + shared discharge path."""

    @property
    @abstractmethod
    # frob:doc docs/modules/py-harness.md#model
    def signature(self) -> ModelSignature:
        """The claim kind, sense, and inputs this model matches."""

    @property
    @abstractmethod
    # frob:doc docs/modules/py-harness.md#model
    def version(self) -> str:
        """The model's own version id (part of ``model_id``)."""

    @property
    @abstractmethod
    # frob:doc docs/modules/py-harness.md#model
    def cost(self) -> int:
        """Relative discharge cost (cheapest model wins ties, INV -- BE)."""

    @property
    # frob:doc docs/modules/py-harness.md#model
    def model_id(self) -> str:
        """The stable discharge model id recorded in evidence."""
        return f"{self.signature.name}@{self.version}"

    @property
    # frob:doc docs/modules/py-harness.md#model
    def citation(self) -> str | None:
        """A literature/standard citation for this model's method (WO-114).

        The calc book (D221) renders this beside the model id; a model
        that returns ``None`` renders the honest ``uncited built-in``
        marker rather than a fabricated reference. Override to supply a
        real citation (WO-110 lands citations across the built-in packs
        in parallel); the base default keeps every existing model valid.
        """
        return None

    @property
    # frob:doc docs/modules/py-harness.md#model
    def input_units(self) -> Mapping[str, str]:
        """The physical unit each named input port carries (WO-123 D238.4).

        The calc book (D221) prints every input's unit beside its
        value; a port absent from this map has NO reachable unit (the
        calc sheet renders an honest ``--``/``(unitless)`` marker rather
        than guess, D224). Override with the model's own already-
        documented physical units (never invented here); the base
        default (empty) keeps every existing model valid.
        """
        return {}

    @property
    # frob:doc docs/modules/py-harness.md#model
    # frob:waive TEST001 reason="thin accessor, tested transitively via discharge tests"
    def output_unit(self) -> str | None:
        """This model's own output quantity's physical unit, if declared.

        The calc book (D221) prints the discharged value/margin beside
        this unit; ``None`` means no unit is reachable for this model's
        output (the sheet renders the honest marker, D224) -- override
        with the model's own documented physical unit, never a guess.
        """
        return None

    @abstractmethod
    # frob:doc docs/modules/py-harness.md#model
    def estimate(self, request: DischargeRequest) -> Result[Prediction, HarnessError]:
        """Compute the claim's quantity at its worst corner (INV-9).

        The base contract stays exactly this one-argument shape (LSP: a
        base method may not add a parameter its existing overrides do
        not accept). A model that wants the D96/D154 payload-resolution
        channel OVERRIDES this with an additional keyword-only
        ``resolver: PayloadResolver | None = None`` parameter -- widening
        acceptance is always a sound override, so a concrete
        ``estimate(self, request, *, resolver=None)`` still satisfies
        every caller of this contract. :func:`Model.discharge` detects
        that widening at the instance via :func:`_accepts_resolver` and
        passes the handle ONLY to a model that declared it; a model
        that keeps this exact one-argument shape (every pre-D154 model)
        is called exactly as it always was.
        """

    # frob:doc docs/modules/py-harness.md#model
    # frob:invariant INV-009
    # frob:invariant INV-025
    def discharge(
        self,
        request: DischargeRequest,
        *,
        registry_version: str,
        pack_name: str = "regolith",
        pack_version: str | None = None,
        resolver: PayloadResolver | None = None,
    ) -> Result[Evidence, HarnessError]:
        """Run :meth:`estimate` and apply the single margin rule.

        Returns an ``Evidence`` value (never raises for user-recoverable
        conditions): a missing input is an ``Err(InputError)``, an
        out-of-domain corner an ``Err(DomainError)``; the registry maps
        those to explicit indeterminate evidence so nothing silently
        passes. ``pack_name``/``pack_version`` identify the model pack
        this model was registered from (AD-19); the defaults are the
        built-in identity ``("regolith", registry_version)``.

        ``resolver`` (D96/D154) is forwarded to :meth:`estimate` ONLY
        when this model's concrete override declares a ``resolver``
        parameter (see :meth:`estimate`'s docstring) -- an unmodified
        pre-D154 model is called exactly as it always was.
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
        # `self.estimate` is statically typed to the one-argument base
        # contract (LSP, see the docstring above); a `resolver`-accepting
        # override is a WIDENING the type checker cannot see through a
        # `Model`-typed `self`, so the extra keyword is passed via
        # `**kwargs` -- runtime-dynamic, exactly matching what
        # `_accepts_resolver`'s `inspect.signature` check already proved
        # this concrete instance accepts.
        extra_kwargs: dict[str, object] = (
            {"resolver": resolver} if _accepts_resolver(self.estimate) else {}
        )
        estimated = self.estimate(request, **extra_kwargs)
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
