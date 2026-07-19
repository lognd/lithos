//! `std.cost` record wire shapes (WO-54 deliverable 2; toolchain/27
//! sec. 1.2-1.3, 1.5; D147).
//!
//! AD-29's ledger rule: cost is a claim, an estimate is evidence, and
//! every priced number comes from a profile-selected, hash-pinned
//! record -- the compiler contains no prices, rates, or currencies
//! beyond unit machinery. This module defines the WIRE SHAPES only
//! (mirrors `frame.rs`/`flownet.rs`'s precedent): a rate record (shop/
//! labor/regional rates), a pricing record (vendor price breaks by
//! quantity, hash-pinned quotes/catalogs, `valid_until`-windowed), a
//! unit-cost record (RSMeans-shaped assemblies for civil takeoffs),
//! and the itemized-estimate `table`-kind payload (feldspar 09 sec. 4
//! vocabulary) that is a cost claim's evidence. No prices, rates, or
//! currency conversions are literal in this crate or anywhere else in
//! the compiler (AD-29, grep-provable) -- every numeric field here is
//! populated from project/registry record content, never a default.
//!
//! Determinism (AD-6): every collection is an ordered `Vec`, so
//! [`ItemizedEstimate::content_digest`] is stable across builds of the
//! same source.

use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

use crate::flownet::{RecordRef, ScalarInterval};
use regolith_util::canon::{content_address, EncodeError};

/// Domain tag folded into every itemized-estimate content address
/// (AD-18): keeps a cost-estimate digest from colliding with any other
/// payload kind even if the canonical CBOR bytes happened to coincide.
// frob:doc docs/modules/regolith-oblig.md#cost
pub const ITEMIZED_ESTIMATE_DOMAIN_TAG: &str = "cost.itemized_estimate";

/// A shop/labor/regional rate record (toolchain/27 sec. 1.3): the
/// `labor`/`process_rates` refs a `[profiles.cost.<name>]` manifest
/// table names. One named rate per record (a shop rents by hour, a
/// labor grade bills by hour); a profile composes several.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#cost
pub struct RateRecord {
    /// The rate's name (e.g. `"cnc_shop_rate"`, `"assembly_labor"`).
    pub name: String,
    /// The rate itself (currency-per-time; currency is a unit family,
    /// never a literal -- e.g. unit `"USD/hr"`).
    pub rate: ScalarInterval,
    /// Free-form regional/vendor provenance text (diagnostics only).
    pub basis: String,
}

/// One quantity-break price point (toolchain/27 sec. 1.3: "vendor
/// price breaks by quantity").
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#cost
pub struct PriceBreak {
    /// The minimum order quantity this break applies at.
    pub min_qty: f64,
    /// The unit price at this break (currency unit, e.g. `"USD"`).
    pub unit_price: ScalarInterval,
}

/// A vendor pricing record (toolchain/27 sec. 1.3): a hash-pinned
/// quote or catalog snapshot with quantity breaks and a validity
/// window. A claim consuming an EXPIRED record (`valid_until` in the
/// past at build time) is INDETERMINATE, never silently stale (D147
/// sec. 1.3) -- the expiry check itself is an orchestrator concern
/// (deliverable 4); this module only carries the field.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#cost
pub struct PricingRecord {
    /// The priced item's name (e.g. a part number, a material spec).
    pub item: String,
    /// Quantity-break price points, ascending `min_qty` order.
    pub breaks: Vec<PriceBreak>,
    /// ISO-8601 date string after which this record is expired.
    pub valid_until: String,
    /// Free-form vendor/catalog provenance text (diagnostics only).
    pub basis: String,
}

/// An RSMeans-shaped unit-cost assembly record (toolchain/27 sec. 1.3,
/// 1.4: civil takeoff estimators multiply member-schedule/assembly-
/// area quantities by these). One assembly per record (e.g. "CMU wall,
/// 8in, reinforced" priced per square meter).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#cost
pub struct UnitCostRecord {
    /// The assembly's name (e.g. `"cmu_wall_8in_reinforced"`).
    pub assembly: String,
    /// The unit basis this cost is quoted per (e.g. `"m2"`, `"m3"`,
    /// `"each"`).
    pub unit_basis: String,
    /// The unit cost (currency-per-unit-basis, e.g. `"USD/m2"`).
    pub unit_cost: ScalarInterval,
    /// Free-form regional/catalog provenance text (diagnostics only).
    pub basis: String,
}

/// One line of an itemized estimate (toolchain/27 sec. 1.5): item,
/// quantity, unit cost with its pricing record ref, and the extended
/// (quantity x unit cost) total -- computed once at estimate
/// construction time so the payload is a plain data table, never a
/// live recomputation.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#cost
pub struct EstimateLineItem {
    /// The line item's name (part number, assembly, labor line).
    pub item: String,
    /// The priced quantity.
    pub qty: ScalarInterval,
    /// The unit cost applied to this line.
    pub unit_cost: ScalarInterval,
    /// The record this line's price came from (hash-pinned, INV-22).
    pub record: RecordRef,
    /// The extended total (`qty * unit_cost`, same currency unit).
    pub extended: ScalarInterval,
}

/// The itemized-estimate `table`-kind payload (toolchain/27 sec. 1.5):
/// a cost claim's evidence. Content-addressed -- auditable and
/// diffable across builds, so a price change shows as a line-item
/// diff. `exclusions` states what the estimator did NOT price,
/// keeping the total honest (never a silently-partial number).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#cost
pub struct ItemizedEstimate {
    /// The cost profile this estimate was built under (manifest
    /// `[profiles.cost.<name>]` name).
    pub profile: String,
    /// The estimate's line items, in estimator-emission order.
    pub lines: Vec<EstimateLineItem>,
    /// The grand total (sum of `lines[..].extended`, same currency
    /// unit), computed once at construction.
    pub total: ScalarInterval,
    /// Declared exclusions: named things the estimator did not price
    /// (e.g. `"shipping"`, `"civil sitework"`).
    pub exclusions: Vec<String>,
}

impl ItemizedEstimate {
    /// The content digest identifying this estimate (AD-6/AD-18): the
    /// canonical encoding of every field, domain-separated from every
    /// other payload kind.
    ///
    /// # Errors
    /// Propagates [`EncodeError`] from the canonical encoder (only a
    /// non-finite float or a serializer failure -- an upstream bug).
    // frob:doc docs/modules/regolith-oblig.md#cost
    // frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
    pub fn content_digest(&self) -> Result<String, EncodeError> {
        content_address(ITEMIZED_ESTIMATE_DOMAIN_TAG, self)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample() -> ItemizedEstimate {
        ItemizedEstimate {
            profile: "prototype".to_string(),
            lines: vec![EstimateLineItem {
                item: "M3x10 SHCS".to_string(),
                qty: ScalarInterval {
                    lo: 12.0,
                    hi: 12.0,
                    unit: "each".to_string(),
                },
                unit_cost: ScalarInterval {
                    lo: 0.12,
                    hi: 0.12,
                    unit: "USD".to_string(),
                },
                record: RecordRef {
                    digest: "blake3:aa".to_string(),
                    name: "mcmaster_fastener_catalog".to_string(),
                },
                extended: ScalarInterval {
                    lo: 1.44,
                    hi: 1.44,
                    unit: "USD".to_string(),
                },
            }],
            total: ScalarInterval {
                lo: 1.44,
                hi: 1.44,
                unit: "USD".to_string(),
            },
            exclusions: vec!["shipping".to_string()],
        }
    }

    #[test]
    fn itemized_estimate_round_trips_json() {
        let est = sample();
        let json = serde_json::to_string(&est).unwrap();
        let back: ItemizedEstimate = serde_json::from_str(&json).unwrap();
        assert_eq!(back, est);
    }

    // frob:tests crates/regolith-oblig/src/cost.rs::ItemizedEstimate.content_digest kind="unit"
    #[test]
    fn content_digest_is_stable_and_field_sensitive() {
        let est = sample();
        let d1 = est.content_digest().unwrap();
        let d2 = est.content_digest().unwrap();
        assert_eq!(d1, d2, "same value hashes the same way twice");

        let mut other = sample();
        other.exclusions.push("civil sitework".to_string());
        assert_ne!(
            d1,
            other.content_digest().unwrap(),
            "changing a field must change the digest"
        );
    }

    #[test]
    fn rate_record_round_trips_json() {
        let rate = RateRecord {
            name: "cnc_shop_rate".to_string(),
            rate: ScalarInterval {
                lo: 85.0,
                hi: 85.0,
                unit: "USD/hr".to_string(),
            },
            basis: "regional shop quote 2026Q2".to_string(),
        };
        let json = serde_json::to_string(&rate).unwrap();
        let back: RateRecord = serde_json::from_str(&json).unwrap();
        assert_eq!(back, rate);
    }

    #[test]
    fn pricing_record_carries_quantity_breaks_and_validity() {
        let pricing = PricingRecord {
            item: "aluminum_6061_bar_1in".to_string(),
            breaks: vec![
                PriceBreak {
                    min_qty: 1.0,
                    unit_price: ScalarInterval {
                        lo: 12.5,
                        hi: 12.5,
                        unit: "USD".to_string(),
                    },
                },
                PriceBreak {
                    min_qty: 100.0,
                    unit_price: ScalarInterval {
                        lo: 9.75,
                        hi: 9.75,
                        unit: "USD".to_string(),
                    },
                },
            ],
            valid_until: "2026-12-31".to_string(),
            basis: "vendor quote #4471".to_string(),
        };
        let json = serde_json::to_string(&pricing).unwrap();
        let back: PricingRecord = serde_json::from_str(&json).unwrap();
        assert_eq!(back.breaks.len(), 2);
        assert_eq!(back, pricing);
    }

    #[test]
    fn unit_cost_record_round_trips_json() {
        let uc = UnitCostRecord {
            assembly: "cmu_wall_8in_reinforced".to_string(),
            unit_basis: "m2".to_string(),
            unit_cost: ScalarInterval {
                lo: 145.0,
                hi: 145.0,
                unit: "USD/m2".to_string(),
            },
            basis: "RSMeans-shaped fixture".to_string(),
        };
        let json = serde_json::to_string(&uc).unwrap();
        let back: UnitCostRecord = serde_json::from_str(&json).unwrap();
        assert_eq!(back, uc);
    }
}
