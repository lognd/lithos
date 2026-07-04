//! Symmetry groups and orbits: the machinery behind `x.any`.
//!
//! Substrate reference: `docs/substrate/05-ownership-and-queries.md`
//! sec. 5. The DB tracks the artifact's symmetry group, computed
//! CONSERVATIVELY from per-construct declared contributions (the
//! intersection). Sound-but-conservative: an undetected true symmetry
//! may cause a spurious `any` error; a false symmetry is never
//! asserted. Later constructs break symmetry, splitting orbits.

use serde::{Deserialize, Serialize};

/// An orbit identifier: a set of entities equivalent under the current
/// group (identical bus bits, pattern instances).
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
pub struct OrbitId(pub u32);

/// A symmetry group representation. Conservative: only the forms a
/// construct can soundly declare.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SymmetryGroup {
    /// The trivial group (no symmetry).
    Trivial,
    /// Cyclic order n (a circular pattern of n).
    Cyclic(u32),
    /// Continuous rotational symmetry (a body of revolution).
    Continuous,
    /// A permutation orbit of identical members (an n-bit bus).
    Permutation(u32),
}

impl SymmetryGroup {
    /// The conservative intersection of two groups on commit: the
    /// largest group both admit. Anything uncertain collapses toward
    /// [`SymmetryGroup::Trivial`] (soundness).
    #[must_use]
    pub fn intersect(&self, _other: &SymmetryGroup) -> SymmetryGroup {
        todo!("STUB WO-07: greatest common symmetry; collapse to Trivial when uncertain")
    }
}

/// The orbit bookkeeping over a snapshot: which entities share an orbit,
/// and the splitting a symmetry-breaking delta forces.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct OrbitTable {
    group: Option<SymmetryGroup>,
}

impl OrbitTable {
    /// An empty orbit table (trivial symmetry).
    #[must_use]
    pub fn new() -> OrbitTable {
        OrbitTable { group: None }
    }

    /// The current artifact-level group, if any has been declared.
    #[must_use]
    pub fn group(&self) -> Option<&SymmetryGroup> {
        self.group.as_ref()
    }

    /// Whether every candidate in `orbit` still shares one orbit of the
    /// current group -- the legality test for `.any` (WO-08 calls this).
    #[must_use]
    pub fn any_is_legal(&self, _orbit: OrbitId) -> bool {
        todo!("STUB WO-07: check candidates lie in one orbit of the current group")
    }

    /// Apply a symmetry-breaking contribution, splitting the affected
    /// orbit and returning the new table.
    #[must_use]
    pub fn split_on_break(&self, _broken: OrbitId) -> OrbitTable {
        todo!("STUB WO-07: split the orbit the breaking delta touches; keep the rest")
    }
}

#[cfg(test)]
mod tests {
    use super::{OrbitTable, SymmetryGroup};

    #[test]
    fn empty_table_has_no_group() {
        assert!(OrbitTable::new().group().is_none());
    }

    #[test]
    fn group_round_trips_json() {
        let g = SymmetryGroup::Cyclic(6);
        let json = serde_json::to_string(&g).unwrap();
        let back: SymmetryGroup = serde_json::from_str(&json).unwrap();
        assert_eq!(back, g);
    }
}
