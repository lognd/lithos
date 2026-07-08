//! The claim AST: what `require <Group>:` bodies say. Claims lower to
//! obligations (`obligation.rs`); evidence is the only return type.
//!
//! Regolith reference: `docs/regolith/07-claims-and-evidence.md` and
//! `docs/regolith/02` sec. 5 (time/frequency forms). Time and frequency
//! claims (`peak`, `settles`, `rms(band=)`, `stays_within(mask)`) are
//! one family with different harness models; windows (`during`,
//! `within .. after`, `until`) build on events.

use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

/// A time/event window a claim is evaluated over.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum Window {
    /// `during <event-or-config-domain>`.
    During(String),
    /// `within <duration> after <event>`.
    WithinAfter {
        /// The bounding duration (source text; typed in qty).
        duration: String,
        /// The anchoring event.
        event: String,
    },
    /// `until <event>`.
    Until(String),
}

/// The claim form -- the shape of the assertion.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(tag = "form", rename_all = "snake_case")]
pub enum ClaimForm {
    /// A scalar comparison (`stress < limit`, `k within [lo, hi]`).
    Comparison {
        /// The quantity expression (kept as text; parsed in WO-05).
        lhs: String,
        /// The comparator/containment (`<`, `within`, ...).
        op: String,
        /// The bound expression.
        rhs: String,
    },
    /// `peak(x, during w) <op> <rhs>` (D102: a REDUCTION form that
    /// yields a scalar and requires an external comparator).
    Peak {
        /// The signal expression.
        signal: String,
        /// The evaluation window.
        window: Window,
        /// The external comparator (`<`, `<=`, ...).
        op: String,
        /// The bound expression.
        rhs: String,
    },
    /// `settles(x, to=tol, within d after e)`. A CONTAINMENT form
    /// (D102): self-contained, no external comparator (its `tol` IS
    /// the acceptance).
    Settles {
        /// The signal expression.
        signal: String,
        /// Settling tolerance text.
        tol: String,
        /// The bounding window.
        window: Window,
    },
    /// `overshoot(x, after e) <op> <rhs>` (D102: a REDUCTION form).
    Overshoot {
        /// The signal expression.
        signal: String,
        /// The anchoring event.
        event: String,
        /// The external comparator (`<`, `<=`, ...).
        op: String,
        /// The bound expression.
        rhs: String,
    },
    /// `rms(x, band=[f1, f2]) <op> <rhs>` (D102: a REDUCTION form).
    Rms {
        /// The signal expression.
        signal: String,
        /// The frequency band, as text.
        band: String,
        /// The external comparator (`<`, `<=`, ...).
        op: String,
        /// The bound expression.
        rhs: String,
    },
    /// `stays_within(x, mask)`.
    StaysWithin {
        /// The signal expression.
        signal: String,
        /// The hash-pinned mask reference.
        mask: String,
    },
    /// `compute <name>: <quantity kind> over <index domain>` (WO-33
    /// D98): produces a named indexed field instead of asserting a
    /// bound. Lowers to ONE obligation whose successful evidence
    /// carries a `field` payload; the produced name enters the datum
    /// ledger ([`crate::field::FieldDatum`]).
    Compute {
        /// The dotted quantity-kind path (e.g. `thermo.wall_temperature`).
        quantity_kind: String,
        /// The index domain text after `over` (e.g. `liner.zones` or
        /// `travel in [-80mm, 120mm]`), kept as text like every other
        /// predicate-side expression in this AST (parsed structurally
        /// by the harness half, not the core).
        over: String,
    },
}

/// A single named claim inside a `require` group.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
pub struct Claim {
    /// Optional claim name.
    pub name: Option<String>,
    /// The claim form.
    pub form: ClaimForm,
    /// `forall <cfg>` config axes the claim quantifies over.
    pub forall: Vec<String>,
    /// Safety factor (`sf=`), if any.
    pub sf: Option<f64>,
    /// Scatter factor (`scatter_factor=`), if any.
    pub scatter_factor: Option<f64>,
    /// Minimum required evidence trust tier (`trust: >= tier`).
    pub trust_floor: Option<String>,
    /// Discharge-model hints (`@hint`).
    pub hints: Vec<String>,
    /// A `model=` pin selecting the discharge model.
    pub model_pin: Option<String>,
}

/// An `assume!(expr, basis=)` assumption: an un-discharged claim that
/// `--release` refuses (recorded in the todo/assume/waive ledger).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
pub struct Assumption {
    /// The assumed expression, as text.
    pub expr: String,
    /// The stated basis for the assumption.
    pub basis: String,
}

#[cfg(test)]
mod tests {
    use super::{Claim, ClaimForm, Window};

    #[test]
    fn claim_round_trips_json() {
        let c = Claim {
            name: Some("droop".to_string()),
            form: ClaimForm::Peak {
                signal: "v(out)".to_string(),
                window: Window::During("load_step".to_string()),
                op: "<".to_string(),
                rhs: "3.3V".to_string(),
            },
            forall: vec!["corner".to_string()],
            sf: Some(1.5),
            scatter_factor: None,
            trust_floor: Some("measured".to_string()),
            hints: vec![],
            model_pin: None,
        };
        let json = serde_json::to_string(&c).unwrap();
        let back: Claim = serde_json::from_str(&json).unwrap();
        assert_eq!(back, c);
    }
}
