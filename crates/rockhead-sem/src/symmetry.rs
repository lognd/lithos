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

/// Greatest common divisor (used to intersect two cyclic orders: the
/// common subgroup of `Cyclic(a)` and `Cyclic(b)` is `Cyclic(gcd(a, b))`).
#[must_use]
fn gcd(a: u32, b: u32) -> u32 {
    if b == 0 {
        a
    } else {
        gcd(b, a % b)
    }
}

impl SymmetryGroup {
    /// The conservative intersection of two groups on commit: the
    /// largest group both admit. Anything uncertain collapses toward
    /// [`SymmetryGroup::Trivial`] (soundness, INV-4): a false symmetry
    /// must never be asserted, so any pair whose common subgroup is not
    /// soundly representable in this enum collapses to `Trivial`.
    #[must_use]
    pub fn intersect(&self, other: &SymmetryGroup) -> SymmetryGroup {
        use SymmetryGroup::{Continuous, Cyclic, Permutation, Trivial};

        match (self, other) {
            (Continuous, Continuous) => Continuous,
            (Continuous, Cyclic(n)) | (Cyclic(n), Continuous) => {
                if *n >= 2 {
                    Cyclic(*n)
                } else {
                    Trivial
                }
            }
            (Cyclic(a), Cyclic(b)) => {
                let g = gcd(*a, *b);
                if g >= 2 {
                    Cyclic(g)
                } else {
                    Trivial
                }
            }
            (Permutation(a), Permutation(b)) if a == b => Permutation(*a),
            // Different structural kinds (or mismatched permutation
            // orbits): no sound common representation -- collapse.
            _ => Trivial,
        }
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
    ///
    /// `orbit` itself is opaque here (per-entity orbit membership is
    /// tracked on [`crate::entity::Entity::orbit`], and it is the
    /// caller's job to confirm every candidate names the same
    /// `OrbitId`); this table only answers whether the *artifact* still
    /// has a declared, non-trivial group to license the extension.
    /// Under [`SymmetryGroup::Trivial`] (no declared symmetry, or
    /// collapsed by [`SymmetryGroup::intersect`]) every orbit is a
    /// singleton and `.any` is never legal across more than one
    /// candidate -- the sound default (INV-4) is to refuse.
    #[must_use]
    pub fn any_is_legal(&self, _orbit: OrbitId) -> bool {
        !matches!(self.group, None | Some(SymmetryGroup::Trivial))
    }

    /// Apply a symmetry-breaking contribution, splitting the affected
    /// orbit and returning the new table.
    ///
    /// This table's current shape tracks one artifact-level group (no
    /// per-orbit membership sets to split independently), so a break
    /// conservatively collapses the whole group to `Trivial` -- sound
    /// per INV-4 (never assert a symmetry that no longer holds) and
    /// consistent with the WO-07 acceptance scenario (a single pattern
    /// orbit that a later off-pattern feature splits). Finer per-orbit
    /// splitting (keeping unrelated orbits intact) needs a richer
    /// membership table and is out of this WO's scope.
    #[must_use]
    pub fn split_on_break(&self, _broken: OrbitId) -> OrbitTable {
        OrbitTable {
            group: Some(SymmetryGroup::Trivial),
        }
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
