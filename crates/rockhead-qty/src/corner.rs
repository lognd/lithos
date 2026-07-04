//! Corner machinery: enumerate the endpoint assignments of a set of
//! named interval inputs, and select the worst one for a check.
//!
//! Substrate reference: `docs/substrate/07` sec. 5 (corner discipline).
//! Which corner is worst is the *model's* decision, per-check, never a
//! global policy (WO-03 goal: expose the mechanism, not a policy). This
//! module yields the corners and takes the model's direction/evaluator;
//! it does not decide worseness itself.

use rockhead_util::IndexMap;

use crate::interval::Interval;

/// One corner: each named input pinned to a chosen endpoint magnitude
/// (in that input's own unit). Insertion order = declaration order for
/// determinism (AD-6).
#[derive(Debug, Clone)]
pub struct Corner {
    /// Chosen endpoint magnitude per input name.
    pub assignment: IndexMap<String, f64>,
}

/// The direction a given check cares about at its worst corner. Passed
/// in BY the model; this crate never assumes one.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CheckDirection {
    /// The check is worst when the evaluated quantity is smallest.
    Lower,
    /// The check is worst when the evaluated quantity is largest.
    Upper,
}

/// A named set of interval inputs whose corners a check ranges over.
#[derive(Debug, Default)]
pub struct CornerInputs {
    inputs: IndexMap<String, Interval>,
}

impl CornerInputs {
    /// An empty input set.
    #[must_use]
    pub fn new() -> CornerInputs {
        CornerInputs {
            inputs: IndexMap::new(),
        }
    }

    /// Register a named interval input (declaration order preserved).
    pub fn insert(&mut self, name: impl Into<String>, interval: Interval) {
        self.inputs.insert(name.into(), interval);
    }

    /// Number of interval inputs (the corner space is `2^n`).
    #[must_use]
    pub fn len(&self) -> usize {
        self.inputs.len()
    }

    /// True when there are no inputs.
    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.inputs.is_empty()
    }

    /// Enumerate all `2^n` endpoint-assignment corners in a
    /// deterministic order (AD-6).
    #[must_use]
    pub fn corners(&self) -> Vec<Corner> {
        todo!("STUB WO-03: cartesian product of each input's lo/hi endpoints, source order")
    }

    /// Select the worst corner for a check, given the check's direction
    /// and an evaluator mapping a corner to a scalar magnitude. Worseness
    /// is the model's call; this only maximizes/minimizes the evaluator.
    #[must_use]
    pub fn worst_case(
        &self,
        _direction: CheckDirection,
        _evaluate: &dyn Fn(&Corner) -> f64,
    ) -> Option<Corner> {
        todo!("STUB WO-03: argmax/argmin of evaluate over corners() per direction")
    }
}

#[cfg(test)]
mod tests {
    use super::CornerInputs;

    #[test]
    fn empty_inputs_report_empty() {
        let inputs = CornerInputs::new();
        assert!(inputs.is_empty());
        assert_eq!(inputs.len(), 0);
    }
}
