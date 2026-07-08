//! The realized-IR input channel (WO-42 deliverable 3, AD-25/D128).
//!
//! `lower()`/`lower_and_discharge()` are pure functions of (sources,
//! realized-IR inputs): the orchestrator resolves realized-domain IR
//! digests against the WO-30 content store and hands the resolved
//! bytes in here -- AD-17 purity is preserved (the rule forbids IO in
//! the pipeline, not realized content as an input). This module is the
//! pure data carrier only; resolving a digest to bytes is the caller's
//! IO, done before `lower()` is ever called.

use std::collections::BTreeMap;

/// One realized-domain IR supplied to a build: the caller-resolved
/// bytes plus the metadata `regolith debug ir` lists alongside them
/// (kind, subject) -- the content digest is the [`RealizedInputs`] map
/// key (AD-18), so `bytes` alone would be enough for extraction but not
/// for inspectability.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RealizedInput {
    /// The D96 payload kind (e.g. `"geometry.realized"`, `"layout.realized"`).
    pub kind: String,
    /// The subject the IR was realized for (e.g. the part/block name
    /// the `from=` ref names), used to match a flownet's `from=<ref>`
    /// edge to the realized-geometry record that backs it.
    pub subject: String,
    /// The resolved record bytes (the [`crate::extract::extract_path`]
    /// input).
    pub bytes: Vec<u8>,
}

/// Every realized-IR input supplied to a build, keyed by content
/// digest (AD-18). Empty for a build with no realized-domain inputs --
/// the D128 placeholder path: dependent obligations stay honestly
/// indeterminate, naming the missing IR.
pub type RealizedInputs = BTreeMap<String, RealizedInput>;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_realized_inputs_is_the_placeholder_default() {
        let inputs: RealizedInputs = RealizedInputs::new();
        assert!(inputs.is_empty());
    }

    #[test]
    fn realized_input_carries_kind_subject_and_bytes() {
        let mut inputs = RealizedInputs::new();
        inputs.insert(
            "blake3:aa".to_string(),
            RealizedInput {
                kind: "geometry.realized".to_string(),
                subject: "manifold.jacket".to_string(),
                bytes: vec![1, 2, 3],
            },
        );
        let input = inputs.get("blake3:aa").unwrap();
        assert_eq!(input.kind, "geometry.realized");
        assert_eq!(input.subject, "manifold.jacket");
        assert_eq!(input.bytes, vec![1, 2, 3]);
    }
}
