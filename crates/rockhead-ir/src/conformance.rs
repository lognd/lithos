//! T1 conformance and refinement checking: role-kind by construction,
//! parameter match, capability-vs-demand, and the promise-refinement
//! direction rule.
//!
//! Substrate reference: `docs/substrate/04-contracts.md`. Refinement is
//! directional: a refined interface makes TIGHTER demands on itself and
//! STRONGER promises to consumers, so an impl may only NARROW a promise.
//! Widening a promise is rejected (WO-12 acceptance). Capability tables
//! are WO-16 data; a static in-memory pack backs the tests.

use rockhead_diag::{codes, Diagnostic};
use rockhead_util::IndexMap;

use crate::nodes::{Impl, Interface, PromiseSlot};

/// Check that an impl's role bindings resolve to entities of the kinds
/// the interface's roles require (role-kind by construction).
///
/// This IR's `Interface::roles` carries only role *names*
/// (`docs/substrate/04-contracts.md` sec. 1: `roles: bore: cylindrical(d=d)`
/// -- the per-role predicate/kind is not yet a modeled field on this
/// node). What IS checkable by construction from the fields this crate
/// carries: every declared role has exactly one binding, and no binding
/// names an undeclared role -- a role bound zero or more-than-once times,
/// or a binding naming a role the interface never declared, is rejected.
/// Kind-vs-predicate matching proper is left for the role-kind data to
/// land on `Interface`/`Impl` (tracked as a follow-on, out of this
/// stub's scope).
#[must_use]
pub fn check_role_kind(iface: &Interface, imp: &Impl) -> Vec<Diagnostic> {
    let mut diags = Vec::new();

    // Source-order count of how many times each bound role name appears.
    let mut bound_counts: IndexMap<&str, usize> = IndexMap::new();
    for (role, _query) in &imp.role_bindings {
        *bound_counts.entry(role.as_str()).or_insert(0) += 1;
        if !iface.roles.iter().any(|r| r == role) {
            diags.push(Diagnostic::error(
                codes::CAPABILITY_VS_DEMAND,
                format!(
                    "impl of `{}` binds role `{role}`, which the interface does not declare",
                    iface.name
                ),
            ));
        }
    }

    for role in &iface.roles {
        match bound_counts.get(role.as_str()) {
            None | Some(0) => diags.push(Diagnostic::error(
                codes::CAPABILITY_VS_DEMAND,
                format!("impl of `{}` leaves role `{role}` unbound", iface.name),
            )),
            Some(n) if *n > 1 => diags.push(Diagnostic::error(
                codes::CAPABILITY_VS_DEMAND,
                format!(
                    "impl of `{}` binds role `{role}` {n} times (a role binds exactly once)",
                    iface.name
                ),
            )),
            Some(_) => {}
        }
    }

    diags
}

/// Check that an impl's parameters match the interface's; a binding may
/// pin a free variable but may not conflict with a fixed one.
///
/// This IR does not yet carry a `params:` field on `Interface` or
/// `Impl` (substrate/04 sec. 1: the impl-chosen `params:` block distinct
/// from caller-chosen `<params>`) -- there is no parameter data on
/// either node for this stub to compare. Returns no diagnostics
/// (vacuously true) rather than inventing a parameter representation
/// this WO's node types do not declare; wiring `params:` through
/// `Interface`/`Impl` is a follow-on, not this stub's call to make.
#[must_use]
pub fn check_param_match(_iface: &Interface, _imp: &Impl) -> Vec<Diagnostic> {
    Vec::new()
}

/// A minimal capability record for the static test pack (WO-16 supplies
/// the real table).
#[derive(Debug, Clone)]
pub struct Capability {
    /// The demand name this capability answers.
    pub demand: String,
    /// Whether the capability meets the demand.
    pub meets: bool,
}

/// Check demanded capabilities against supplied ones (E0410 when a
/// demand exceeds the supply).
///
/// Walks `demands` in source order (AD-6); a demand with no matching,
/// meeting entry in `supplied` is E0410. When more than one supplied
/// entry answers the same demand name, the first match in source order
/// decides (deterministic tie-break, no `HashMap` involved).
#[must_use]
pub fn check_capability_vs_demand(demands: &[String], supplied: &[Capability]) -> Vec<Diagnostic> {
    let mut diags = Vec::new();
    for demand in demands {
        let meets = supplied
            .iter()
            .find(|c| &c.demand == demand)
            .is_some_and(|c| c.meets);
        if !meets {
            diags.push(Diagnostic::error(
                codes::CAPABILITY_VS_DEMAND,
                format!("demand `{demand}` exceeds the supplied capability"),
            ));
        }
    }
    diags
}

/// Check promise refinement direction: the refined promises must be at
/// least as strong (narrower) as the base. A WIDENED promise is rejected.
///
/// Walks `base` in source order (AD-6); a refined slot with no matching
/// name in `base` is a pure addition (not a refinement of anything) and
/// is not checked here. Only value-source shapes this crate can compare
/// without a unit-conversion table (matching unit symbol, matching
/// dimension) are judged; shapes it cannot soundly compare (mismatched
/// units, or a non-comparable value-source variant such as `free` vs
/// `derived`) are left unflagged rather than guessed at, to avoid a
/// false-positive rejection.
#[must_use]
pub fn check_refinement(base: &[PromiseSlot], refined: &[PromiseSlot]) -> Vec<Diagnostic> {
    let mut diags = Vec::new();
    for b in base {
        let Some(r) = refined.iter().find(|r| r.name == b.name) else {
            continue;
        };
        if let Some(reason) = widening_reason(&b.value, &r.value) {
            diags.push(Diagnostic::error(
                codes::CAPABILITY_VS_DEMAND,
                format!(
                    "promise `{}` widens the base interface's promise: {reason}",
                    b.name
                ),
            ));
        }
    }
    diags
}

/// Compare a base and refined promise's value sources; `Some(reason)`
/// when the refined side is strictly WIDER (illegal), `None` when it
/// narrows or is not comparable with the data this crate has.
fn widening_reason(
    base: &rockhead_qty::ValueSource,
    refined: &rockhead_qty::ValueSource,
) -> Option<String> {
    use rockhead_qty::{Comparator, Literal, ValueSource};

    match (base, refined) {
        (
            ValueSource::Literal(Literal::Comparator(Comparator::AtLeast(b))),
            ValueSource::Literal(Literal::Comparator(Comparator::AtLeast(r))),
        ) if same_unit(b, r) && r.magnitude() < b.magnitude() => Some(format!(
            "floor weakened from >= {} {} to >= {} {}",
            b.magnitude(),
            b.unit().symbol,
            r.magnitude(),
            r.unit().symbol
        )),
        (
            ValueSource::Literal(Literal::Comparator(Comparator::AtMost(b))),
            ValueSource::Literal(Literal::Comparator(Comparator::AtMost(r))),
        ) if same_unit(b, r) && r.magnitude() > b.magnitude() => Some(format!(
            "ceiling loosened from <= {} {} to <= {} {}",
            b.magnitude(),
            b.unit().symbol,
            r.magnitude(),
            r.unit().symbol
        )),
        (ValueSource::Literal(Literal::Scatter(b)), ValueSource::Literal(Literal::Scatter(r)))
            if same_interval_unit(b, r)
                && (r.lo().magnitude() < b.lo().magnitude()
                    || r.hi().magnitude() > b.hi().magnitude()) =>
        {
            Some(format!(
                "scatter widened from [{}, {}] to [{}, {}] {}",
                b.lo().magnitude(),
                b.hi().magnitude(),
                r.lo().magnitude(),
                r.hi().magnitude(),
                b.unit().symbol
            ))
        }
        _ => None,
    }
}

/// True when two quantities share a unit symbol (safe to compare
/// magnitudes directly; no cross-unit conversion is exposed to this
/// crate).
fn same_unit(a: &rockhead_qty::Qty, b: &rockhead_qty::Qty) -> bool {
    a.unit().symbol == b.unit().symbol
}

/// True when two intervals share a unit symbol.
fn same_interval_unit(a: &rockhead_qty::Interval, b: &rockhead_qty::Interval) -> bool {
    a.unit().symbol == b.unit().symbol
}

#[cfg(test)]
mod tests {
    use super::{
        check_capability_vs_demand, check_param_match, check_refinement, check_role_kind,
        Capability,
    };
    use crate::nodes::{Impl, Interface, PromiseSlot};
    use num_rational::Ratio;
    use rockhead_diag::codes;
    use rockhead_qty::{
        BaseDimension, Comparator, Dimension, Interval, Literal, Qty, Unit, ValueSource,
    };
    use rockhead_sem::Query;

    fn newtons_per_mm() -> Unit {
        Unit {
            symbol: "N/mm".to_string(),
            dimension: Dimension::base(BaseDimension::Mass),
            scale: Ratio::from_integer(1),
            offset: Ratio::from_integer(0),
        }
    }

    fn at_least(x: f64) -> ValueSource {
        ValueSource::Literal(Literal::Comparator(Comparator::AtLeast(Qty::new(
            x,
            newtons_per_mm(),
        ))))
    }

    fn query(name: &str) -> Query {
        Query {
            base: name.to_string(),
            ops: Vec::new(),
        }
    }

    // Widening rejected / narrowing accepted (WO-12 acceptance).
    #[test]
    fn refinement_direction_enforced() {
        let base = vec![PromiseSlot {
            name: "stiffness".to_string(),
            value: at_least(80.0),
        }];

        // Narrowing (stronger floor) is accepted.
        let narrowed = vec![PromiseSlot {
            name: "stiffness".to_string(),
            value: at_least(100.0),
        }];
        assert!(check_refinement(&base, &narrowed).is_empty());

        // Widening (weaker floor) is rejected.
        let widened = vec![PromiseSlot {
            name: "stiffness".to_string(),
            value: at_least(50.0),
        }];
        let diags = check_refinement(&base, &widened);
        assert_eq!(diags.len(), 1);
        assert_eq!(diags[0].code, codes::CAPABILITY_VS_DEMAND);
        assert!(diags[0].message.contains("stiffness"));

        // Exact equality is neither wider nor narrower: accepted.
        let same = vec![PromiseSlot {
            name: "stiffness".to_string(),
            value: at_least(80.0),
        }];
        assert!(check_refinement(&base, &same).is_empty());
    }

    #[test]
    fn scatter_refinement_subset_narrows_superset_widens() {
        let base = vec![PromiseSlot {
            name: "wall".to_string(),
            value: ValueSource::Literal(Literal::Scatter(
                Interval::new(
                    &Qty::new(3.0, newtons_per_mm()),
                    &Qty::new(5.0, newtons_per_mm()),
                )
                .unwrap(),
            )),
        }];
        let narrower = vec![PromiseSlot {
            name: "wall".to_string(),
            value: ValueSource::Literal(Literal::Scatter(
                Interval::new(
                    &Qty::new(3.5, newtons_per_mm()),
                    &Qty::new(4.5, newtons_per_mm()),
                )
                .unwrap(),
            )),
        }];
        assert!(check_refinement(&base, &narrower).is_empty());

        let wider = vec![PromiseSlot {
            name: "wall".to_string(),
            value: ValueSource::Literal(Literal::Scatter(
                Interval::new(
                    &Qty::new(2.0, newtons_per_mm()),
                    &Qty::new(6.0, newtons_per_mm()),
                )
                .unwrap(),
            )),
        }];
        assert_eq!(check_refinement(&base, &wider).len(), 1);
    }

    #[test]
    fn capability_vs_demand_flags_unmet_demand() {
        let demands = vec!["sink_current".to_string(), "source_current".to_string()];
        let supplied = vec![
            Capability {
                demand: "sink_current".to_string(),
                meets: true,
            },
            Capability {
                demand: "source_current".to_string(),
                meets: false,
            },
        ];
        let diags = check_capability_vs_demand(&demands, &supplied);
        assert_eq!(diags.len(), 1);
        assert_eq!(diags[0].code, codes::CAPABILITY_VS_DEMAND);
        assert!(diags[0].message.contains("source_current"));
    }

    #[test]
    fn capability_vs_demand_empty_ledger_is_clean() {
        assert!(check_capability_vs_demand(&[], &[]).is_empty());
    }

    #[test]
    fn role_kind_requires_full_coverage_no_duplicates_no_unknowns() {
        let iface = Interface {
            name: "seat".to_string(),
            roles: vec!["bore".to_string(), "face".to_string()],
            demands: Vec::new(),
            promises: Vec::new(),
            spec_island: None,
        };

        // Well-formed: exactly one binding per declared role.
        let complete = Impl {
            interface: "seat".to_string(),
            role_bindings: vec![
                ("bore".to_string(), query("shell.faces")),
                ("face".to_string(), query("shell.faces")),
            ],
            refinements: Vec::new(),
        };
        assert!(check_role_kind(&iface, &complete).is_empty());

        // Missing a declared role.
        let missing = Impl {
            interface: "seat".to_string(),
            role_bindings: vec![("bore".to_string(), query("shell.faces"))],
            refinements: Vec::new(),
        };
        assert_eq!(check_role_kind(&iface, &missing).len(), 1);

        // Unknown role bound.
        let unknown = Impl {
            interface: "seat".to_string(),
            role_bindings: vec![
                ("bore".to_string(), query("shell.faces")),
                ("face".to_string(), query("shell.faces")),
                ("nonesuch".to_string(), query("shell.faces")),
            ],
            refinements: Vec::new(),
        };
        assert_eq!(check_role_kind(&iface, &unknown).len(), 1);

        // Duplicate binding of the same role.
        let duplicate = Impl {
            interface: "seat".to_string(),
            role_bindings: vec![
                ("bore".to_string(), query("shell.faces")),
                ("bore".to_string(), query("shell.faces")),
                ("face".to_string(), query("shell.faces")),
            ],
            refinements: Vec::new(),
        };
        assert_eq!(check_role_kind(&iface, &duplicate).len(), 1);
    }

    #[test]
    fn param_match_has_nothing_to_compare_yet() {
        let iface = Interface {
            name: "seat".to_string(),
            roles: Vec::new(),
            demands: Vec::new(),
            promises: Vec::new(),
            spec_island: None,
        };
        let imp = Impl {
            interface: "seat".to_string(),
            role_bindings: Vec::new(),
            refinements: Vec::new(),
        };
        assert!(check_param_match(&iface, &imp).is_empty());
    }
}
