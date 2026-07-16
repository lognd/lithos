"""Tests for `regolith.backends.quantity.DimensionedValue` (WO-150).

The structural half of D262: an artifact-rendering interface that
accepts a dimensioned value must refuse a bare-float-plus-hope call
site at construction time, not merely document the refusal. These
tests are the acceptance criterion's negative test
(`uv run pytest -k unit_enforcement -q`).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from regolith.backends.hdl import HdlTierRow
from regolith.backends.instructions import FastenerCallout
from regolith.backends.quantity import DIMENSIONLESS, DimensionedValue


def test_unit_enforcement_bare_float_construction_is_a_type_error() -> None:
    """Constructing a `DimensionedValue` with an empty unit is refused."""
    with pytest.raises(ValidationError):
        DimensionedValue(magnitude="5", unit="")


def test_unit_enforcement_blank_unit_is_also_refused() -> None:
    """Whitespace-only is not a loophole around the empty-string check."""
    with pytest.raises(ValidationError):
        DimensionedValue(magnitude="5", unit="   ")


def test_unit_enforcement_explicit_dimensionless_marker_is_accepted() -> None:
    """A genuinely unitless magnitude passes the explicit marker, never
    an absent unit (D262 ruling 1)."""
    qty = DimensionedValue.dimensionless(0.87)
    assert qty.unit == DIMENSIONLESS
    assert qty.as_float() == 0.87


def test_unit_enforcement_explicit_unit_round_trips() -> None:
    qty = DimensionedValue.of(45.0, "ohm")
    assert qty.magnitude == "45.0"
    assert qty.unit == "ohm"
    assert qty.as_float() == 45.0


def test_unit_enforcement_hdl_tier_row_refuses_a_bare_float() -> None:
    """`HdlTierRow` (WO-150 structural half: it used to carry a bare
    `value: float`/`margin: float` with NO unit field reachable at
    all) now requires `DimensionedValue` -- passing a bare float is a
    constructor/type error, not a runtime possibility."""
    with pytest.raises((ValidationError, TypeError)):
        HdlTierRow(
            claim="hdl.build",
            status="discharged",
            model_id="hdl_build@1+verilator5.047",
            value=0.0,  # bare float where DimensionedValue is required
            margin=0.0,
            tool="verilator",
            tool_version="5.047",
        )


def test_unit_enforcement_fastener_callout_refuses_a_bare_float() -> None:
    """`FastenerCallout` (WO-150 structural half: it used to carry a
    bare `value: float` next to an independently-defaultable
    `unit: str`) now requires one atomic `DimensionedValue`."""
    with pytest.raises((ValidationError, TypeError)):
        FastenerCallout(
            claim_label="residual clamp force (VDI 2230)",
            value=13200.0,  # bare float, no unit -- refused
            model_id="bolted_joint_separation_vdi2230@1",
            evidence_hash="blake3:deadbeef",
        )
