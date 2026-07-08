"""The in-repo fixture model pack (WO-20 conformance exercise).

A minimal but complete pack: one pure-Python model and one
out-of-process :class:`SubprocessSolverModel` wired to the fixture
solver executable. A real pack ships this shape as its own
distribution with a ``regolith.model_packs`` entry point; here the
suite injects it through fake entry points (AD-11 fakes -- no install
step in the test env).
"""

from __future__ import annotations

import sys
from pathlib import Path

from regolith.harness import (
    ClaimSense,
    DischargeRequest,
    Model,
    ModelRegistry,
    ModelSignature,
    Prediction,
    SolverSpec,
    SubprocessSolverModel,
)
from regolith.harness.errors import HarnessError
from typani.result import Ok, Result

# The claim kinds the fixture pack serves (never colliding with a
# shipped built-in model's claim kind).
ECHO_CLAIM_KIND = "fixture.echo.metric"
SOLVER_CLAIM_KIND = "fixture.solver.metric"

# D94 kind-competition fixture: ONE model id registered under two
# DIFFERENT claim kinds (a real pack would wrap one physics core twice).
TWO_KIND_CLAIM_KIND_A = "fixture.two_kind.metric_a"
TWO_KIND_CLAIM_KIND_B = "fixture.two_kind.metric_b"

# D96 payload-channel fixture: a model that only matches when the
# request carries a payload of this kind on this port.
PAYLOAD_CLAIM_KIND = "fixture.payload.metric"
PAYLOAD_PORT = "geometry"
PAYLOAD_KIND = "geometry.realized"

# D97 regime fixture: a model that only matches when the request
# asserts this regime tag.
REGIME_CLAIM_KIND = "fixture.regime.metric"
REQUIRED_REGIME = "fixture_regime"

# The fixture solver executable, run through the current interpreter so
# the test env needs no installed binary.
SOLVER_SCRIPT = Path(__file__).with_name("fixture_solver.py")


class FixtureEchoModel(Model):
    """A trivial in-process pack model: predicts its input's upper corner."""

    @property
    def signature(self) -> ModelSignature:
        """Upper-bound claim over one input port ``x``."""
        return ModelSignature(
            name="fixture.echo",
            claim_kind=ECHO_CLAIM_KIND,
            sense=ClaimSense.upper_bound(),
            inputs=("x",),
        )

    @property
    def version(self) -> str:
        """The fixture model's own version id."""
        return "1.0.0"

    @property
    def cost(self) -> int:
        """Cheapest possible: the fixture has no physics to pay for."""
        return 1

    def estimate(self, request: DischargeRequest) -> Result[Prediction, HarnessError]:
        """Worst corner of ``x`` with zero model error (INV-9 trivially)."""
        x = request.inputs["x"]
        return Ok(Prediction(value=x.hi, eps=0.0, coverage=1.0, in_domain=True))


class TwoKindModel(Model):
    """D94 (sec. 8.1): one model id, registered under TWO claim kinds.

    ``register`` below registers this SAME class twice, each instance
    reporting a different ``claim_kind`` through ``_kind`` -- exactly
    the "one physics core wrapped twice" shape D94 legalizes.
    """

    def __init__(self, kind: str) -> None:
        """Bind this instance to one of the two competing claim kinds."""
        self._kind = kind

    @property
    def signature(self) -> ModelSignature:
        """Upper-bound claim over ``x``, keyed by the bound claim kind."""
        return ModelSignature(
            name="fixture.two_kind",
            claim_kind=self._kind,
            sense=ClaimSense.upper_bound(),
            inputs=("x",),
        )

    @property
    def version(self) -> str:
        """Shared version: both instances share ONE model id (D94)."""
        return "1.0.0"

    @property
    def cost(self) -> int:
        """Cheapest possible."""
        return 1

    def estimate(self, request: DischargeRequest) -> Result[Prediction, HarnessError]:
        """Worst corner of ``x``, identical physics under either kind."""
        x = request.inputs["x"]
        return Ok(Prediction(value=x.hi, eps=0.0, coverage=1.0, in_domain=True))


class PayloadRequiringModel(Model):
    """D96 (sec. 8.3): matches only when the request carries the payload."""

    @property
    def signature(self) -> ModelSignature:
        """Requires a `geometry.realized` payload on the `geometry` port."""
        return ModelSignature(
            name="fixture.payload",
            claim_kind=PAYLOAD_CLAIM_KIND,
            sense=ClaimSense.upper_bound(),
            inputs=(),
            payload_kinds={PAYLOAD_PORT: PAYLOAD_KIND},
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
        """A trivial always-discharging estimate (the payload gate is the point)."""
        return Ok(Prediction(value=0.0, eps=0.0, coverage=1.0, in_domain=True))


class RegimeRequiringModel(Model):
    """D97 (sec. 8.4): matches only when the request asserts the regime."""

    @property
    def signature(self) -> ModelSignature:
        """Requires the fixture regime tag."""
        return ModelSignature(
            name="fixture.regime",
            claim_kind=REGIME_CLAIM_KIND,
            sense=ClaimSense.upper_bound(),
            inputs=("x",),
            required_regimes=(REQUIRED_REGIME,),
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
        """Worst corner of ``x`` with zero model error."""
        x = request.inputs["x"]
        return Ok(Prediction(value=x.hi, eps=0.0, coverage=1.0, in_domain=True))


def solver_spec(mode: str = "ok", *, timeout_s: float = 30.0) -> SolverSpec:
    """The fixture solver's wiring, with an argv-selected misbehavior mode."""
    return SolverSpec(
        argv=(sys.executable, str(SOLVER_SCRIPT), mode),
        signature=ModelSignature(
            name="fixture.solver",
            claim_kind=SOLVER_CLAIM_KIND,
            sense=ClaimSense.upper_bound(),
            inputs=("x",),
        ),
        version="1.0.0",
        cost=10,
        deterministic=True,
        timeout_s=timeout_s,
    )


def register(registry: ModelRegistry) -> None:
    """The pack protocol's whole surface (design doc D-B)."""
    registry.register(FixtureEchoModel())
    registry.register(SubprocessSolverModel(solver_spec()))


def register_duplicate(registry: ModelRegistry) -> None:
    """A hostile pack: registers a model id the fixture pack already owns."""
    registry.register(FixtureEchoModel())


def register_raising(registry: ModelRegistry) -> None:
    """A broken pack whose ``register`` raises (the plugin-boundary case)."""
    raise RuntimeError("fixture pack exploding on purpose")


def register_two_kind(registry: ModelRegistry) -> None:
    """D94: one model id registered under two DIFFERENT claim kinds."""
    registry.register(TwoKindModel(TWO_KIND_CLAIM_KIND_A))
    registry.register(TwoKindModel(TWO_KIND_CLAIM_KIND_B))


def register_two_kind_same_kind_duplicate(registry: ModelRegistry) -> None:
    """A hostile pack: the SAME id under the SAME kind twice (still an error)."""
    registry.register(TwoKindModel(TWO_KIND_CLAIM_KIND_A))
    registry.register(TwoKindModel(TWO_KIND_CLAIM_KIND_A))


def register_payload_requiring(registry: ModelRegistry) -> None:
    """D96: a model that only matches with the required payload present."""
    registry.register(PayloadRequiringModel())


def register_regime_requiring(registry: ModelRegistry) -> None:
    """D97: a model that only matches with the required regime tag present."""
    registry.register(RegimeRequiringModel())


def register_method_named_kind(registry: ModelRegistry) -> None:
    """D94: a hostile pack naming its claim kind after a method (`fea`)."""
    registry.register(
        TwoKindModel("mech.fea.static_stress"),
    )
