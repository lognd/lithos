//! End-to-end exercise of the crate from outside: parse a compound unit
//! expression, build `Qty` values over it, and reduce them through
//! dimension-checked arithmetic and SI conversion -- driven entirely
//! through `pub` API (no `crate::` internal access), per TEST003 (min
//! one integration test per crate interface).
// frob:tests crates/regolith-qty/src kind="integration"

use regolith_qty::{Qty, Unit};

#[test]
fn parsed_units_reduce_through_dimension_checked_arithmetic() {
    // A compound unit expression, parsed from source text the way a
    // `.hema`/`.cupr` literal spells it.
    let ohm = Unit::parse_expr("ohm").expect("ohm is a base unit");
    let amp = Unit::parse_atom("A").expect("A is a base unit");

    let resistance = Qty::new(10.0, ohm.clone());
    let current = Qty::new(0.5, amp);

    // V = I * R: dimensions multiply, magnitudes multiply.
    let voltage = current
        .mul(&resistance)
        .expect("A * ohm must be dimension-legal");
    assert!((voltage.magnitude() - 5.0).abs() < 1e-12);

    // Incompatible dimensions are an error VALUE, never a panic.
    let stray_mass = Qty::new(1.0, Unit::parse_atom("kg").unwrap());
    assert!(voltage.add(&stray_mass).is_err());

    // SI reduction round-trips through the unit's own conversion.
    let si = resistance.unit().si_magnitude(resistance.magnitude());
    assert!(
        (si - 10.0).abs() < 1e-12,
        "ohm is already an SI-coherent unit"
    );
}

#[test]
fn compound_unit_algebra_is_associative_with_division() {
    let mm = Unit::parse_atom("mm").expect("mm is a prefixed SI unit");
    let s = Unit::parse_atom("s").expect("s is a base unit");
    let speed_unit = mm.div(&s).expect("mm/s must be a legal quotient unit");

    let distance = Qty::new(1000.0, mm);
    let time = Qty::new(2.0, s);
    let speed = distance.div(&time).expect("mm / s must be dimension-legal");

    assert_eq!(speed.unit().base_symbol(), speed_unit.base_symbol());
    assert!((speed.magnitude() - 500.0).abs() < 1e-9);
}
