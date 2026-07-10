"""Harness error VALUES (AD-7 / house style).

Every fallible harness API returns a typani ``Result[T, E]`` whose ``E`` is
one of these frozen models -- never a bare exception. A missing model, a
missing input, or an out-of-domain request is recoverable data the
orchestrator reasons about (it may pick another model, widen a margin, or
record an indeterminate result); only programmer bugs raise.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class NoModelMatch(BaseModel):
    """No registered model matches an obligation's claim kind + inputs.

    An explicit, honest outcome (INV -- no silent pass): the registry
    turns it into an ``indeterminate`` evidence value rather than
    pretending the claim discharged.
    """

    model_config = ConfigDict(frozen=True)

    claim_kind: str
    reason: str
    considered: tuple[str, ...] = ()
    # WO-80 deliverable 3 (regolith/12 sec. 2 rung 5): the claim's
    # `model=<ident>` pin that produced this no-match, when the request
    # was pinned. `None` is the ordinary (un-pinned) no-model outcome;
    # non-`None` tells the registry to stamp the DISTINCT
    # `harness.model_pin_unmatched` indeterminate id instead of the
    # generic `harness.no_model` one -- "a forced model that cannot
    # close the margin yields indeterminate, not a pass," and never a
    # silent fallback to another model.
    pinned: str | None = None


class InputError(BaseModel):
    """A required model input is missing or malformed in the request."""

    model_config = ConfigDict(frozen=True)

    model_id: str
    missing: tuple[str, ...] = ()
    message: str


class DomainError(BaseModel):
    """The request falls outside a matched model's validity domain.

    Distinct from a violated claim: the model cannot speak here, so the
    discharge is ``indeterminate`` (regolith/07 sec. 4).
    """

    model_config = ConfigDict(frozen=True)

    model_id: str
    message: str


class SpawnFailed(BaseModel):
    """The subprocess solver executable could not be started (WO-20).

    An infrastructure failure, never a verdict: the registry maps it to
    the explicit ``harness.adapter_error`` indeterminate evidence value.
    """

    model_config = ConfigDict(frozen=True)

    argv: tuple[str, ...]
    message: str


class Timeout(BaseModel):
    """The subprocess solver exceeded its wall-clock ``timeout_s``.

    Maps to ``harness.adapter_error`` indeterminate -- a slow solver
    proves nothing either way (never a pass, never a violation).
    """

    model_config = ConfigDict(frozen=True)

    argv: tuple[str, ...]
    timeout_s: float


class MalformedResponse(BaseModel):
    """The solver's stdout was not a valid ``SolverResponse`` document.

    Covers unparseable JSON, schema-invalid payloads, non-finite float
    bits, and a non-deterministic solver omitting its settings digest
    (INV-10). Maps to ``harness.adapter_error`` indeterminate.
    """

    model_config = ConfigDict(frozen=True)

    argv: tuple[str, ...]
    message: str


class SchemaVersionMismatch(BaseModel):
    """The solver spoke a different wire ``schema_version`` than ours.

    AD-5 discipline at the subprocess seam: a version skew is an
    infrastructure failure (``harness.adapter_error`` indeterminate),
    never a silently reinterpreted payload.
    """

    model_config = ConfigDict(frozen=True)

    argv: tuple[str, ...]
    expected: int
    got: int


class NonzeroExit(BaseModel):
    """The solver exited nonzero -- an infrastructure failure by protocol.

    Exit code 0 covers ALL computed outcomes including a violated claim
    (design doc D-C); nonzero therefore never carries a verdict and maps
    to ``harness.adapter_error`` indeterminate.
    """

    model_config = ConfigDict(frozen=True)

    argv: tuple[str, ...]
    returncode: int
    message: str


# The union of subprocess-adapter failure values (WO-20): every arm maps
# to `harness.adapter_error` indeterminate evidence in the registry.
AdapterError = (
    SpawnFailed | Timeout | MalformedResponse | SchemaVersionMismatch | NonzeroExit
)

# The synthetic model id stamped on evidence produced when the adapter
# fails: an honest, greppable INDETERMINATE marker (the
# `harness.no_model` precedent), never a pass, never an exception.
ADAPTER_ERROR_ID = "harness.adapter_error"

# The union of harness error values, for annotating merged flows.
HarnessError = NoModelMatch | InputError | DomainError | AdapterError
