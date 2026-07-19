"""The one home for a unit-carrying artifact-rendering value (WO-150,
D262 ruling 1: STRUCTURAL enforcement).

Before this module, a handful of artifact-rendering interfaces accepted
a dimensioned quantity as two loose, independently-defaultable
primitives (a bare ``value: float`` next to a ``unit: str`` that could
be omitted, or -- worse, ``hdl.py``'s tier row -- a bare ``value: float``
with no unit field reachable AT ALL). Nothing stopped a caller from
constructing either shape with an absent unit and a renderer from
printing the resulting bare numeral straight into a calc sheet,
bring-up pack, drawing, or BOM view: exactly the F156 family the D256
hash window fixed for the Rust-side bound text, generalized here to
every Python-side artifact-rendering interface (D262).

:class:`DimensionedValue` makes that state unrepresentable: its ``unit``
field is REQUIRED and its validator rejects an empty string outright,
so a caller with a genuinely dimensionless magnitude (a build/sim
pass-fail encoding, a coverage ratio, a safety factor) must say so
explicitly via :data:`DIMENSIONLESS` -- absence is never an option
(the same unreachability doctrine as D246's "cannot forge a pass" and
D257 ruling 2's uncited-value refusal). This is a Python-side type,
not a schema change (D262/D265: no `.rgp`/L3 schema bump rides this
window); it exists purely to make renderer call sites refuse a bare
float at construction time.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator

# The explicit marker a genuinely unitless magnitude carries (D262
# ruling 1: "genuinely dimensionless values pass an EXPLICIT
# dimensionless unit, never an absent one"). Distinct in spelling and
# in meaning from `calc.py`'s `UNIT_UNREACHABLE` ("--"): that marker
# says "a unit exists but this renderer could not reach it"; this one
# says "there is no unit -- the quantity is a pure number by design."
# frob:doc docs/modules/py-backends.md#backends-quantity
DIMENSIONLESS = "1"


# frob:doc docs/modules/py-backends.md#backends-quantity
class DimensionedValue(BaseModel):
    """A magnitude that can only ever carry an explicit unit.

    ``magnitude`` is kept as verbatim text (the D265 representation
    choice this WO's structural half follows: the unit rides attached
    to the value's own text, never a separate re-derived field) so a
    renderer never re-normalizes a value it did not compute. ``unit``
    is REQUIRED and non-empty -- use :data:`DIMENSIONLESS` for a
    genuinely unitless magnitude, never an empty string.
    """

    model_config = ConfigDict(frozen=True)

    magnitude: str
    unit: str

    @model_validator(mode="after")
    def _unit_required(self) -> DimensionedValue:
        """Refuse construction outright when ``unit`` is blank.

        This is the structural refusal WO-150's negative test exercises:
        a bare-float-plus-hope call site is not a runtime possibility,
        it is a constructor error (D262 ruling 1).
        """
        if not self.unit.strip():
            raise ValueError(
                "DimensionedValue requires an explicit unit; pass "
                f"DIMENSIONLESS ({DIMENSIONLESS!r}) for a genuinely "
                "unitless magnitude, never an empty string"
            )
        return self

    # frob:doc docs/modules/py-backends.md#backends-quantity
    @classmethod
    def of(cls, magnitude: float | str, unit: str) -> DimensionedValue:
        """Construct from a numeric or textual magnitude plus its unit."""
        return cls(magnitude=str(magnitude), unit=unit)

    # frob:doc docs/modules/py-backends.md#backends-quantity
    @classmethod
    def dimensionless(cls, magnitude: float | str) -> DimensionedValue:
        """Construct an explicitly-marked dimensionless magnitude."""
        return cls(magnitude=str(magnitude), unit=DIMENSIONLESS)

    # frob:doc docs/modules/py-backends.md#backends-quantity
    def as_float(self) -> float:
        """The magnitude parsed back to ``float`` (callers that need
        the numeric value, e.g. re-serializing evidence bits)."""
        return float(self.magnitude)
