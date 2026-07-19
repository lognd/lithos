//! `SolverResponse`: the wire response an out-of-process solver returns
//! over the WO-20 subprocess adapter (AD-19).
//!
//! Design reference: `docs/spec/toolchain/20-solver-abstraction.md`
//! sec. D-C/3. A non-Python solver receives a serialized
//! `DischargeRequest` on stdin and answers with ONE `SolverResponse`
//! JSON document on stdout; stderr is logs. Exit code 0 covers every
//! COMPUTED outcome, including a violated claim -- the response is a
//! worst-corner prediction the shared margin rule decides, never a
//! verdict the solver decides for itself. Floats travel as exact `u64`
//! bit patterns (the `Evidence` convention) so text formatting can
//! never move a hash (INV-10).

use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

use crate::evidence::Coverage;

/// The schema-versioned JSON document a subprocess solver writes to
/// stdout: its worst-corner prediction, plus the identity/determinism
/// metadata the evidence hash folds (AD-19: `solver_version` is always
/// folded; non-deterministic solvers also fold `settings_digest`).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#solver
pub struct SolverResponse {
    /// The `SCHEMA_VERSION` the solver spoke; a mismatch with ours is
    /// the adapter's `SchemaVersionMismatch` failure arm (AD-5).
    pub schema_version: u32,
    /// The predicted worst-corner value's `f64` bits.
    pub value_bits: u64,
    /// The solver's declared worst-case error `eps`'s `f64` bits.
    pub eps_bits: u64,
    /// Structured coverage achieved (D95, sec. 8.2).
    pub coverage: Coverage,
    /// The solver binary's own version id (always folded into the
    /// evidence hash, AD-19).
    pub solver_version: String,
    /// Settings/seed digest for non-deterministic solvers (INV-10);
    /// absent for a fully deterministic solve.
    pub settings_digest: Option<String>,
    /// True iff the request fell inside the solver's validity domain;
    /// false maps to an honest `indeterminate`, never a silent pass.
    pub domain_ok: bool,
    /// Optional human-readable note carried into logs (never hashed).
    pub note: Option<String>,
}

#[cfg(test)]
mod tests {
    use super::SolverResponse;
    use crate::evidence::Coverage;

    #[test]
    fn solver_response_round_trips_through_json() {
        // JSON is THE wire format (D-C): a response must survive a
        // serialize/deserialize round trip bit-exactly.
        let response = SolverResponse {
            schema_version: crate::SCHEMA_VERSION,
            value_bits: 94.2_f64.to_bits(),
            eps_bits: 3.1_f64.to_bits(),
            coverage: Coverage::full(),
            solver_version: "fixture-solver@1.0.0".to_string(),
            settings_digest: Some("blake3:ab".to_string()),
            domain_ok: true,
            note: Some("thin_wall ok".to_string()),
        };
        let json = serde_json::to_string(&response).unwrap();
        let back: SolverResponse = serde_json::from_str(&json).unwrap();
        assert_eq!(back, response);
    }

    #[test]
    fn optional_fields_deserialize_from_null() {
        // `settings_digest`/`note` are `str | null` on the wire
        // (design doc sec. 3): a deterministic solver sends null.
        let json = r#"{"schema_version":4,"value_bits":0,"eps_bits":0,
            "coverage":{"axes":[],"fraction_bits":0},"solver_version":"s@1",
            "settings_digest":null,"domain_ok":false,"note":null}"#;
        let back: SolverResponse = serde_json::from_str(json).unwrap();
        assert_eq!(back.settings_digest, None);
        assert_eq!(back.note, None);
        assert!(!back.domain_ok);
    }
}
