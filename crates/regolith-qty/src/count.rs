//! Counts: `n x thing`, a discrete quantity of identical members.
//!
//! Regolith reference: `docs/regolith/02-quantity-core.md` sec. 3.
//! A count models as a dimensionless integer quantity carrying a
//! member-kind tag; the members form an orbit of entities
//! (`battery(2 x AA_alkaline)`, `pwm x 4`). Discrete, so exact equality
//! IS legal here (the `==` ban is on continuous quantities only).

use serde::{Deserialize, Serialize};

/// A count constructor value: `count` identical members of `member_kind`.
///
/// `Eq` is intentional and permitted -- counts are discrete integers,
/// exempt from the continuous-quantity equality ban.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Count {
    /// The number of members (`n` in `n x thing`).
    pub count: u64,
    /// The kind name of each identical member (`AA_alkaline`, `pwm`).
    pub member_kind: String,
}

impl Count {
    /// Build a count of `count` members of `member_kind`.
    #[must_use]
    pub fn new(count: u64, member_kind: impl Into<String>) -> Count {
        Count {
            count,
            member_kind: member_kind.into(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::Count;

    #[test]
    fn count_is_discrete_and_eq() {
        let a = Count::new(2, "AA_alkaline");
        let b = Count::new(2, "AA_alkaline");
        assert_eq!(a, b);
        assert_ne!(a, Count::new(4, "pwm"));
    }

    #[test]
    fn count_round_trips_json() {
        let c = Count::new(4, "pwm");
        let json = serde_json::to_string(&c).unwrap();
        let back: Count = serde_json::from_str(&json).unwrap();
        assert_eq!(back, c);
    }
}
