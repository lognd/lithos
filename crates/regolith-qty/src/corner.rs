//! Corner machinery: enumerate the endpoint assignments of a set of
//! named interval inputs, and select the worst one for a check.
//!
//! Regolith reference: `docs/spec/regolith/07` sec. 5 (corner discipline).
//! Which corner is worst is the *model's* decision, per-check, never a
//! global policy (WO-03 goal: expose the mechanism, not a policy). This
//! module yields the corners and takes the model's direction/evaluator;
//! it does not decide worseness itself.

use regolith_util::IndexMap;

use crate::interval::Interval;

/// One corner: each named input pinned to a chosen endpoint magnitude
/// (in that input's own unit). Insertion order = declaration order for
/// determinism (AD-6).
#[derive(Debug, Clone)]
// frob:doc docs/modules/regolith-qty.md#corner
pub struct Corner {
    /// Chosen endpoint magnitude per input name.
    pub assignment: IndexMap<String, f64>,
}

/// The direction a given check cares about at its worst corner. Passed
/// in BY the model; this crate never assumes one.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
// frob:doc docs/modules/regolith-qty.md#corner
pub enum CheckDirection {
    /// The check is worst when the evaluated quantity is smallest.
    Lower,
    /// The check is worst when the evaluated quantity is largest.
    Upper,
}

/// A named set of interval inputs whose corners a check ranges over.
#[derive(Debug, Default)]
// frob:doc docs/modules/regolith-qty.md#corner
pub struct CornerInputs {
    inputs: IndexMap<String, Interval>,
}

impl CornerInputs {
    /// An empty input set.
    #[must_use]
    // frob:doc docs/modules/regolith-qty.md#corner
    pub fn new() -> CornerInputs {
        CornerInputs {
            inputs: IndexMap::new(),
        }
    }

    /// Register a named interval input (declaration order preserved).
    // frob:doc docs/modules/regolith-qty.md#corner
    // frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
    pub fn insert(&mut self, name: impl Into<String>, interval: Interval) {
        self.inputs.insert(name.into(), interval);
    }

    /// Number of interval inputs (the corner space is `2^n`).
    #[must_use]
    // frob:doc docs/modules/regolith-qty.md#corner
    // frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
    pub fn len(&self) -> usize {
        self.inputs.len()
    }

    /// True when there are no inputs.
    #[must_use]
    // frob:doc docs/modules/regolith-qty.md#corner
    pub fn is_empty(&self) -> bool {
        self.inputs.is_empty()
    }

    /// Enumerate all `2^n` endpoint-assignment corners in a
    /// deterministic order (AD-6).
    #[must_use]
    // frob:doc docs/modules/regolith-qty.md#corner
    pub fn corners(&self) -> Vec<Corner> {
        let mut result = vec![Corner {
            assignment: IndexMap::new(),
        }];
        for (name, interval) in &self.inputs {
            let mut next = Vec::with_capacity(result.len() * 2);
            for corner in &result {
                for endpoint in [interval.lo().magnitude(), interval.hi().magnitude()] {
                    let mut assignment = corner.assignment.clone();
                    assignment.insert(name.clone(), endpoint);
                    next.push(Corner { assignment });
                }
            }
            result = next;
        }
        result
    }

    /// Select the worst corner for a check, given the check's direction
    /// and an evaluator mapping a corner to a scalar magnitude. Worseness
    /// is the model's call; this only maximizes/minimizes the evaluator.
    #[must_use]
    // frob:doc docs/modules/regolith-qty.md#corner
    // frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
    pub fn worst_case(
        &self,
        direction: CheckDirection,
        evaluate: &dyn Fn(&Corner) -> f64,
    ) -> Option<Corner> {
        let corners = self.corners();
        corners
            .into_iter()
            .fold(None, |best, corner| {
                let value = evaluate(&corner);
                match &best {
                    None => Some((value, corner)),
                    Some((best_value, _)) => {
                        let replace = match direction {
                            CheckDirection::Lower => value < *best_value,
                            CheckDirection::Upper => value > *best_value,
                        };
                        if replace {
                            Some((value, corner))
                        } else {
                            best
                        }
                    }
                }
            })
            .map(|(_, corner)| corner)
    }
}

#[cfg(test)]
mod tests {
    use super::{CheckDirection, CornerInputs};
    use crate::interval::Interval;
    use crate::quantity::Qty;
    use crate::unit::Unit;

    // frob:tests crates/regolith-qty/src/corner.rs::CornerInputs.len kind="unit"
    #[test]
    fn empty_inputs_report_empty() {
        let inputs = CornerInputs::new();
        assert!(inputs.is_empty());
        assert_eq!(inputs.len(), 0);
    }

    // frob:tests crates/regolith-qty/src/corner.rs::CornerInputs.insert kind="unit"
    // frob:tests crates/regolith-qty/src/corner.rs::CornerInputs.worst_case kind="unit"
    #[test]
    fn worst_case_selects_the_maximizing_corner_for_upper_direction() {
        let dimensionless = Unit::dimensionless();
        let lo = Qty::new(10.0, dimensionless.clone());
        let hi = Qty::new(20.0, dimensionless);
        let mut inputs = CornerInputs::new();
        inputs.insert("load", Interval::new(&lo, &hi).expect("lo <= hi"));
        assert_eq!(inputs.len(), 1);

        let worst = inputs
            .worst_case(CheckDirection::Upper, &|corner| corner.assignment["load"])
            .expect("one input must yield exactly one worst corner");
        assert!((worst.assignment["load"] - 20.0).abs() < f64::EPSILON);

        let worst_lower = inputs
            .worst_case(CheckDirection::Lower, &|corner| corner.assignment["load"])
            .expect("one input must yield exactly one worst corner");
        assert!((worst_lower.assignment["load"] - 10.0).abs() < f64::EPSILON);
    }
}
