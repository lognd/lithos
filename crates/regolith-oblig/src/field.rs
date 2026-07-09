//! `FieldDatum`: the datum-ledger entry a `compute` claim produces
//! (WO-33 D98).
//!
//! Regolith reference: `docs/spec/regolith/02` sec. 4 (zones) + sec. 5
//! (events/datums, the borrow-exempt-ledger precedent this reuses
//! verbatim); `docs/spec/regolith/07` sec. 2 (obligations). A `compute`
//! claim lowers to ONE obligation whose successful evidence carries a
//! `field` payload (the WO-30 `PayloadRef` channel, `kind:
//! "field"`); this type is the ledger entry that names the datum,
//! states its index axis, and (once discharged) points at that
//! payload. `payload: None` is the honest pre-discharge state -- with
//! no field-producing model registered (WO-33 non-goal), it never
//! resolves in this repo's built-in harness, and consumers
//! referencing it stay `Indeterminate` (the chain rule of the
//! ledger).

use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

use crate::evidence::CoverageAxis;
use crate::payload::PayloadRef;

/// One computed indexed field's ledger entry: a named quantity over
/// one index axis (a zone set or a config interval), plus its
/// discharge payload once resolved.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
pub struct FieldDatum {
    /// The field's name (the `compute <name>: ...` binding).
    pub name: String,
    /// The dotted quantity-kind path (e.g. `thermo.wall_temperature`).
    pub quantity_kind: String,
    /// The field's index axis: the domain declared by the `over`
    /// clause, plus the method it was resolved with (`Undischarged`
    /// pre-evidence -- see [`crate::evidence::CoverageMethod::Undischarged`]).
    pub axis: CoverageAxis,
    /// The discharged field payload (`kind: "field"`), or `None`
    /// before any model has produced one.
    pub payload: Option<PayloadRef>,
}

#[cfg(test)]
mod tests {
    use super::FieldDatum;
    use crate::evidence::{CoverageAxis, CoverageDomain, CoverageMethod};

    #[test]
    fn field_datum_round_trips_json_with_null_payload() {
        let datum = FieldDatum {
            name: "wall_T".to_string(),
            quantity_kind: "thermo.wall_temperature".to_string(),
            axis: CoverageAxis {
                axis: "liner.zones".to_string(),
                domain: CoverageDomain::Values {
                    values: vec!["tip".to_string(), "throat".to_string()],
                },
                method: CoverageMethod::Undischarged,
            },
            payload: None,
        };
        let json = serde_json::to_string(&datum).unwrap();
        assert!(json.contains("\"payload\":null"));
        let back: FieldDatum = serde_json::from_str(&json).unwrap();
        assert_eq!(back, datum);
    }
}
