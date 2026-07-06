"""Model signatures: the typed contract the registry matches against.

A signature is the harness-side half of the spec's model registry
(regolith/07 sec. 3): what claim a model discharges, which inputs it
needs, and the validity-domain tags it declares. It is deliberately a
Python-native model (not the generated ``_schema.Signature``, which is
the Rust-side interchange record for `impl ... by` declarations): the
harness owns the executable code and its matching predicate.
"""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field


class ClaimSense(BaseModel):
    """Which direction a scalar claim bounds its quantity.

    ``upper`` = the predicted quantity must stay BELOW the limit
    (``value < limit``, e.g. ripple, stress, dissipation); ``lower`` = it
    must stay ABOVE (``value > limit``, e.g. efficiency, first mode). The
    sense selects which way the model's ``eps`` is charged against the
    margin (regolith/07 sec. 4).
    """

    model_config = ConfigDict(frozen=True)

    upper: bool

    @classmethod
    def upper_bound(cls) -> ClaimSense:
        """A ``value < limit`` claim."""
        return cls(upper=True)

    @classmethod
    def lower_bound(cls) -> ClaimSense:
        """A ``value > limit`` claim."""
        return cls(upper=False)


class ModelSignature(BaseModel):
    """A model's input/output contract keyed by the claim kind it serves."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(description="Signature name (matches the model id).")
    claim_kind: str = Field(
        description="The obligation claim kind this signature discharges "
        "(the registry lookup key, e.g. `elec.buck.output_voltage_ripple`)."
    )
    sense: ClaimSense = Field(
        description="Whether the claim is an upper or lower bound."
    )
    inputs: tuple[str, ...] = Field(
        description="Required input port names (all must be present to match)."
    )
    domain: tuple[str, ...] = Field(
        default=(), description="Validity-domain tags (`buck`, `ccm`, ...)."
    )

    def accepts(self, available: Iterable[str]) -> bool:
        """True iff every required input is present in ``available``."""
        have = set(available)
        return all(port in have for port in self.inputs)

    def missing(self, available: Iterable[str]) -> tuple[str, ...]:
        """The required inputs absent from ``available`` (deterministic order)."""
        have = set(available)
        return tuple(port for port in self.inputs if port not in have)
