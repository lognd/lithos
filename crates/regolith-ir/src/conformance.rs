//! T1 conformance and refinement checking: role-kind by construction,
//! parameter match, capability-vs-demand, and the promise-refinement
//! direction rule.
//!
//! Regolith reference: `docs/regolith/04-contracts.md`. Refinement is
//! directional: a refined interface makes TIGHTER demands on itself and
//! STRONGER promises to consumers, so an impl may only NARROW a promise.
//! Widening a promise is rejected (WO-12 acceptance). Capability tables
//! are WO-16 data; a static in-memory pack backs the tests.

use regolith_diag::{codes, Diagnostic};
use regolith_util::IndexMap;

use crate::nodes::{Impl, Interface, PromiseSlot};

/// Check that an impl's role bindings cover the interface's roles AND
/// that each binding's entity KIND is compatible with the role's required
/// kind (real role-kind matching, WO-12).
///
/// Two failure families (both `E0410` CAPABILITY_VS_DEMAND):
/// 1. Coverage/shape: every declared role has exactly one binding, and no
///    binding names an undeclared role (a role bound zero or more than
///    once, or an unknown role, is rejected).
/// 2. Role-kind: when the interface declares a role's required kind
///    (`Interface::role_kinds`, e.g. `bore` -> `cylindrical`) AND the impl
///    carries the bound entity's kind (`Impl::bound_kinds`), a mismatch is
///    rejected. When either side is absent the pair is kind-agnostic and
///    passes (no false positive; the entity-DB wiring that fills
///    `bound_kinds` is a documented WO-12 dependency).
#[must_use]
pub fn check_role_kind(iface: &Interface, imp: &Impl) -> Vec<Diagnostic> {
    let span = tracing::debug_span!("check_role_kind", interface = %iface.name);
    let _enter = span.enter();
    let mut diags = Vec::new();

    // Source-order count of how many times each bound role name appears.
    let mut bound_counts: IndexMap<&str, usize> = IndexMap::new();
    for (role, _query) in &imp.role_bindings {
        *bound_counts.entry(role.as_str()).or_insert(0) += 1;
        if !iface.roles.iter().any(|r| r == role) {
            tracing::debug!(role, "binding names an undeclared role");
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

    // Role-kind compatibility: required kind vs bound kind, in the
    // interface's source order (AD-6 determinism).
    for (role, required) in &iface.role_kinds {
        let Some((_, bound)) = imp.bound_kinds.iter().find(|(r, _)| r == role) else {
            continue; // bound kind unknown -> kind-agnostic, no verdict
        };
        if bound != required {
            tracing::debug!(role, %required, %bound, "role-kind mismatch");
            diags.push(Diagnostic::error(
                codes::CAPABILITY_VS_DEMAND,
                format!(
                    "impl of `{}` binds role `{role}` to a `{bound}`, but the interface \
                     requires a `{required}`",
                    iface.name
                ),
            ));
        }
    }

    diags
}

/// Check that an impl's parameters match the interface's (real parameter
/// type/shape matching, WO-12).
///
/// Walks the interface's parameters in source order (AD-6). For each,
/// the impl's parameter of the same name must:
/// - agree on `ParamKind` (a `<params>` type parameter and a `params:`
///   field are different sorts and cannot substitute), and
/// - agree on declared type/shape when BOTH sides declare one. An impl
///   pinning a free (untyped) interface parameter is allowed (the binding
///   MAY pin a free variable, regolith/04 sec. 1); an impl leaving a
///   parameter absent is not this check's failure (coverage is role-kind's
///   job) unless the type conflicts.
///
/// A mismatch is `E0410` (CAPABILITY_VS_DEMAND).
#[must_use]
pub fn check_param_match(iface: &Interface, imp: &Impl) -> Vec<Diagnostic> {
    let span = tracing::debug_span!("check_param_match", interface = %iface.name);
    let _enter = span.enter();
    let mut diags = Vec::new();

    for want in &iface.params {
        let Some(got) = imp.params.iter().find(|p| p.name == want.name) else {
            continue; // impl does not pin this parameter -> nothing to conflict
        };
        if got.kind != want.kind {
            tracing::debug!(param = %want.name, "param kind mismatch");
            diags.push(Diagnostic::error(
                codes::CAPABILITY_VS_DEMAND,
                format!(
                    "impl of `{}` binds parameter `{}` as a {:?} parameter, but the interface \
                     declares it a {:?} parameter",
                    iface.name, want.name, got.kind, want.kind
                ),
            ));
            continue;
        }
        if let Some(reason) = param_type_conflict(want, got) {
            tracing::debug!(param = %want.name, reason, "param type mismatch");
            diags.push(Diagnostic::error(
                codes::CAPABILITY_VS_DEMAND,
                format!(
                    "impl of `{}` binds parameter `{}`: {reason}",
                    iface.name, want.name
                ),
            ));
        }
    }

    diags
}

/// `Some(reason)` when an impl parameter's declared type conflicts with
/// the interface's; `None` when they agree or the interface's parameter is
/// free (untyped), which the impl may legally pin to any type.
fn param_type_conflict(want: &crate::nodes::Param, got: &crate::nodes::Param) -> Option<String> {
    match (&want.ty, &got.ty) {
        (Some(w), Some(g)) if w != g => Some(format!("expected type `{w}`, found `{g}`")),
        _ => None,
    }
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
    base: &regolith_qty::ValueSource,
    refined: &regolith_qty::ValueSource,
) -> Option<String> {
    use regolith_qty::{Comparator, Literal, ValueSource};

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
fn same_unit(a: &regolith_qty::Qty, b: &regolith_qty::Qty) -> bool {
    a.unit().symbol == b.unit().symbol
}

/// True when two intervals share a unit symbol.
fn same_interval_unit(a: &regolith_qty::Interval, b: &regolith_qty::Interval) -> bool {
    a.unit().symbol == b.unit().symbol
}

#[cfg(test)]
mod tests {
    use super::{
        check_capability_vs_demand, check_param_match, check_refinement, check_role_kind,
        Capability,
    };
    use crate::nodes::{Impl, Interface, Param, ParamKind, PromiseSlot};
    use num_rational::Ratio;
    use regolith_diag::codes;
    use regolith_qty::{
        BaseDimension, Comparator, Dimension, Interval, Literal, Qty, Unit, ValueSource,
    };
    use regolith_sem::Query;

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
            role_kinds: Vec::new(),
            demands: Vec::new(),
            promises: Vec::new(),
            params: Vec::new(),
            spec_island: None,
        };

        // Well-formed: exactly one binding per declared role.
        let complete = Impl {
            interface: "seat".to_string(),
            role_bindings: vec![
                ("bore".to_string(), query("shell.faces")),
                ("face".to_string(), query("shell.faces")),
            ],
            bound_kinds: Vec::new(),
            params: Vec::new(),
            refinements: Vec::new(),
        };
        assert!(check_role_kind(&iface, &complete).is_empty());

        // Missing a declared role.
        let missing = Impl {
            interface: "seat".to_string(),
            role_bindings: vec![("bore".to_string(), query("shell.faces"))],
            bound_kinds: Vec::new(),
            params: Vec::new(),
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
            bound_kinds: Vec::new(),
            params: Vec::new(),
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
            bound_kinds: Vec::new(),
            params: Vec::new(),
            refinements: Vec::new(),
        };
        assert_eq!(check_role_kind(&iface, &duplicate).len(), 1);
    }

    fn seat_iface() -> Interface {
        Interface {
            name: "seat".to_string(),
            roles: vec!["bore".to_string()],
            role_kinds: vec![("bore".to_string(), "cylindrical".to_string())],
            demands: Vec::new(),
            promises: Vec::new(),
            params: vec![Param {
                name: "d".to_string(),
                kind: ParamKind::Type,
                ty: Some("length".to_string()),
            }],
            spec_island: None,
        }
    }

    /// A matching impl -- role bound to the required kind, parameter of the
    /// declared type -- passes both role-kind and param checks (WO-12).
    #[test]
    fn matching_impl_passes_role_kind_and_params() {
        let iface = seat_iface();
        let imp = Impl {
            interface: "seat".to_string(),
            role_bindings: vec![("bore".to_string(), query("shell.bore"))],
            bound_kinds: vec![("bore".to_string(), "cylindrical".to_string())],
            params: vec![Param {
                name: "d".to_string(),
                kind: ParamKind::Type,
                ty: Some("length".to_string()),
            }],
            refinements: Vec::new(),
        };
        assert!(check_role_kind(&iface, &imp).is_empty());
        assert!(check_param_match(&iface, &imp).is_empty());
    }

    /// A role-kind mismatch (binding a `planar` where `cylindrical` is
    /// required) fails role-kind matching (WO-12 acceptance).
    #[test]
    fn role_kind_mismatch_fails() {
        let iface = seat_iface();
        let imp = Impl {
            interface: "seat".to_string(),
            role_bindings: vec![("bore".to_string(), query("shell.face"))],
            bound_kinds: vec![("bore".to_string(), "planar".to_string())],
            params: Vec::new(),
            refinements: Vec::new(),
        };
        let diags = check_role_kind(&iface, &imp);
        assert_eq!(diags.len(), 1);
        assert_eq!(diags[0].code, codes::CAPABILITY_VS_DEMAND);
        assert!(diags[0].message.contains("cylindrical"));
        assert!(diags[0].message.contains("planar"));
    }

    /// A parameter type mismatch (impl pins `d` as an `angle` where the
    /// interface declares `length`) fails param matching (WO-12 acceptance).
    #[test]
    fn param_type_mismatch_fails() {
        let iface = seat_iface();
        let imp = Impl {
            interface: "seat".to_string(),
            role_bindings: vec![("bore".to_string(), query("shell.bore"))],
            bound_kinds: vec![("bore".to_string(), "cylindrical".to_string())],
            params: vec![Param {
                name: "d".to_string(),
                kind: ParamKind::Type,
                ty: Some("angle".to_string()),
            }],
            refinements: Vec::new(),
        };
        assert!(check_role_kind(&iface, &imp).is_empty());
        let diags = check_param_match(&iface, &imp);
        assert_eq!(diags.len(), 1);
        assert_eq!(diags[0].code, codes::CAPABILITY_VS_DEMAND);
        assert!(diags[0].message.contains('d'));
    }

    /// An impl pinning a FREE (untyped) interface parameter is allowed
    /// (regolith/04: a binding may pin a free variable).
    #[test]
    fn pinning_a_free_interface_param_is_allowed() {
        let mut iface = seat_iface();
        iface.params[0].ty = None; // free parameter
        let imp = Impl {
            interface: "seat".to_string(),
            role_bindings: vec![("bore".to_string(), query("shell.bore"))],
            bound_kinds: vec![("bore".to_string(), "cylindrical".to_string())],
            params: vec![Param {
                name: "d".to_string(),
                kind: ParamKind::Type,
                ty: Some("20mm".to_string()),
            }],
            refinements: Vec::new(),
        };
        assert!(check_param_match(&iface, &imp).is_empty());
    }

    /// The CST extractors populate `role_kinds` and `params` from the
    /// typed interface declaration, and role bindings + `params:` from the
    /// typed `ImplStmt` (WO-12 "populate from the typed CST").
    #[test]
    fn extracts_interface_and_impl_from_cst() {
        use camino::Utf8PathBuf;
        use regolith_syntax::ast::{AstNode, File};
        use regolith_syntax::syntax_kind::SyntaxKind;

        let src = "interface SensorPad:\n\
                    \x20\x20\x20\x20roles:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20pad: planar\n\
                    \x20\x20\x20\x20demands:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20stiffness: bar\n\
                    \x20\x20\x20\x20params:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20size: length\n\
                    \npart P:\n\
                    \x20\x20\x20\x20impl SensorPad<d=20mm> for self:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20pad = milled.face\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20params:\n\
                    \x20\x20\x20\x20\x20\x20\x20\x20\x20\x20size: length\n";
        let parse = regolith_syntax::parser::parse(src, &Utf8PathBuf::from("t.hema"));
        let file = File::cast(parse.syntax()).expect("file");

        let iface_decl = file
            .decls()
            .into_iter()
            .find(|d| d.name().as_deref() == Some("SensorPad"))
            .expect("interface decl");
        let iface = Interface::from_decl(&iface_decl).expect("interface");
        assert_eq!(iface.roles, vec!["pad".to_string()]);
        assert_eq!(
            iface.role_kinds,
            vec![("pad".to_string(), "planar".to_string())]
        );
        assert_eq!(iface.demands, vec!["stiffness".to_string()]);
        // `params: size: length` -> a Field parameter.
        assert!(iface.params.iter().any(|p| p.name == "size"
            && p.kind == ParamKind::Field
            && p.ty.as_deref() == Some("length")));

        let impl_stmt = parse
            .syntax()
            .descendants()
            .find(|n| n.kind() == SyntaxKind::ImplStmt)
            .expect("impl stmt");
        let imp = Impl::from_impl_stmt(&impl_stmt).expect("impl");
        assert_eq!(imp.interface, "SensorPad");
        assert_eq!(imp.role_bindings.len(), 1);
        assert_eq!(imp.role_bindings[0].0, "pad");
        assert!(imp.params.iter().any(|p| p.name == "d"));
        assert!(imp
            .params
            .iter()
            .any(|p| p.name == "size" && p.kind == ParamKind::Field));
    }
}
