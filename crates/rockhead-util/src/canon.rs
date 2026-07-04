//! Canonical encoding and domain-tagged content addressing (AD-6/AD-18).
//!
//! Substrate reference: `docs/substrate/07` and AD-5/AD-6. Content
//! addresses are `blake3(domain_tag || schema_version ||
//! canonical_cbor(value))`. JSON is the human-facing interchange and
//! durable artifact; canonical CBOR exists ONLY as hash input -- nothing
//! hashes JSON anywhere (AD-18). The canonical encoder enforces key
//! ordering and rejects NaN/non-finite (compiler bugs upstream). This
//! lives at the bottom of the layering (`rockhead-util`) so every crate
//! that hashes (`rockhead-sem` snapshot hashes, `rockhead-oblig`
//! obligation keys, future foreign-content pinning) shares ONE
//! implementation; `rockhead-oblig` re-exports these names unchanged.

use ciborium::value::{CanonicalValue, Value};
use serde::Serialize;

/// Schema version stamped on every cross-boundary payload (AD-5),
/// folded into every content address (AD-18). Bumped whenever a
/// serialized shape changes; the facade asserts it against the core at
/// import.
pub const SCHEMA_VERSION: u32 = 1;

/// Canonically encode a value to CBOR bytes: deterministic key order,
/// no floating NaN/non-finite. The ONLY hash input encoder (AD-6).
///
/// Encodes with `ciborium`, then walks the resulting dynamic [`Value`]
/// tree: every map is re-sorted by RFC 7049/8949 canonical key order
/// (`CanonicalValue`, byte-length-then-lexical) regardless of the
/// original struct/collection's serialize order, and every float is
/// checked for finiteness, before re-encoding. This makes the byte
/// output stable across platforms and immune to accidental map-order
/// drift even if a future type sneaks in an unordered map.
///
/// # Errors
/// Returns [`EncodeError::NonFiniteFloat`] if the value contains a
/// non-finite float (a compiler bug upstream, surfaced here rather
/// than silently hashed), or [`EncodeError::Serialize`] if the
/// underlying CBOR codec fails.
pub fn canonical_cbor<T: Serialize>(value: &T) -> Result<Vec<u8>, EncodeError> {
    let mut raw = Vec::new();
    ciborium::into_writer(value, &mut raw).map_err(|e| EncodeError::Serialize(e.to_string()))?;
    let parsed: Value =
        ciborium::from_reader(raw.as_slice()).map_err(|e| EncodeError::Serialize(e.to_string()))?;
    let canonical = canonicalize(parsed)?;
    let mut out = Vec::new();
    ciborium::into_writer(&canonical, &mut out)
        .map_err(|e| EncodeError::Serialize(e.to_string()))?;
    Ok(out)
}

/// Recursively enforce canonical map-key ordering and reject
/// non-finite floats anywhere in the value tree.
fn canonicalize(value: Value) -> Result<Value, EncodeError> {
    match value {
        Value::Float(f) => {
            if f.is_finite() {
                Ok(Value::Float(f))
            } else {
                Err(EncodeError::NonFiniteFloat)
            }
        }
        Value::Array(items) => {
            let items = items
                .into_iter()
                .map(canonicalize)
                .collect::<Result<Vec<_>, _>>()?;
            Ok(Value::Array(items))
        }
        Value::Map(entries) => {
            let mut entries = entries
                .into_iter()
                .map(|(k, v)| Ok((canonicalize(k)?, canonicalize(v)?)))
                .collect::<Result<Vec<_>, EncodeError>>()?;
            entries.sort_by(|(k1, _), (k2, _)| {
                CanonicalValue::from(k1.clone()).cmp(&CanonicalValue::from(k2.clone()))
            });
            Ok(Value::Map(entries))
        }
        Value::Tag(tag, inner) => Ok(Value::Tag(tag, Box::new(canonicalize(*inner)?))),
        other => Ok(other),
    }
}

/// The domain address of a value: `blake3(domain_tag || schema_version
/// || canonical_cbor(value))` as a lowercase hex digest.
///
/// `domain_tag` and [`SCHEMA_VERSION`] are folded into the hash input
/// ahead of the payload bytes so two different schemas (or two
/// versions of the same schema) can never collide on a hash even if
/// their canonical CBOR happened to coincide.
///
/// # Errors
/// Propagates [`canonical_cbor`] failure.
pub fn content_address<T: Serialize>(domain_tag: &str, value: &T) -> Result<String, EncodeError> {
    let payload = canonical_cbor(value)?;
    let mut bytes = Vec::with_capacity(domain_tag.len() + 4 + payload.len());
    bytes.extend_from_slice(domain_tag.as_bytes());
    bytes.extend_from_slice(&SCHEMA_VERSION.to_le_bytes());
    bytes.extend_from_slice(&payload);
    Ok(crate::hash_hex(&bytes))
}

/// Failure canonically encoding a value.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum EncodeError {
    /// A non-finite float reached the canonical encoder (upstream bug).
    NonFiniteFloat,
    /// The CBOR serializer failed.
    Serialize(String),
}

#[cfg(test)]
mod tests {
    use serde::Serialize;

    use super::{canonical_cbor, content_address, EncodeError};

    #[derive(Serialize)]
    struct Sample {
        a: u32,
        b: String,
        c: f64,
    }

    // Determinism (same value -> same bytes -> same hash) and non-finite
    // rejection are property-tested with the encoder body (WO-13); the
    // 3-OS hash-diff CI job (AD-6) is the cross-platform guard.
    #[test]
    fn content_address_is_deterministic() {
        let v = Sample {
            a: 1,
            b: "hi".to_string(),
            c: 2.5,
        };
        let addr1 = content_address("rockhead.oblig.test", &v).unwrap();
        let addr2 = content_address("rockhead.oblig.test", &v).unwrap();
        assert_eq!(addr1, addr2);
    }

    #[test]
    fn content_address_separates_domains() {
        let v = Sample {
            a: 1,
            b: "hi".to_string(),
            c: 2.5,
        };
        let addr1 = content_address("domain.a", &v).unwrap();
        let addr2 = content_address("domain.b", &v).unwrap();
        assert_ne!(addr1, addr2);
    }

    #[test]
    fn non_finite_float_is_rejected() {
        let v = Sample {
            a: 1,
            b: "hi".to_string(),
            c: f64::NAN,
        };
        assert_eq!(canonical_cbor(&v), Err(EncodeError::NonFiniteFloat));

        let v = Sample {
            a: 1,
            b: "hi".to_string(),
            c: f64::INFINITY,
        };
        assert_eq!(canonical_cbor(&v), Err(EncodeError::NonFiniteFloat));
    }

    #[test]
    fn canonical_cbor_round_trips_and_is_stable_across_field_order() {
        #[derive(Serialize)]
        struct AB {
            a: u32,
            b: u32,
        }
        #[derive(Serialize)]
        struct BA {
            b: u32,
            a: u32,
        }
        let ab = canonical_cbor(&AB { a: 1, b: 2 }).unwrap();
        let ba = canonical_cbor(&BA { b: 2, a: 1 }).unwrap();
        assert_eq!(
            ab, ba,
            "canonical encoding sorts map keys regardless of struct field order"
        );

        let decoded: ciborium::value::Value = ciborium::from_reader(ab.as_slice()).unwrap();
        let a_val = decoded
            .as_map()
            .unwrap()
            .iter()
            .find(|(k, _)| k.as_text() == Some("a"))
            .unwrap()
            .1
            .as_integer()
            .unwrap();
        assert_eq!(i64::try_from(a_val).unwrap(), 1);
    }
}
