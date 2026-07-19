//! `PowerNetPayload`: the cuprite facility-power distribution payload
//! (charter toolchain/43-power-distribution.md secs. 1-3, D248/AD-42).
//!
//! One schema-versioned, Rust-sourced record (AD-5/AD-25 growth rule: a
//! schemars schema in `regolith-oblig`, content-addressed via the one
//! encoder, a payload kind on the D96 channel -- kind string `power`),
//! mirroring `flownet.rs`'s idiom exactly (WO-133's named precedent):
//! buses are nodes, branches (sources/transformers/feeders/protective
//! devices) are edges, current (kVA) is the conserved flow, voltage is
//! the potential (charter 43 sec. 1). Lowering (WO-133 deliverable 2,
//! `regolith_lower::power_payload`) turns a declared `power` net into
//! this serialized, content-addressed record; every `elec.power.*`
//! claim lowers to an ordinary obligation carrying a
//! `PayloadRef { kind: "power", .. }` pointing at it.
//!
//! D250.3 (safety honesty -- the rule that outranks convenience): every
//! field a model needs but an author has not declared from a real
//! source is `Option::None`, NEVER a default. `available_fault_current`,
//! `x_over_r`, a transformer's `pct_z` -- an unverifiable input is a
//! named absence carried straight through to the claim's deferral, not
//! synthesized here or anywhere upstream of the model.
//!
//! D255 (the cross-standard guard): every apparatus record's declared
//! `standard_family` rides on the payload so lowering/claim-routing can
//! name a mixed-family crossing without building any conversion table
//! (translating one family's rating into another's assumption is
//! exactly the "correctly-computed, lethally-wrong" move D250 forbids).
//!
//! This module defines the WIRE SHAPE only. Nothing here reads source,
//! touches IO, or emits diagnostics (mirrors `flownet.rs`/`frame.rs`).
//!
//! Determinism (AD-6): every collection is an ordered `Vec` (elaboration
//! sorts before construction), so [`PowerNetPayload::content_digest`] is
//! stable across builds of the same source.

use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

use crate::flownet::{RecordRef, ScalarInterval};
use regolith_util::canon::{content_address, EncodeError};

/// Domain tag folded into every power content address (AD-18): keeps a
/// power digest from colliding with any other payload kind even if the
/// canonical CBOR bytes happened to coincide.
// frob:doc docs/modules/regolith-oblig.md#power
pub const POWER_DOMAIN_TAG: &str = "power";

/// A bus identifier within a power net (a stable elaboration-assigned
/// name -- the power discipline's node, charter 43 sec. 1).
// frob:doc docs/modules/regolith-oblig.md#power
pub type BusId = String;

/// A standard family a power apparatus/conductor record is authored
/// against (D255, the cross-standard guard). Named, never inferred --
/// a record with no declared family cannot participate in the guard's
/// crossing check and lowering treats that absence honestly.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
// frob:doc docs/modules/regolith-oblig.md#power
pub enum StandardFamily {
    /// IEC (60909 short-circuit, 60364 installation practice, ...).
    Iec,
    /// NEC (NFPA 70 conductor/ampacity/demand-load practice).
    Nec,
    /// ANSI/NEMA (switchgear ratings, motor code letters, ...).
    AnsiNema,
}

/// One bus: a power-discipline node (charter 43 sec. 1) with its
/// nominal voltage and phase count.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#power
pub struct Bus {
    /// The stable bus id (elaboration-assigned).
    pub id: BusId,
    /// The bus's nominal voltage interval.
    pub nominal_voltage: ScalarInterval,
    /// The number of phases (1 or 3; charter 43 sec. 2 vocabulary).
    pub phases: u8,
    /// The standard family this bus's rating was authored against
    /// (D255), when declared.
    pub standard_family: Option<StandardFamily>,
}

/// The constructor kind of a power branch (charter 43 sec. 2
/// vocabulary): every apparatus an electrical engineer already names.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
// frob:doc docs/modules/regolith-oblig.md#power
pub enum BranchKind {
    /// A utility point of delivery.
    Service,
    /// An on-site generator.
    Generator,
    /// A transformer (kVA/%Z/vector-group/taps -- see [`Transformer`]).
    Transformer,
    /// A conductor run (size/length/raceway -- see [`Feeder`]).
    Feeder,
    /// A busway run.
    Busway,
    /// A protective device (breaker/fuse/relay -- see
    /// [`ProtectiveDevice`]).
    ProtectiveDevice,
}

/// A source's declared electrical characteristics (charter 43 sec. 2).
/// Every field is an `Option` (D250.3): a source with no declared
/// available fault current is a NAMED ABSENCE, never a default -- the
/// fault/withstand/arc-flash claims defer by name over the missing
/// field rather than assuming a "typical" utility stiffness.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#power
pub struct SourceParams {
    /// The available fault current at the point of delivery, when a
    /// real source (utility letter, generator datasheet) declares it.
    pub available_fault_current: Option<ScalarInterval>,
    /// The source's X/R ratio, when declared.
    pub x_over_r: Option<ScalarInterval>,
    /// The source's nominal voltage, when declared (may duplicate the
    /// adjoining bus's `nominal_voltage`; kept here so a source's own
    /// declared value is distinguishable from the bus's).
    pub voltage: Option<ScalarInterval>,
}

/// A transformer's nameplate parameters (charter 43 sec. 2). `pct_z`
/// and `x_over_r` are `Option` (D250.3): an undeclared %Z means every
/// claim needing it (fault current, transformer loading) defers by
/// name rather than assuming a nameplate-typical value.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#power
pub struct Transformer {
    /// The transformer's kVA rating.
    pub kva: ScalarInterval,
    /// The percent impedance, when declared from a nameplate/datasheet.
    pub pct_z: Option<ScalarInterval>,
    /// The X/R ratio, when declared.
    pub x_over_r: Option<ScalarInterval>,
    /// The vector group (e.g. `"Dyn11"`), when declared.
    pub vector_group: Option<String>,
    /// Declared tap positions (percent, e.g. `[-5.0, 0.0, 5.0]`), when
    /// the transformer has taps.
    pub taps: Vec<f64>,
    /// The standard family this nameplate was authored against (D255).
    pub standard_family: Option<StandardFamily>,
}

/// A feeder's conductor-run parameters (charter 43 sec. 2): the
/// declared conductor record, run length, and the raceway/ambient/
/// grouping context ampacity derating needs.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#power
pub struct Feeder {
    /// The hash-pinned conductor record (size, insulation, ampacity
    /// table row).
    pub conductor: RecordRef,
    /// The run length.
    pub length: ScalarInterval,
    /// The declared raceway kind (e.g. `"conduit"`, `"cable_tray"`,
    /// `"free_air"`), when declared -- ampacity derating (NEC 310.15)
    /// needs it; absent, the ampacity claim defers by name.
    pub raceway: Option<String>,
    /// The declared ambient temperature, when declared.
    pub ambient: Option<ScalarInterval>,
    /// The declared count of current-carrying conductors grouped with
    /// this run (adjustment-factor derating), when declared.
    pub grouping: Option<u32>,
    /// The standard family this conductor record was authored against
    /// (D255).
    pub standard_family: Option<StandardFamily>,
}

/// A protective device's rating (charter 43 sec. 2): frame/trip/
/// interrupting rating and its time-current curve reference, when a
/// curve is declared (coordination/selectivity needs it; withstand/
/// fault-current claims can discharge on frame+interrupting alone).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#power
pub struct ProtectiveDevice {
    /// The device frame rating.
    pub frame: ScalarInterval,
    /// The device trip setting, when declared (a fixed-trip device
    /// carries `None`).
    pub trip: Option<ScalarInterval>,
    /// The device's interrupting rating, when declared.
    pub interrupting_rating: Option<ScalarInterval>,
    /// The hash-pinned time-current curve record, when declared
    /// (coordination claims defer by name without one).
    pub curve: Option<RecordRef>,
    /// The standard family this device's rating was authored against
    /// (D255).
    pub standard_family: Option<StandardFamily>,
}

/// A branch's apparatus-specific parameters -- exactly one populated
/// per [`BranchKind`], mirroring `flownet.rs::EdgeParams`'s tagged-union
/// idiom (`source`/`transformer`/`feeder`/`protective_device` carry
/// their own shape; `service`/`generator`/`busway` reuse
/// [`SourceParams`]/an empty marker as charter 43 sec. 2 does not name
/// further nameplate fields for them beyond the source's).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case", tag = "apparatus")]
// frob:doc docs/modules/regolith-oblig.md#power
pub enum BranchParams {
    /// A utility service or generator (charter 43 sec. 2's source
    /// apparatus): the [`SourceParams`] D250.3 option set.
    Source(SourceParams),
    /// A transformer (nameplate parameters, [`Transformer`]).
    Transformer(Transformer),
    /// A feeder or busway conductor run ([`Feeder`]).
    Feeder(Feeder),
    /// A breaker/fuse/relay ([`ProtectiveDevice`]).
    ProtectiveDevice(ProtectiveDevice),
}

/// One power branch: a directed (positive-sense `a -> b`, the declared
/// feed direction, charter 43 sec. 1) apparatus edge between two buses.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#power
pub struct Branch {
    /// The stable branch id (elaboration-assigned).
    pub id: String,
    /// The constructor kind.
    pub kind: BranchKind,
    /// The positive-sense (feed-direction) tail bus.
    pub a: BusId,
    /// The positive-sense (feed-direction) head bus.
    pub b: BusId,
    /// The apparatus-specific parameters.
    pub params: BranchParams,
}

/// A motor load's nameplate fields (charter 43 sec. 2's motor
/// vocabulary), present only when a `load` declares itself a motor.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#power
pub struct MotorFields {
    /// The motor's horsepower/kW rating.
    pub hp_kw: ScalarInterval,
    /// The NEMA/IEC locked-rotor code letter, when declared (motor-
    /// start voltage-dip claims defer by name without one).
    pub code_letter: Option<String>,
    /// The service factor, when declared.
    pub service_factor: Option<f64>,
    /// The power factor, when declared.
    pub power_factor: Option<f64>,
    /// The efficiency, when declared.
    pub efficiency: Option<f64>,
}

/// A declared load (charter 43 sec. 2): connected demand at a bus.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#power
pub struct Load {
    /// The stable load id (elaboration-assigned).
    pub id: String,
    /// The bus this load is connected to.
    pub bus: BusId,
    /// The connected kVA.
    pub connected_kva: ScalarInterval,
    /// The demand factor, when declared (NEC 220 demand-load claims
    /// defer by name without one).
    pub demand_factor: Option<f64>,
    /// Whether the load is continuous (NEC 220/210 125% posture).
    pub continuous: bool,
    /// The declared load class (e.g. `"lighting"`, `"motor"`,
    /// `"receptacle"`), when declared.
    pub class: Option<String>,
    /// The motor nameplate fields, when this load is a motor.
    pub motor: Option<MotorFields>,
}

/// The serialized power net payload (charter 43 secs. 1-3, verbatim): a
/// content-addressed record carrying every bus/branch/load a power
/// model needs to discharge an `elec.power.*` claim.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, JsonSchema)]
// frob:doc docs/modules/regolith-oblig.md#power
pub struct PowerNetPayload {
    /// Every bus in the network (elaboration-sorted for determinism).
    pub buses: Vec<Bus>,
    /// Every branch (elaboration-sorted for determinism).
    pub branches: Vec<Branch>,
    /// Every declared load (elaboration-sorted for determinism).
    pub loads: Vec<Load>,
}

impl PowerNetPayload {
    /// The AD-18 content address of this payload under the `power`
    /// domain tag -- the digest a `PayloadRef` pins and the store keys
    /// on. Stable across builds of the same source (AD-6).
    ///
    /// # Errors
    /// Propagates [`EncodeError`] from the canonical encoder (only a
    /// non-finite float or a serializer failure -- an upstream bug).
    // frob:doc docs/modules/regolith-oblig.md#power
    // frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
    pub fn content_digest(&self) -> Result<String, EncodeError> {
        content_address(POWER_DOMAIN_TAG, self)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample() -> PowerNetPayload {
        PowerNetPayload {
            buses: vec![
                Bus {
                    id: "Svc1".to_string(),
                    nominal_voltage: ScalarInterval {
                        lo: 480.0,
                        hi: 480.0,
                        unit: "V".to_string(),
                    },
                    phases: 3,
                    standard_family: Some(StandardFamily::Nec),
                },
                Bus {
                    id: "MainBus".to_string(),
                    nominal_voltage: ScalarInterval {
                        lo: 480.0,
                        hi: 480.0,
                        unit: "V".to_string(),
                    },
                    phases: 3,
                    standard_family: Some(StandardFamily::Nec),
                },
            ],
            branches: vec![Branch {
                id: "f1".to_string(),
                kind: BranchKind::Transformer,
                a: "Svc1".to_string(),
                b: "MainBus".to_string(),
                params: BranchParams::Transformer(Transformer {
                    kva: ScalarInterval {
                        lo: 500.0,
                        hi: 500.0,
                        unit: "kVA".to_string(),
                    },
                    pct_z: None,
                    x_over_r: None,
                    vector_group: None,
                    taps: vec![],
                    standard_family: Some(StandardFamily::Nec),
                }),
            }],
            loads: vec![Load {
                id: "Motor1".to_string(),
                bus: "MainBus".to_string(),
                connected_kva: ScalarInterval {
                    lo: 10.0,
                    hi: 10.0,
                    unit: "kVA".to_string(),
                },
                demand_factor: None,
                continuous: false,
                class: Some("motor".to_string()),
                motor: None,
            }],
        }
    }

    #[test]
    fn power_payload_round_trips_json() {
        let payload = sample();
        let json = serde_json::to_string(&payload).unwrap();
        let back: PowerNetPayload = serde_json::from_str(&json).unwrap();
        assert_eq!(back, payload);
    }

    // frob:tests crates/regolith-oblig/src/power.rs::PowerNetPayload.content_digest kind="unit"
    #[test]
    fn content_digest_is_stable_and_field_sensitive() {
        let payload = sample();
        let d1 = payload.content_digest().unwrap();
        let d2 = payload.content_digest().unwrap();
        assert_eq!(d1, d2, "same payload -> same digest (AD-6)");

        let mut other = sample();
        other.buses.push(Bus {
            id: "PanelA".to_string(),
            nominal_voltage: ScalarInterval {
                lo: 208.0,
                hi: 208.0,
                unit: "V".to_string(),
            },
            phases: 3,
            standard_family: Some(StandardFamily::Nec),
        });
        assert_ne!(
            d1,
            other.content_digest().unwrap(),
            "a changed field must change the digest"
        );
    }

    /// D250.3: a source with no declared available fault current
    /// round-trips as `None`, never a synthesized default.
    #[test]
    fn undeclared_source_fields_stay_none() {
        let params = SourceParams {
            available_fault_current: None,
            x_over_r: None,
            voltage: None,
        };
        let json = serde_json::to_value(&params).unwrap();
        assert!(json["available_fault_current"].is_null());
        let back: SourceParams = serde_json::from_value(json).unwrap();
        assert!(back.available_fault_current.is_none());
    }

    /// D255: two branches whose apparatus records declare different
    /// standard families is representable and distinct in the payload
    /// (the cross-standard guard's job is to notice this, not to
    /// forbid declaring it).
    #[test]
    fn branch_params_tag_on_apparatus() {
        let feeder = BranchParams::Feeder(Feeder {
            conductor: RecordRef {
                digest: "blake3:cc".to_string(),
                name: "cu_4_0awg".to_string(),
            },
            length: ScalarInterval {
                lo: 30.0,
                hi: 30.0,
                unit: "m".to_string(),
            },
            raceway: None,
            ambient: None,
            grouping: None,
            standard_family: Some(StandardFamily::Iec),
        });
        let json = serde_json::to_value(&feeder).unwrap();
        assert_eq!(json["apparatus"], "feeder");
        assert_eq!(json["standard_family"], "iec");
    }
}
