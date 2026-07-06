"""Elec realizer error VALUES (AD-7 / house style).

Every fallible realizer API returns a typani ``Result[T, E]`` whose
``E`` is one of these frozen models -- never a bare exception.
Exceptions are reserved for programmer bugs.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


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


class ArbitrationError(BaseModel):
    """A net has more than one driver pin (cuprite/06 pre-emission check)."""

    model_config = ConfigDict(frozen=True)

    net: str
    drivers: tuple[str, ...]
    message: str


class ToolUnavailable(BaseModel):
    """A vendor tool (kicad-cli, pcbnew) is not installed/reachable.

    An honest infrastructure gap, never faked: the caller maps this to
    indeterminate evidence, exactly like a WO-20 adapter ``SpawnFailed``.
    """

    model_config = ConfigDict(frozen=True)

    tool: str
    message: str


class LayoutFailed(BaseModel):
    """The layout subprocess ran but produced no usable artifact.

    Route failure is honest indeterminate (WO-24: "autorouting quality
    is NOT promised"), not an exception.
    """

    model_config = ConfigDict(frozen=True)

    stage: str  # "placement" | "routing" | "drc"
    message: str


class LayoutImportError(BaseModel):
    """A hand-edited layout re-imported for pinning failed to read/hash."""

    model_config = ConfigDict(frozen=True)

    path: str
    message: str


RealizerError = (
    NoFeasibleBinding
    | ArbitrationError
    | ToolUnavailable
    | LayoutFailed
    | LayoutImportError
)
