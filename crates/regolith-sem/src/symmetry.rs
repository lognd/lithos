//! Symmetry groups and orbits: the machinery behind `x.any`.
//!
//! Regolith reference: `docs/spec/regolith/05-ownership-and-queries.md`
//! sec. 5. The DB tracks the artifact's symmetry group, computed
//! CONSERVATIVELY from per-construct declared contributions (the
//! intersection). Sound-but-conservative: an undetected true symmetry
//! may cause a spurious `any` error; a false symmetry is never
//! asserted. Later constructs break symmetry, splitting orbits.

use serde::{Deserialize, Serialize};

/// An orbit identifier: a set of entities equivalent under the current
/// group (identical bus bits, pattern instances).
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
// frob:doc docs/modules/regolith-sem.md#symmetry
pub struct OrbitId(pub u32);

/// A symmetry group representation. Conservative: only the forms a
/// construct can soundly declare.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
// frob:doc docs/modules/regolith-sem.md#symmetry
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
    // frob:doc docs/modules/regolith-sem.md#symmetry
    // frob:invariant INV-004
    // frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
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
// frob:doc docs/modules/regolith-sem.md#symmetry
pub struct OrbitTable {
    group: Option<SymmetryGroup>,
}

impl OrbitTable {
    /// An empty orbit table (trivial symmetry).
    #[must_use]
    // frob:doc docs/modules/regolith-sem.md#symmetry
    pub fn new() -> OrbitTable {
        OrbitTable { group: None }
    }

    /// The current artifact-level group, if any has been declared.
    #[must_use]
    // frob:doc docs/modules/regolith-sem.md#symmetry
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
    // frob:doc docs/modules/regolith-sem.md#symmetry
    // frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
    pub fn any_is_legal(&self, _orbit: OrbitId) -> bool {
        !matches!(self.group, None | Some(SymmetryGroup::Trivial))
    }

    /// Fold one construct's declared symmetry contribution into the
    /// artifact-level group (WO-07: the group is the CONSERVATIVE
    /// intersection of per-construct declared contributions). The first
    /// contribution seeds the group; each later one intersects via
    /// [`SymmetryGroup::intersect`], so the result is a sound
    /// under-approximation (INV-4): a mixed pair whose common subgroup is
    /// not soundly representable collapses toward
    /// [`SymmetryGroup::Trivial`], never asserting a false symmetry.
    ///
    /// This is the population half `regolith-lower` calls with the
    /// `PredictedDelta.symmetry` contributions parsed from `pattern`
    /// constructs; without it the table had no way to acquire a non-
    /// trivial group from source.
    // frob:doc docs/modules/regolith-sem.md#symmetry
    // frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
    pub fn contribute(&mut self, group: SymmetryGroup) {
        self.group = Some(match self.group.take() {
            None => group,
            Some(existing) => existing.intersect(&group),
        });
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
    // frob:doc docs/modules/regolith-sem.md#symmetry
    // frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
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

    // frob:tests crates/regolith-sem/src/symmetry.rs::SymmetryGroup.intersect kind="unit"
    // frob:tests crates/regolith-sem/src/symmetry.rs::OrbitTable.contribute kind="unit"
    // frob:tests crates/regolith-sem/src/symmetry.rs::OrbitTable.any_is_legal kind="unit"
    #[test]
    fn contribute_seeds_then_intersects_conservatively() {
        // First contribution seeds; a compatible second keeps the common
        // subgroup; an incompatible one collapses to Trivial (INV-4).
        let mut t = OrbitTable::new();
        t.contribute(SymmetryGroup::Cyclic(6));
        assert_eq!(t.group(), Some(&SymmetryGroup::Cyclic(6)));
        assert!(t.any_is_legal(super::OrbitId(0)));
        t.contribute(SymmetryGroup::Cyclic(4));
        assert_eq!(t.group(), Some(&SymmetryGroup::Cyclic(2)), "gcd(6,4)=2");
        t.contribute(SymmetryGroup::Permutation(3));
        assert_eq!(
            t.group(),
            Some(&SymmetryGroup::Trivial),
            "mixed kinds collapse"
        );
        assert!(!t.any_is_legal(super::OrbitId(0)));
    }

    #[test]
    fn group_round_trips_json() {
        let g = SymmetryGroup::Cyclic(6);
        let json = serde_json::to_string(&g).unwrap();
        let back: SymmetryGroup = serde_json::from_str(&json).unwrap();
        assert_eq!(back, g);
    }

    // frob:tests crates/regolith-sem/src/symmetry.rs::OrbitTable.split_on_break kind="unit"
    #[test]
    fn split_on_break_conservatively_collapses_the_whole_group() {
        let mut t = OrbitTable::new();
        t.contribute(SymmetryGroup::Cyclic(6));
        let broken = t.split_on_break(super::OrbitId(0));
        assert_eq!(broken.group(), Some(&SymmetryGroup::Trivial));
        assert!(!broken.any_is_legal(super::OrbitId(0)));
    }
}
