//! `HarnessPayload`: the cuprite wiring-harness routed-runs payload
//! (WO-34, D99).
//!
//! One schema-versioned, Rust-sourced record (AD-5 precedent, mirrors
//! [`crate::flownet::FlownetPayload`]) content-addressed and carried on
//! [`crate::obligation::Obligation`] payload refs the same way a
//! flownet is: elaboration (`regolith_lower::harness_lower`, a later
//! dispatch) turns a `harness:` block's declared runs into this
//! serialized record via the WO-32 extraction seam
//! (`regolith_lower::extract`) -- the SAME module a fluid edge reads,
//! never a second copy. Rule packs (E06xx ampacity rules) and mass
//! budgets read `run.length`/`run.bundle` off this payload (AD-22).
//!
//! This module defines the WIRE SHAPE only. The lowering pass that
//! PRODUCES it and the `BuildPayload.harnesses` field wiring live in
//! `regolith-lower`/`regolith-api`; nothing here reads source, touches
//! IO, or emits diagnostics.
//!
//! Determinism (AD-6): `runs` is an `IndexMap` sorted by run name at
//! construction (elaboration's responsibility, mirroring
//! `FlownetPayload.edges`'s sort-before-construct discipline), and
//! `environments` is a `BTreeMap` (key order intrinsic), so
//! [`HarnessPayload::content_digest`] is stable across builds of the
//! same source.

use indexmap::IndexMap;
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

use crate::flownet::ScalarInterval;

/// Domain tag folded into every harness content address (AD-18): keeps
/// a harness digest from colliding with any other payload kind even if
/// the canonical CBOR bytes happened to coincide.
pub const HARNESS_DOMAIN_TAG: &str = "harness";

/// One segment of a run's routed path: a structural ref extracted
/// through the shared WO-32 seam, with its resolved length and the
/// per-segment environment role (the seam's shared "wire run is a
/// multi-segment path" shape, `regolith_lower::extract` module doc).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
pub struct RunSegment {
    /// The structural ref this segment was extracted along (e.g.
    /// `"frame.spine_tube"`).
    pub structural_ref: String,
    /// The segment's environment role (shared slot with fluid edges).
    pub role: String,
    /// The extracted centreline length, m.
    pub length: ScalarInterval,
}

/// A run's routed-PATH resolution: either declared waypoints (fully
/// extracted, cited to a snapshot) or the planner-routed marker,
/// resolved or not (D99: never hand-asserted in source, INV-21).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum RunRoute {
    /// `along <structural refs>`: every ref extracted and concatenated
    /// in declaration order.
    Waypoints {
        /// The extracted segments, in declaration order.
        segments: Vec<RunSegment>,
        /// Sum of the segment lengths, m.
        total_length: ScalarInterval,
        /// The realized-geometry snapshot hash every segment is cited
        /// to.
        snapshot_hash: String,
    },
    /// `route: free`: planner-routed. `resolved_length` is `None`
    /// until the planner materializes a lockfile row (`cause:
    /// planner(route <run>)`, `regolith_qty::Cause::Planner`); a
    /// consumer reading a run with `resolved_length: None` sees an
    /// honestly indeterminate length, never a fabricated one.
    PlannerFree {
        /// The planner-resolved length, once materialized.
        resolved_length: Option<ScalarInterval>,
    },
}

/// One declared run: its two endpoints, routed-path resolution, and
/// bundle co-routing membership.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
pub struct RunRecord {
    /// The `from` endpoint (`component.port` text, re-tokenized from
    /// the header line elaboration reads).
    pub from: String,
    /// The `to` endpoint.
    pub to: String,
    /// The declared co-routing bundle group, if any.
    pub bundle: Option<String>,
    /// The routed-path resolution.
    pub route: RunRoute,
}

/// The serialized harness payload (D99, verbatim): every declared run
/// plus the connector environment classes the harness names.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
pub struct HarnessPayload {
    /// The harness's declared name.
    pub name: String,
    /// Every declared run, keyed by name, in name order (AD-6).
    pub runs: IndexMap<String, RunRecord>,
    /// Every declared connector environment class, name -> `[lo, hi]`
    /// bound (degC), in name order (`BTreeMap`, AD-6).
    pub environments: std::collections::BTreeMap<String, ScalarInterval>,
}

impl HarnessPayload {
    /// The content-addressed digest of this payload (AD-18): the
    /// citation every `RunRecord` field and rule-pack read is pinned
    /// to.
    ///
    /// # Errors
    /// [`crate::encoding::EncodeError`] when canonical encoding fails
    /// (malformed float, non-canonical map -- see
    /// `regolith_util::canon`).
    pub fn content_digest(&self) -> Result<String, regolith_util::canon::EncodeError> {
        regolith_util::canon::content_address(HARNESS_DOMAIN_TAG, self)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample() -> HarnessPayload {
        let mut runs = IndexMap::new();
        runs.insert(
            "batt_to_kill".to_string(),
            RunRecord {
                from: "battery.pos".to_string(),
                to: "kill_switch.in".to_string(),
                bundle: Some("primary".to_string()),
                route: RunRoute::Waypoints {
                    segments: vec![RunSegment {
                        structural_ref: "frame.spine_tube".to_string(),
                        role: "frame.spine_tube".to_string(),
                        length: ScalarInterval {
                            lo: 1.0,
                            hi: 1.0,
                            unit: "m".to_string(),
                        },
                    }],
                    total_length: ScalarInterval {
                        lo: 1.0,
                        hi: 1.0,
                        unit: "m".to_string(),
                    },
                    snapshot_hash: "blake3:snap".to_string(),
                },
            },
        );
        HarnessPayload {
            name: "MainLoom".to_string(),
            runs,
            environments: std::collections::BTreeMap::new(),
        }
    }

    #[test]
    fn content_digest_is_deterministic() {
        let a = sample().content_digest().unwrap();
        let b = sample().content_digest().unwrap();
        assert_eq!(a, b, "same payload digests identically (AD-6)");
    }

    #[test]
    fn digest_changes_with_length() {
        let mut changed = sample();
        if let RunRoute::Waypoints { total_length, .. } =
            &mut changed.runs.get_mut("batt_to_kill").unwrap().route
        {
            total_length.hi = 2.0;
        }
        assert_ne!(
            sample().content_digest().unwrap(),
            changed.content_digest().unwrap(),
            "the anti-staleness property (G42): a changed length changes the digest"
        );
    }

    #[test]
    fn planner_free_round_trips_unresolved() {
        let mut p = sample();
        p.runs.insert(
            "vr_sense".to_string(),
            RunRecord {
                from: "vr_sensor.sig".to_string(),
                to: "ecu.vr_in".to_string(),
                bundle: Some("shielded_signals".to_string()),
                route: RunRoute::PlannerFree {
                    resolved_length: None,
                },
            },
        );
        let json = serde_json::to_string(&p).unwrap();
        let back: HarnessPayload = serde_json::from_str(&json).unwrap();
        assert_eq!(p, back);
    }
}
