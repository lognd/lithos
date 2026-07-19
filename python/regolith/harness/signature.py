"""Model signatures: the typed contract the registry matches against.

A signature is the harness-side half of the spec's model registry
(regolith/07 sec. 3): what claim a model discharges, which inputs it
needs, and the validity-domain tags it declares. It is deliberately a
Python-native model (not the generated ``_schema.Signature``, which is
the Rust-side interchange record for `impl ... by` declarations): the
harness owns the executable code and its matching predicate.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from pydantic import BaseModel, ConfigDict, Field


# frob:doc docs/modules/py-harness.md#signature
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
    # frob:doc docs/modules/py-harness.md#signature
    def upper_bound(cls) -> ClaimSense:
        """A ``value < limit`` claim."""
        return cls(upper=True)

    @classmethod
    # frob:doc docs/modules/py-harness.md#signature
    def lower_bound(cls) -> ClaimSense:
        """A ``value > limit`` claim."""
        return cls(upper=False)


# frob:doc docs/modules/py-harness.md#signature
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
    payload_kinds: Mapping[str, str] = Field(
        default_factory=dict,
        description="Required payload ports (D96, sec. 8.3): port name -> "
        "the payload kind demanded (feldspar 09 sec. 4 vocabulary).",
    )
    required_regimes: tuple[str, ...] = Field(
        default=(),
        description="Validity-domain regime tags required (D97, sec. 8.4): "
        "`linear_elastic`, `static`, ...; a request missing one is a "
        "non-match, never an assumption.",
    )

    # frob:doc docs/modules/py-harness.md#signature
    def accepts(self, available: Iterable[str]) -> bool:
        """True iff every required scalar input is present in ``available``.

        Scalar-only check (payload kinds and regimes are matched
        separately by :meth:`accepts_payloads`/:meth:`accepts_regimes`,
        composed in :meth:`matches`).
        """
        have = set(available)
        return all(port in have for port in self.inputs)

    # frob:doc docs/modules/py-harness.md#signature
    def missing(self, available: Iterable[str]) -> tuple[str, ...]:
        """The required scalar inputs absent from ``available`` (deterministic)."""
        have = set(available)
        return tuple(port for port in self.inputs if port not in have)

    # frob:doc docs/modules/py-harness.md#signature
    def accepts_payloads(self, available: Mapping[str, str]) -> bool:
        """True iff every required payload port is present with its kind.

        ``available`` maps a request's carried payload port names to
        their kind (D96): a port present with the WRONG kind is as much
        a non-match as an absent port (honest, never a silent
        reinterpretation).
        """
        return all(
            available.get(port) == kind for port, kind in self.payload_kinds.items()
        )

    # frob:doc docs/modules/py-harness.md#signature
    # frob:waive TEST001 reason="thin accessor, tested transitively via harness tests"
    def accepts_regimes(self, available: Iterable[str]) -> bool:
        """True iff every required regime tag is present in ``available``.

        D97: a model whose validity domain requires an absent regime
        tag is a non-match -- never an assumption.
        """
        have = set(available)
        return all(tag in have for tag in self.required_regimes)
