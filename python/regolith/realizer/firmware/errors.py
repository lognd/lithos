"""Firmware realizer error VALUES (AD-7 / house style).

Every fallible realizer API returns a typani ``Result[T, E]`` whose
``E`` is one of these frozen models -- never a bare exception.
Exceptions are reserved for programmer bugs.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class UnknownFamily(BaseModel):
    """No MCU-family pack is installed for the design's declared family.

    D109: "a design whose MCU family has no pack is honest
    indeterminate on the codegen step, never a guess."
    """

    model_config = ConfigDict(frozen=True)

    family: str
    message: str


class InterruptCapabilityMissing(BaseModel):
    """An `on <event>` handler has no interrupt-capable pin assignment.

    Names the event and the pin fact so the diagnostic is
    constructive (WO-37 acceptance criterion 3): interrupt capability
    is a component-record fact (WO-35's model), never guessed here.
    """

    model_config = ConfigDict(frozen=True)

    event: str
    pin: str | None
    message: str


class PartitionOverlap(BaseModel):
    """Two declared `partitions:` regions contest the same address range."""

    model_config = ConfigDict(frozen=True)

    region: str
    first: str
    second: str
    message: str
