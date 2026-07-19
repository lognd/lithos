//! The registry-records payload (WO-87, D198): loaded record fields
//! reaching the Rust rule engine through the EXISTING WO-42
//! realized-input channel as a `kind: "registry.records"` payload.
//!
//! Python's magnetite `RecordStore` is the ONE record loader (the
//! one-loader law, D198): it serializes the loaded record slice --
//! exactly the scalar fields rule predicates dereference, keyed by
//! record key -- and hands it in as an ordinary realized input. This
//! module DESERIALIZES that payload; it never reads TOML and never
//! does IO (AD-17 purity holds: the payload is an input to lowering
//! like any realized IR).
//!
//! The payload shape (JSON, content-hashed by the caller like every
//! realized input, so INV-22 pinning holds unchanged):
//!
//! ```json
//! { "records": { "<record key>": { "<field>": "<value text>", ... } } }
//! ```
//!
//! Field values are STRINGS (the same opaque-value-text discipline as
//! `Entity::measures`); the stdlib TOML convention embeds the unit in
//! the field NAME (`cl_pf`, `esr_ohm`, `pad_diameter_mm`), so
//! [`RegistryRecords::field`] resolves a bare predicate spelling
//! (`cl`) to its unit-suffixed row field (`cl_pf` -> `18pF`) through
//! the ONE suffix table below.

use regolith_util::IndexMap;

use crate::realized_input::RealizedInputs;

/// The realized-input `kind` string carrying registry records (D198).
/// The Python serializer and this reader both cite this constant --
/// nothing else spells it.
// frob:doc docs/modules/regolith-lower.md#registry
pub const REGISTRY_RECORDS_KIND: &str = "registry.records";

/// One record's scalar fields (field name -> value text).
// frob:doc docs/modules/regolith-lower.md#registry
pub type RecordFields = IndexMap<String, String>;

/// The unit-suffix spellings the stdlib record convention embeds in
/// field names (`cl_pf` = CL in picofarads), mapped to the unit symbol
/// the quantity grammar lexes. ONE table: `field` below and any future
/// suffix-aware reader cite it rather than re-deriving.
const UNIT_SUFFIXES: &[(&str, &str)] = &[
    ("pf", "pF"),
    ("nf", "nF"),
    ("uf", "uF"),
    ("mm", "mm"),
    ("ohm", "ohm"),
    ("mhz", "MHz"),
    ("khz", "kHz"),
    ("hz", "Hz"),
    ("ppm", "ppm"),
    ("v", "V"),
    ("ma", "mA"),
    ("a", "A"),
    ("w", "W"),
];

/// Every registry record supplied to this build, keyed by record key.
/// Empty when no `registry.records` payload was supplied -- dependent
/// rule terms then defer honestly (D-E), naming the missing fact.
// frob:doc docs/modules/regolith-lower.md#registry
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct RegistryRecords {
    records: IndexMap<String, RecordFields>,
}

/// The serde mirror of the payload JSON envelope.
#[derive(serde::Deserialize)]
struct PayloadEnvelope {
    records: IndexMap<String, IndexMap<String, serde_json::Value>>,
}

impl RegistryRecords {
    /// The no-records default (every lookup misses; rules defer).
    // frob:doc docs/modules/regolith-lower.md#registry
    #[must_use]
    pub fn empty() -> RegistryRecords {
        RegistryRecords::default()
    }

    /// Collect every `registry.records` payload out of the build's
    /// realized inputs (digest order -- `RealizedInputs` is a
    /// `BTreeMap`, so this is deterministic, AD-6). A malformed
    /// payload is logged and skipped, never invented around: the
    /// records it would have carried simply stay missing and the
    /// dependent rules defer (D-E) -- the same posture as an absent
    /// payload.
    // frob:doc docs/modules/regolith-lower.md#registry
    #[must_use]
    pub fn from_realized_inputs(inputs: &RealizedInputs) -> RegistryRecords {
        let mut records: IndexMap<String, RecordFields> = IndexMap::new();
        for (digest, input) in inputs {
            if input.kind != REGISTRY_RECORDS_KIND {
                continue;
            }
            let envelope: PayloadEnvelope = match serde_json::from_slice(&input.bytes) {
                Ok(env) => env,
                Err(e) => {
                    tracing::warn!(
                        digest = %digest,
                        error = %e,
                        "malformed registry.records payload skipped; its \
                         records stay missing and dependent rules defer"
                    );
                    continue;
                }
            };
            for (key, fields) in envelope.records {
                let flat: RecordFields = fields
                    .into_iter()
                    .map(|(name, value)| (name, json_value_text(&value)))
                    .collect();
                records.insert(key, flat);
            }
        }
        tracing::debug!(records = records.len(), "registry records payload loaded");
        RegistryRecords { records }
    }

    /// Build directly from (key, fields) pairs (test fixtures).
    // frob:doc docs/modules/regolith-lower.md#registry
    // frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
    #[must_use]
    pub fn from_pairs(pairs: &[(&str, &[(&str, &str)])]) -> RegistryRecords {
        let mut records = IndexMap::new();
        for (key, fields) in pairs {
            let flat: RecordFields = fields
                .iter()
                .map(|(n, v)| ((*n).to_string(), (*v).to_string()))
                .collect();
            records.insert((*key).to_string(), flat);
        }
        RegistryRecords { records }
    }

    /// True when no records were supplied.
    // frob:doc docs/modules/regolith-lower.md#registry
    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.records.is_empty()
    }

    /// A record's raw field map, by record key.
    // frob:doc docs/modules/regolith-lower.md#registry
    #[must_use]
    pub fn get(&self, key: &str) -> Option<&RecordFields> {
        self.records.get(key)
    }

    /// Resolve `field` on record `key` to its value TEXT, applying the
    /// unit-suffix convention: an exact field-name match wins; else a
    /// row field spelled `<field>_<suffix>` with a known unit suffix
    /// resolves to `<value><unit>` (`cl` -> `cl_pf = 18.0` -> `18pF`)
    /// so the value re-parses through the same quantity grammar rule
    /// predicates use. `None` when the record or field is absent --
    /// the caller's honest-deferral signal.
    // frob:doc docs/modules/regolith-lower.md#registry
    #[must_use]
    pub fn field(&self, key: &str, field: &str) -> Option<String> {
        let record = self.records.get(key)?;
        if let Some(value) = record.get(field) {
            return Some(value.clone());
        }
        for (suffix, unit) in UNIT_SUFFIXES {
            let candidate = format!("{field}_{suffix}");
            if let Some(value) = record.get(&candidate) {
                return Some(format!("{value}{unit}"));
            }
        }
        None
    }
}

/// Render a JSON scalar as the value text the evaluator's quantity
/// grammar parses (numbers without a trailing `.0`, strings verbatim).
/// Non-scalar values render as their JSON text: honest, and
/// `parse_scalar` downstream rejects them with the term named.
fn json_value_text(value: &serde_json::Value) -> String {
    match value {
        serde_json::Value::String(s) => s.clone(),
        serde_json::Value::Number(n) => {
            // `18.0` renders as `18` so the composed `18pF` matches the
            // literal grammar; non-integral values keep their digits.
            n.as_f64().map_or_else(
                || n.to_string(),
                |f| {
                    if f.fract() == 0.0 && f.abs() < 1e15 {
                        format!("{f:.0}")
                    } else {
                        format!("{f}")
                    }
                },
            )
        }
        other => other.to_string(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::realized_input::RealizedInput;

    fn payload_inputs(json: &str) -> RealizedInputs {
        let mut inputs = RealizedInputs::new();
        inputs.insert(
            "blake3:test".to_string(),
            RealizedInput {
                kind: REGISTRY_RECORDS_KIND.to_string(),
                subject: "registry".to_string(),
                bytes: json.as_bytes().to_vec(),
            },
        );
        inputs
    }

    #[test]
    fn payload_round_trips_scalar_fields() {
        let reg = RegistryRecords::from_realized_inputs(&payload_inputs(
            r#"{"records": {"abracon_abm8_16mhz_18pf":
                {"class": "crystal", "cl_pf": 18.0, "esr_ohm": 60}}}"#,
        ));
        let fields = reg.get("abracon_abm8_16mhz_18pf").expect("record present");
        assert_eq!(fields.get("class").map(String::as_str), Some("crystal"));
        assert_eq!(fields.get("cl_pf").map(String::as_str), Some("18"));
    }

    // frob:tests crates/regolith-lower/src/registry.rs::RegistryRecords.from_pairs kind="unit"
    #[test]
    fn unit_suffix_field_lookup_composes_the_literal() {
        let reg = RegistryRecords::from_pairs(&[(
            "xtal",
            &[("class", "crystal"), ("cl_pf", "18"), ("esr_ohm", "60")],
        )]);
        assert_eq!(reg.field("xtal", "cl").as_deref(), Some("18pF"));
        assert_eq!(reg.field("xtal", "esr").as_deref(), Some("60ohm"));
        assert_eq!(reg.field("xtal", "class").as_deref(), Some("crystal"));
        assert_eq!(reg.field("xtal", "absent"), None);
        assert_eq!(reg.field("missing", "cl"), None);
    }

    #[test]
    fn malformed_payload_is_skipped_not_fatal() {
        let reg = RegistryRecords::from_realized_inputs(&payload_inputs("not json"));
        assert!(reg.is_empty());
    }

    #[test]
    fn foreign_kinds_are_ignored() {
        let mut inputs = RealizedInputs::new();
        inputs.insert(
            "blake3:geo".to_string(),
            RealizedInput {
                kind: "geometry.realized".to_string(),
                subject: "part".to_string(),
                bytes: b"{}".to_vec(),
            },
        );
        assert!(RegistryRecords::from_realized_inputs(&inputs).is_empty());
    }
}
