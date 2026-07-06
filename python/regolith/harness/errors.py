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


# The union of harness error values, for annotating merged flows.
HarnessError = NoModelMatch | InputError | DomainError
