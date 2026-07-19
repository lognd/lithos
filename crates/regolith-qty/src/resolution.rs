//! Resolution records: a resolved value plus the cause that decided it
//! -- the lockfile row shape.
//!
//! Regolith reference: `docs/spec/regolith/03-value-sources.md` sec. 2.
//! Every non-literal source resolves into the lockfile carrying WHY it
//! got its value; a number that changes in review names why it changed.
//! Resolutions are constructed only through a `Cause`-requiring API
//! (INV-21 as a type: a causeless resolved value is unrepresentable).

use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

use crate::quantity::Qty;

/// Why a value resolved to what it did. Mandatory on every resolution
/// (INV-21). The variants mirror the resolving mechanisms.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(tag = "cause", content = "ref", rename_all = "snake_case")]
// frob:doc docs/modules/regolith-qty.md#resolution
// frob:invariant INV-021
pub enum Cause {
    /// A DFM rule pinned it (`dfm(sheet.min_bend_radius)`).
    Dfm(String),
    /// A DRC rule pinned it (`drc(jlc_2l.current_capacity)`).
    Drc(String),
    /// An obligation determined it (`obligation(vdd_core.droop)`).
    Obligation(String),
    /// A budget allocation set it (`budget(mesh_alignment)`).
    Budget(String),
    /// A topology/structure boundary pinned it.
    Topology(String),
    /// A planner produced it.
    Planner(String),
    /// A foreign artifact linked via `extern(ref)` supplied it
    /// (regolith/08 lowering, `by extern`).
    Extern(String),
    /// A derived intent/workload analysis pinned it
    /// (`derived(intent <name>)`, regolith/09 sec. 1).
    DerivedIntent(String),
    /// A `policy:` block at system altitude decided it (regolith/03
    /// sec. 2, `allocated (policy)`).
    Policy(String),
}

impl Cause {
    /// The lockfile spelling of this cause's kind and its reference
    /// string (`dfm(sheet.min_bend_radius)` -> `("dfm",
    /// "sheet.min_bend_radius")`).
    #[must_use]
    fn kind_and_ref(&self) -> (&'static str, &str) {
        match self {
            Cause::Dfm(r) => ("dfm", r.as_str()),
            Cause::Drc(r) => ("drc", r.as_str()),
            Cause::Obligation(r) => ("obligation", r.as_str()),
            Cause::Budget(r) => ("budget", r.as_str()),
            Cause::Topology(r) => ("topology", r.as_str()),
            Cause::Planner(r) => ("planner", r.as_str()),
            Cause::Extern(r) => ("extern", r.as_str()),
            Cause::DerivedIntent(r) => ("derived_intent", r.as_str()),
            Cause::Policy(r) => ("policy", r.as_str()),
        }
    }
}

/// A resolved value with its cause: one lockfile row. There is no way
/// to build one without a `Cause` (INV-21).
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-qty.md#resolution
pub struct Resolution {
    value: Qty,
    cause: Cause,
}

impl Resolution {
    /// Build a resolution from a value and its resolving cause. The only
    /// constructor -- causeless resolutions are unrepresentable.
    #[must_use]
    // frob:doc docs/modules/regolith-qty.md#resolution
    pub fn new(value: Qty, cause: Cause) -> Resolution {
        Resolution { value, cause }
    }

    /// The resolved value.
    #[must_use]
    // frob:doc docs/modules/regolith-qty.md#resolution
    pub fn value(&self) -> &Qty {
        &self.value
    }

    /// The cause that decided the value.
    #[must_use]
    // frob:doc docs/modules/regolith-qty.md#resolution
    pub fn cause(&self) -> &Cause {
        &self.cause
    }

    /// Render the documented lockfile line for slot `slot`:
    /// `slot = <value>    cause: dfm(rule)`.
    #[must_use]
    // frob:doc docs/modules/regolith-qty.md#resolution
    // frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
    pub fn lockfile_line(&self, slot: &str) -> String {
        let mut buf = ryu::Buffer::new();
        let value = buf.format(self.value.magnitude());
        let (kind, reference) = self.cause.kind_and_ref();
        format!(
            "{slot} = {value}{unit}    cause: {kind}({reference})",
            unit = self.value.unit().symbol,
        )
    }
}

#[cfg(test)]
mod tests {
    use super::{Cause, Resolution};
    use crate::quantity::Qty;
    use crate::unit::Unit;

    #[test]
    fn resolution_round_trips_json() {
        let r = Resolution::new(
            Qty::new(2.4, Unit::dimensionless()),
            Cause::Dfm("sheet.min_bend_radius".to_string()),
        );
        let json = serde_json::to_string(&r).unwrap();
        let back: Resolution = serde_json::from_str(&json).unwrap();
        assert_eq!(
            back.cause(),
            &Cause::Dfm("sheet.min_bend_radius".to_string())
        );
    }

    #[test]
    fn cause_round_trips_json() {
        let c = Cause::Obligation("vdd_core.droop".to_string());
        let json = serde_json::to_string(&c).unwrap();
        let back: Cause = serde_json::from_str(&json).unwrap();
        assert_eq!(back, c);
    }

    #[test]
    fn all_eight_inv21_causes_render_and_round_trip() {
        // INV-21 enumerates dfm/drc, obligation, budget, topology,
        // planner, extern, derived-intent, policy -- all must be
        // representable (FE-2).
        let causes = [
            Cause::Dfm("r".into()),
            Cause::Drc("r".into()),
            Cause::Obligation("r".into()),
            Cause::Budget("r".into()),
            Cause::Topology("r".into()),
            Cause::Planner("r".into()),
            Cause::Extern("outline.dxf".into()),
            Cause::DerivedIntent("workload_x".into()),
            Cause::Policy("thermal_budget".into()),
        ];
        for c in causes {
            let back: Cause = serde_json::from_str(&serde_json::to_string(&c).unwrap()).unwrap();
            assert_eq!(back, c);
        }
    }

    // frob:tests crates/regolith-qty/src/resolution.rs::Resolution.lockfile_line kind="unit"
    #[test]
    fn lockfile_line_names_the_slot_value_and_cause() {
        let r = Resolution::new(
            Qty::new(2.4, Unit::dimensionless()),
            Cause::Dfm("sheet.min_bend_radius".to_string()),
        );
        let line = r.lockfile_line("bend_radius");
        assert!(line.starts_with("bend_radius = 2.4"));
        assert!(line.contains("cause: dfm(sheet.min_bend_radius)"));
    }
}
