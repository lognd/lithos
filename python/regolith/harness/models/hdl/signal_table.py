"""WO-155 (D264): the `signal_table` stimulus/expectation payload kind.

Charter 38 sec. 5 registry addition (`docs/spec/toolchain/38-emission-
and-artifacts.md`): a `RealizedInput`/payload kind carrying hash-pinned
directed stimulus/expectation vectors for a behavioral HDL subject
(cuprite/03 sec. 2's `require: sim(<stimulus-ref>)` clause resolves by
digest to exactly this shape), plus the D260/D260.3 seam's provenance/
trust-tier fields.

Evidence-honesty posture (INV-35 leg (b), D260 ruling 3): an authored
(hand-drawn/hand-typed) stimulus can never carry, or upgrade to, a
model-backed or measured trust tier. This is enforced BY
UNREACHABILITY (the D257 citation-less-value pattern), not by a runtime
check alone: :class:`SignalTable`'s constructor rejects any
``trust_tier`` outside the authored vocabulary at validation time --
there is no code path that can construct one with a stronger tier.
``check_signal_table_provenance`` is the belt to that suspenders (the
untrusted-JSON-on-disk half): a stimulus artifact whose raw payload
carries no provenance fields at all, or a malformed/foreign tier
string, is refused with E1105 (`STIMULUS_PROVENANCE_UNAUTHORED`)
before it ever reaches the pydantic constructor.
"""

from __future__ import annotations

import json

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from typani.result import Err, Ok, Result

from regolith._codes import STIMULUS_PROVENANCE_UNAUTHORED
from regolith.harness.errors import DomainError
from regolith.logging_setup import get_logger

_log = get_logger(__name__)

# --- D260 ruling 3 / D260.3 trust-tier vocabulary ---------------------

# frob:doc docs/modules/py-harness.md#models-hdl
TRUST_TIER_AUTHORED = "authored"
# frob:doc docs/modules/py-harness.md#models-hdl
TRUST_TIER_ASSERTED = "asserted"
# frob:doc docs/modules/py-harness.md#models-hdl
AUTHORED_TRUST_TIERS = frozenset({TRUST_TIER_AUTHORED, TRUST_TIER_ASSERTED})


# frob:doc docs/modules/py-harness.md#models-hdl
class Port(BaseModel):
    """One DUT port a `signal_table` stimulus drives or observes."""

    model_config = ConfigDict(frozen=True)

    name: str
    width: int = 1
    direction: str  # "in" | "out" -- a plain str (not Literal) so a
    # malformed value is a normal pydantic ValidationError, matching
    # this module's other fields.


# frob:doc docs/modules/py-harness.md#models-hdl
class InputAssignment(BaseModel):
    """One `<signal> = <value>` assignment at a directed vector's cycle."""

    model_config = ConfigDict(frozen=True)

    signal: str
    value: str  # kept as source text (a Verilog literal, e.g. "8'hFE")
    # -- D96 payload posture: no numeric coercion at this layer.


# frob:doc docs/modules/py-harness.md#models-hdl
class ExpectedWindow(BaseModel):
    """One `<signal>` output expectation at a directed vector's cycle."""

    model_config = ConfigDict(frozen=True)

    signal: str
    expected: str


# frob:doc docs/modules/py-harness.md#models-hdl
class DirectedVector(BaseModel):
    """One cycle of a directed stimulus: inputs to assert, outputs to check."""

    model_config = ConfigDict(frozen=True)

    name: str
    inputs: tuple[InputAssignment, ...] = ()
    expect: tuple[ExpectedWindow, ...] = ()


# frob:doc docs/modules/py-harness.md#models-hdl
class SignalTable(BaseModel):
    """The `signal_table` payload (WO-155/D264): a hash-pinned directed
    stimulus/expectation vector table for one HDL subject, v1 = directed
    vectors only (D264 ruling 2 -- constrained-random is a later WO).

    ``trust_tier`` is constrained to the D260 ruling 3 authored-only
    vocabulary BY CONSTRUCTION (unrepresentability, INV-35 leg (b)): no
    constructor path accepts ``"model"``/``"measured"`` for this payload
    kind, ever.
    """

    model_config = ConfigDict(frozen=True)

    top_module: str
    clock: str | None = None
    reset: str | None = None
    ports: tuple[Port, ...] = Field(default_factory=tuple)
    vectors: tuple[DirectedVector, ...]
    method: str
    trust_tier: str

    @field_validator("trust_tier")
    @classmethod
    def _authored_only(cls, value: str) -> str:
        if value not in AUTHORED_TRUST_TIERS:
            raise ValueError(
                f"signal_table trust_tier must be one of "
                f"{sorted(AUTHORED_TRUST_TIERS)} (an authored/drawn "
                "stimulus can never claim model-backed/measured, D260 "
                f"ruling 3); got {value!r}"
            )
        return value

    @field_validator("vectors")
    @classmethod
    def _at_least_one_vector(
        cls, value: tuple[DirectedVector, ...]
    ) -> tuple[DirectedVector, ...]:
        if not value:
            raise ValueError("signal_table must declare at least one directed vector")
        return value


# frob:doc docs/modules/py-harness.md#models-hdl
# frob:waive TEST001 reason="exercised transitively through HdlSimAssertGenericModel.estimate + its own harness-model tests; no isolated unit test calls it directly"
def check_signal_table_provenance(raw: bytes) -> Result[SignalTable, DomainError]:
    """Parse ``raw`` bytes as a `signal_table` payload, refusing (E1105,
    `STIMULUS_PROVENANCE_UNAUTHORED`) any stimulus artifact whose
    provenance is absent or whose declared tier is outside the
    authored-only vocabulary -- the untrusted-JSON-on-disk half of
    INV-35 leg (b); :class:`SignalTable`'s own field validator is the
    unrepresentability half (see module docstring)."""
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        _log.error("check_signal_table_provenance: not JSON: %s", exc)
        return Err(
            DomainError(
                model_id="std.hdl.signal_table",
                message=f"stimulus payload is not JSON: {exc}",
            )
        )
    if "trust_tier" not in payload or "method" not in payload:
        _log.error(
            "check_signal_table_provenance: %s (E1105 %s)",
            "no provenance/authored-tier record",
            STIMULUS_PROVENANCE_UNAUTHORED,
        )
        return Err(
            DomainError(
                model_id="std.hdl.signal_table",
                message=(
                    f"{STIMULUS_PROVENANCE_UNAUTHORED}: stimulus payload "
                    "carries no provenance/authored-tier record (method/"
                    "trust_tier fields required, D260 ruling 3)"
                ),
            )
        )
    try:
        table = SignalTable.model_validate(payload)
    except ValidationError as exc:
        _log.error(
            "check_signal_table_provenance: %s (E1105 %s): %s",
            "malformed or non-authored provenance",
            STIMULUS_PROVENANCE_UNAUTHORED,
            exc,
        )
        return Err(
            DomainError(
                model_id="std.hdl.signal_table",
                message=f"{STIMULUS_PROVENANCE_UNAUTHORED}: {exc}",
            )
        )
    _log.debug(
        "check_signal_table_provenance: authored-tier stimulus ok (%d vector(s))",
        len(table.vectors),
    )
    return Ok(table)
