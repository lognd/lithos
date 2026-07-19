"""Elec realizer error VALUES (AD-7 / house style).

Every fallible realizer API returns a typani ``Result[T, E]`` whose
``E`` is one of these frozen models -- never a bare exception.
Exceptions are reserved for programmer bugs.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


# frob:doc docs/modules/py-realizer.md#elec-errors
class NoFeasibleBinding(BaseModel):
    """The allocation search exhausted every candidate for a block.

    Carries the accumulated nogoods (D75: solver state, never written
    to the lockfile) so the caller can report why every record was
    ruled out.
    """

    model_config = ConfigDict(frozen=True)

    block: str
    nogoods_considered: int
    message: str


# frob:doc docs/modules/py-realizer.md#elec-errors
class ArbitrationError(BaseModel):
    """A net has more than one driver pin (cuprite/06 pre-emission check)."""

    model_config = ConfigDict(frozen=True)

    net: str
    drivers: tuple[str, ...]
    message: str


# frob:doc docs/modules/py-realizer.md#elec-errors
class LockedPinInfeasible(BaseModel):
    """A `locked: pinmux(...)` pin carries no instance the demand needs.

    Named distinctly from :class:`NoFeasiblePinmux` (cuprite/04 sec. 1
    step 2 deliverable 3): "the human's lock, the machine's
    counterexample" -- the lock itself is the cause, not a generic
    search exhaustion.
    """

    model_config = ConfigDict(frozen=True)

    flow: str
    pin: str
    kind: str
    message: str


# frob:doc docs/modules/py-realizer.md#elec-errors
class NoFeasiblePinmux(BaseModel):
    """The pin-mux search exhausted every legal assignment for `flows`.

    ``flows`` names one flow (generic exhaustion) or two (a named
    contention -- "both flows need the only DMA-capable SPI").
    """

    model_config = ConfigDict(frozen=True)

    flows: tuple[str, ...]
    kind: str
    message: str


# frob:doc docs/modules/py-realizer.md#elec-errors
class ToolUnavailable(BaseModel):
    """A vendor tool (kicad-cli, pcbnew) is not installed/reachable.

    An honest infrastructure gap, never faked: the caller maps this to
    indeterminate evidence, exactly like a WO-20 adapter ``SpawnFailed``.
    """

    model_config = ConfigDict(frozen=True)

    tool: str
    message: str


# frob:doc docs/modules/py-realizer.md#elec-errors
class LayoutFailed(BaseModel):
    """The layout subprocess ran but produced no usable artifact.

    Route failure is honest indeterminate (WO-24: "autorouting quality
    is NOT promised"), not an exception.
    """

    model_config = ConfigDict(frozen=True)

    stage: str  # "placement" | "routing" | "drc"
    message: str


# frob:doc docs/modules/py-realizer.md#elec-errors
class LayoutImportError(BaseModel):
    """A hand-edited layout re-imported for pinning failed to read/hash."""

    model_config = ConfigDict(frozen=True)

    path: str
    message: str


RealizerError = (
    NoFeasibleBinding
    | ArbitrationError
    | LockedPinInfeasible
    | NoFeasiblePinmux
    | ToolUnavailable
    | LayoutFailed
    | LayoutImportError
)
