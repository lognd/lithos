"""WO-122 (F132.2): the ONE bound-resolution home never truncates.

:func:`regolith.orchestrator.translate._resolve_bound` is the single
crossing every scalar-comparison bound-text route uses (kwargs routes,
window halves, temporal reductions, the generic fallback, and
`mech.critical_speed`'s own route) to turn `<number> <unit>` and
one-multiplication scalar-arithmetic bound text into a resolved limit --
never a leading-float truncation (the WO-110 close-out's WO110-F1
evidence: `<= 0.10 mrad` read as unitless 0.10, `> 1.4 * 9200rpm`
truncated to 1.4). Units reduce through `regolith-qty`'s own table (the
ONE unit engine) via :func:`regolith.compiler.reduce_unit_literal`; a
route whose model natively speaks a non-SI port unit declares it
(`native_unit`), keeping limit and model output coherent.

WO122-F1 (escalated in the WO-122 close-out): rotational/angular-rate
spellings (`rpm`, `deg`) are NOT in `regolith-qty`'s table -- AD-9
requires an EXACT rational scale and their radian equivalents carry
irrational factors (2*pi/60, pi/180). `rpm` bounds resolve TODAY only
on the critical-speed route, whose pack port is rpm-native; a general
angular-rate ruling is a 02-quantity-core.md decision.
"""

from __future__ import annotations

from regolith.orchestrator.translate import _resolve_bound


def test_dimensionless_literal_unchanged() -> None:
    """A bare number (no unit token) resolves exactly as before WO-122
    (most fleet bounds, e.g. `civil.utilization(...) <= 1.0`)."""
    assert _resolve_bound("1.0") == (1.0, None)
    assert _resolve_bound(" -3.5e2 ") == (-350.0, None)


def test_percent_reads_as_dimensionless_fraction() -> None:
    """`%` is not in `regolith-qty`'s linear unit table; this module
    reads it as a dimensionless fraction (`_parse_tolerance`'s existing
    convention elsewhere in this file), not a deferral."""
    assert _resolve_bound("70%") == (0.7, None)


def test_si_unit_literal_resolves_through_regolith_qty() -> None:
    """A registered SI unit (with prefix) reduces to its SI magnitude
    via the ONE crossing (`regolith.compiler.reduce_unit_literal`),
    the same table L1 quantity literals resolve through."""
    assert _resolve_bound("10 kohm") == (10_000.0, None)
    value, reason = _resolve_bound("2A")
    assert reason is None
    assert value is not None and abs(value - 2.0) < 1e-12


def test_sf_suffix_stripped_before_resolution() -> None:
    """A trailing `, sf=...`/`, scatter_factor=...` claim-metadata
    suffix is stripped before the bound itself is read (existing
    convention this module already carried)."""
    assert _resolve_bound("25N, sf=1.5") == (25.0, None)


def test_trailing_given_suffix_ignored() -> None:
    """A claim-suffix `given x = y` binding rides on later lines of
    the bound text (WO-94 escalation 1's lowering shape); only the
    first line is the bound."""
    assert _resolve_bound("3.4\n               given range_state = race") == (
        3.4,
        None,
    )


def test_scalar_arithmetic_bound_resolves_one_multiplication() -> None:
    """`<number> * <number><unit>` (WO110-F1's evidence shape) reduces
    to the product's SI value when the unit itself is registered."""
    value, reason = _resolve_bound("2 * 5kohm")
    assert reason is None
    assert value == 10_000.0


def test_dimensional_multiplication_defers_named() -> None:
    """Two unit-bearing operands (`<n><u1> * <n><u2>`) are NOT the
    supported scalar-arithmetic shape (one side must be a bare
    scalar); this defers named, never guesses a product unit."""
    assert _resolve_bound("2ohm * 5A") == (None, "bound_expression_unresolved")


def test_unrecognized_shape_defers_bound_expression_unresolved() -> None:
    """A record ref / multi-operator expression is not one of the two
    supported literal shapes -- named deferral, the D103 class stays on
    its own existing resolution path (per this WO's escalation note)."""
    assert _resolve_bound("material.sigma_y / 2.5") == (
        None,
        "bound_expression_unresolved",
    )


def test_unknown_unit_defers_bound_unit_unresolved_never_truncated() -> None:
    """A log-ratio spelling (`dB`) is a `<number> <unit>`-shaped bound
    `regolith-qty` does not know as a linear unit -- named deferral,
    never the pre-WO-122 truncation (`_parse_float` would have kept
    the leading `60`, silently dropping the unit)."""
    assert _resolve_bound("60dB") == (None, "bound_unit_unresolved")


def test_rotational_unit_off_its_native_route_defers_named() -> None:
    """`rpm` outside the critical-speed route (no `native_unit`
    declared) stays an honest named deferral: its radian equivalent is
    irrational (WO122-F1), and guessing a convention would be a wrong
    limit -- exactly what F132.2 forbids."""
    assert _resolve_bound("9200rpm") == (None, "bound_unit_unresolved")
    assert _resolve_bound("-3.5 deg") == (None, "bound_unit_unresolved")


def test_wo110_f1_twist_example_resolves_exactly() -> None:
    """WO110-F1 example 1 / WO-122 acceptance: `<= 0.10 mrad` resolves
    to exactly 1.0e-4 rad (the twist model is radians-native, SI) --
    `rad` is dimensionless at exact scale 1 in `regolith-qty`'s table,
    and `mrad` reduces through the ordinary milli prefix. Never again
    the unitless 0.10 the pre-WO-122 leading-float read produced."""
    value, reason = _resolve_bound("0.10 mrad")
    assert reason is None
    assert value == 0.10 * 1e-3  # exactly 1.0e-4 rad


def test_wo110_f1_critical_speed_example_resolves_exactly() -> None:
    """WO110-F1 example 2 / WO-122 acceptance: `> 1.4 * 9200rpm` on
    the critical-speed route (which declares `rpm` as its pack port's
    native unit -- feldspar's output port is `mech.critical_speed.rpm`)
    resolves to exactly 1.4 * 9200 = 12880 rpm, the model-coherent
    angular-rate limit. Never again the truncated 1.4 the pre-WO-122
    leading-float read froze into a golden."""
    value, reason = _resolve_bound("1.4 * 9200rpm", native_unit="rpm")
    assert reason is None
    assert value == 1.4 * 9200  # exactly 12880 rpm, the pack's port unit
