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
