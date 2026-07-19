//! The diagnostic code registry: stable regolith-wide code families.
//!
//! Regolith reference: `docs/spec/regolith/09-build-and-lockfile.md`
//! sec. 4. Codes are DATA, defined once here, never inline literals
//! anywhere else. Families are shared across both languages; only the
//! human message is domain-specific.

use std::fmt;

use serde::{Deserialize, Serialize};

/// A diagnostic code family. The hundreds digit of the numeric code
/// (`E03xx` -> [`Family::References`]).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
// frob:doc docs/modules/regolith-diag.md#code
pub enum Family {
    /// `E01xx` -- parse, types, units, grammar (incompatible quantities,
    /// `==` on continuous).
    Parse,
    /// `E02xx` -- the AD-23 net disciplines' compile checks: fluorite's
    /// flownet family (E0201-E0203, WO-31 deliverable 3) plus calcite's
    /// circulation and load-path families (E0204-E0209, WO-47
    /// deliverable 4, calcite/03 sec. 3) -- one E-block shared by every
    /// `NetDiscipline` plugin over the ONE `regolith_sem::net_core`
    /// (AD-23), so every net-discipline diagnostic is greppable as one
    /// set. Checked against the tree's registry before allocating
    /// calcite's block (the WO-47 dispatch caveat): offsets 4-9 were
    /// free.
    FluidNet,
    /// `E03xx` -- references, ownership, structure.
    References,
    /// `E04xx` -- contracts (capability vs demand, ledgers, budgets).
    Contracts,
    /// `E05xx` -- instances and symmetry.
    Instances,
    /// `E06xx` -- rule packs (DFM / DRC / ERC), with rule provenance.
    RulePacks,
    /// `E07xx` -- evidence (indeterminate discharge, release assumptions).
    Evidence,
    /// `L08xx` -- style/advisory lints (WO-40, Warning by default; renders
    /// as `L08xx` rather than `E08xx` -- see [`DiagCode::fmt`]). Configured
    /// per code via `magnetite.toml [lints]` (`allow`/`warn`/`deny`); `deny`
    /// promotes the emitted [`super::Severity`] to `Error` at emission time
    /// in ONE place (`regolith_diag::lints::apply_lint_config`) -- the
    /// code's numeric family never changes.
    Lint,
    /// `E09xx` -- emission/packaging: a shipped artifact set is
    /// incomplete, a drafting audit refuses a sheet, or a package's
    /// artifact index drifts from what was actually written (D247.2,
    /// WO-131). D247.1's one-code-space ruling: a failure in this
    /// family may be raised on either side of the language fence
    /// (Rust or Python), same as every other family.
    Emission,
    /// `E10xx` -- injection/override: the D243/D246 override channel
    /// refusing an unexplained override, a source-only claim target
    /// (the D246 claims/evidence boundary), or an override naming a
    /// target that cannot be resolved (D247.2, WO-131). Offsets 1-3
    /// are RESERVED for WO-129A -- registered with their meanings so
    /// that WO can raise them without opening a second registry, but
    /// not yet implemented by this WO.
    Injection,
    /// `E11xx` -- bring-up/harness: a debug-evidence package refused
    /// as release-gate evidence, an expected-signal provenance ref
    /// that does not resolve, or a debug tap-map that disagrees with
    /// the artifact it claims to describe (D247.2, WO-131).
    BringUp,
}

impl Family {
    /// The numeric base of this family (`E03xx` -> `300`).
    #[must_use]
    // frob:doc docs/modules/regolith-diag.md#code
    pub const fn base(self) -> u16 {
        match self {
            Family::Parse => 100,
            Family::FluidNet => 200,
            Family::References => 300,
            Family::Contracts => 400,
            Family::Instances => 500,
            Family::RulePacks => 600,
            Family::Evidence => 700,
            Family::Lint => 800,
            Family::Emission => 900,
            Family::Injection => 1000,
            Family::BringUp => 1100,
        }
    }
}

/// A stable diagnostic code: a family plus its within-family offset.
/// Renders as `E0301` (family base + offset, zero-padded to four
/// digits).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
// frob:doc docs/modules/regolith-diag.md#code
pub struct DiagCode {
    /// The owning family.
    pub family: Family,
    /// Offset within the family (`E0301` -> `1`).
    pub offset: u16,
}

impl DiagCode {
    /// Construct a code in `family` at `offset`.
    #[must_use]
    // frob:doc docs/modules/regolith-diag.md#code
    pub const fn new(family: Family, offset: u16) -> DiagCode {
        DiagCode { family, offset }
    }

    /// The full numeric code (`E0301` -> `301`).
    #[must_use]
    // frob:doc docs/modules/regolith-diag.md#code
    pub const fn number(self) -> u16 {
        self.family.base() + self.offset
    }
}

impl fmt::Display for DiagCode {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let prefix = if self.family == Family::Lint {
            "L"
        } else {
            "E"
        };
        write!(f, "{prefix}{:04}", self.number())
    }
}

/// The registry of named codes the checks refer to by symbol. Every
/// code a check emits MUST be declared here (WO-06 ground rule: codes
/// are data). Grows as each later WO adds its checks.
pub mod codes {
    use super::{DiagCode, Family};

    /// `E0101` -- arithmetic between incompatible quantities.
    // frob:doc docs/modules/regolith-diag.md#code
    pub const INCOMPATIBLE_QUANTITIES: DiagCode = DiagCode::new(Family::Parse, 1);
    /// `E0102` -- `==` used on a continuous quantity (equality ban).
    // frob:doc docs/modules/regolith-diag.md#code
    pub const EQUALITY_ON_CONTINUOUS: DiagCode = DiagCode::new(Family::Parse, 2);
    /// `E0103` -- a `[a, b]` interval and a `[i .. j]` index range were
    /// confused: both separators in one bracket, or a range endpoint
    /// carrying a unit/fractional literal (regolith/02 sec. 3).
    // frob:doc docs/modules/regolith-diag.md#code
    pub const INTERVAL_RANGE_CONFUSION: DiagCode = DiagCode::new(Family::Parse, 3);
    /// `E0104` -- an illegal logarithmic-unit sum: after cancelling
    /// subtracted references against added ones, more than one reference
    /// survives (`dBm + dBm`) or a subtracted reference is uncancelled
    /// (regolith/02 sec. 5a; the linear product/quotient is not a valid
    /// quantity).
    // frob:doc docs/modules/regolith-diag.md#code
    pub const ILLEGAL_LOG_SUM: DiagCode = DiagCode::new(Family::Parse, 4);
    /// `E0105` -- a combinational (instantaneous `=`) cycle entirely
    /// within one clock/continuous domain, with no converter or register
    /// delta to break it (an algebraic loop, INV-16). A cross-domain edge
    /// always passes through a converter (a ZOH delta by type), so no
    /// zero-delay cycle can cross the continuous/discrete boundary; this
    /// code flags only a within-domain loop the source actually declares.
    // frob:doc docs/modules/regolith-diag.md#code
    pub const COMBINATIONAL_CYCLE: DiagCode = DiagCode::new(Family::Parse, 5);
    /// `E0106` -- a `run <name>:` line inside a `harness:` block (D99,
    /// WO-34 deliverable 1) whose header does not spell both a `from`
    /// and a `to` endpoint. Parse-time structural validation only
    /// (required-field presence): it does not resolve the endpoint refs
    /// (that is elaboration's job, WO-34 deliverable 2) -- only that the
    /// two keywords are both present, so a run with no path to extract
    /// a length over is rejected as close to the source as possible.
    // frob:doc docs/modules/regolith-diag.md#code
    pub const RUN_MISSING_ENDPOINT: DiagCode = DiagCode::new(Family::Parse, 6);
    /// `E0107` -- `by select(...)` (WO-56, D161) declared with an
    /// empty candidate list. A choice point over zero candidates has
    /// nothing to search, so it is rejected as a structural,
    /// parse-adjacent malformation (same L1 tier as
    /// `RUN_MISSING_ENDPOINT`) rather than surfacing as an empty
    /// domain at the optimizer.
    // frob:doc docs/modules/regolith-diag.md#code
    pub const SELECT_EMPTY_CANDIDATE_LIST: DiagCode = DiagCode::new(Family::Parse, 7);
    /// `E0201` -- a flownet subnet with no pressure imposer (reference,
    /// regulator, pump curve, or `Imposer`): the network is singular by
    /// construction and is rejected at COMPILE time, never at solve time
    /// (fluorite/02 sec. 4, the AD-23 fluid discipline).
    // frob:doc docs/modules/regolith-diag.md#code
    pub const IMPOSER_FREE_SUBNET: DiagCode = DiagCode::new(Family::FluidNet, 1);
    /// `E0202` -- a declared flownet node that no edge joins and that is
    /// not the reference (an unjoined terminal in the fluorite terminal
    /// ledger, fluorite/02 sec. 4): a dangling node cannot participate in
    /// the solved network.
    // frob:doc docs/modules/regolith-diag.md#code
    pub const UNJOINED_TERMINAL: DiagCode = DiagCode::new(Family::FluidNet, 2);
    /// `E0203` -- a transient/volume-budget claim (`fluids.volume_consumed`,
    /// `peak(...)`) names an edge with neither a compliance record nor an
    /// extractable wall (fluorite/03 sec. 1): the claim would be
    /// undischargeable, so lowering rejects it at compile time rather
    /// than leaving it to fail at solve time. WO-32 deliverable 5.
    // frob:doc docs/modules/regolith-diag.md#code
    pub const TRANSIENT_NO_COMPLIANCE: DiagCode = DiagCode::new(Family::FluidNet, 3);
    /// `E0204` -- a circulation net declares no `edges:` and no
    /// `reference:` (calcite/03 sec. 3, the circulation discipline's
    /// whole-net imposer-free-subnet analog; WO-47 deliverable 4). The
    /// per-space unjoined-terminal half of the sec. 3 ledger needs a
    /// connectivity extraction this front-end layer does not have (see
    /// `regolith_lower::calcite`'s module doc comment).
    // frob:doc docs/modules/regolith-diag.md#code
    pub const SPACE_NOT_IN_CIRCULATION: DiagCode = DiagCode::new(Family::FluidNet, 4);
    /// `E0205` -- a space cannot reach a reference (exit) through
    /// circulation edges (calcite/03 sec. 3, reference reachability).
    /// NOT YET DECIDABLE at this front-end layer without a new
    /// reachability traversal beyond the existing imposer-counting
    /// `net_core` (WO-47 close-out cut; see the crate's `calcite`
    /// module doc comment for the escalation).
    // frob:doc docs/modules/regolith-diag.md#code
    pub const CIRCULATION_UNREACHABLE: DiagCode = DiagCode::new(Family::FluidNet, 5);
    /// `E0206` -- an egress edge on a required path with zero/undeclared
    /// width or `path_length` (calcite/03 sec. 3).
    // frob:doc docs/modules/regolith-diag.md#code
    pub const EGRESS_EDGE_UNDECLARED: DiagCode = DiagCode::new(Family::FluidNet, 6);
    /// `E0207` -- a member cannot reach a support through transfer edges
    /// (calcite/03 sec. 3, the load-LEAK check). Same reachability cut
    /// as `E0205` -- see `CIRCULATION_UNREACHABLE`'s doc comment.
    // frob:doc docs/modules/regolith-diag.md#code
    pub const MEMBER_UNSUPPORTED: DiagCode = DiagCode::new(Family::FluidNet, 7);
    /// `E0208` -- a structure subnet has no `support:` node (calcite/03
    /// sec. 3, the load-path discipline's imposer-counting analog; WO-47
    /// deliverable 4).
    // frob:doc docs/modules/regolith-diag.md#code
    pub const STRUCTURE_NO_SUPPORT: DiagCode = DiagCode::new(Family::FluidNet, 8);
    /// `E0209` -- a member end/bearing terminal is unjoined and not
    /// `unloaded`, or declared tributary shares fail to partition their
    /// loaded surface (calcite/03 sec. 3; two conditions share one code
    /// per the spec's own allocation).
    // frob:doc docs/modules/regolith-diag.md#code
    pub const MEMBER_UNJOINED_OR_TRIBUTARY_MISMATCH: DiagCode = DiagCode::new(Family::FluidNet, 9);
    /// `E0210` -- FOPEN-1 (fluorite/04, WO-49): a flownet edge resolves,
    /// through its `from=<part>.<role>` ref, to a component with a
    /// declared `impl FluidPort<medium=...>` binding whose medium
    /// disagrees with the flownet's own `medium=` header -- a mixed-
    /// medium subnet, rejected at compile time before payload
    /// construction (fluorite/02 sec. 1, the one-medium-per-subnet
    /// rule). Names both media and both declaration sites. (Landed as
    /// E0204 on the WO-49 branch; renumbered at integration -- the
    /// ratified calcite spec owns E0204-E0209.)
    // frob:doc docs/modules/regolith-diag.md#code
    pub const MEDIUM_MISMATCH: DiagCode = DiagCode::new(Family::FluidNet, 10);
    /// `E0211` -- WO-85/D194: a concentrated (force/moment-unit) load
    /// row targets a bare MEMBER with no `@<station>` refinement (the
    /// location is ambiguous: name a station, `G1@0.5`, or target a
    /// joint/support instead -- never inferred), or its declared
    /// station is malformed / outside the normalized `[0, 1]` range.
    /// Constructive: the message names both valid spellings.
    // frob:doc docs/modules/regolith-diag.md#code
    pub const POINT_LOAD_NEEDS_STATION: DiagCode = DiagCode::new(Family::FluidNet, 11);
    /// `E0212` -- WO-132 (charter 43 sec. 1 rule 1, D248/AD-42): an
    /// energized power subnet has no source imposer (utility `service`
    /// or `generator`) -- an unsourced load is a diagnostic, never an
    /// assumption. The power discipline's imposer-free-subnet analog of
    /// `E0201`/`E0204`/`E0208`.
    // frob:doc docs/modules/regolith-diag.md#code
    // frob:ticket T-0007
    pub const POWER_SUBNET_UNSOURCED: DiagCode = DiagCode::new(Family::FluidNet, 12);
    /// `E0213` -- WO-132 (charter 43 sec. 1 rule 2): a bus is reachable
    /// from more than one source through the declared `feeders:` edges
    /// and is not named in the net's `ties:` field -- an undeclared
    /// parallel source path (accidental parallelism destroys equipment).
    // frob:doc docs/modules/regolith-diag.md#code
    // frob:ticket T-0007
    pub const POWER_UNDECLARED_PARALLEL_PATH: DiagCode = DiagCode::new(Family::FluidNet, 13);
    /// `E0214` -- WO-132 (charter 43 sec. 1 rule 3): a `feeders:` edge
    /// whose apparatus constructor narrows ampacity (`transformer`,
    /// `feeder`, `busway`) declares no adjoining protective device
    /// (`breaker`/`fuse`/`relay`) -- an unprotected ampacity transition.
    // frob:doc docs/modules/regolith-diag.md#code
    // frob:ticket T-0007
    pub const POWER_UNPROTECTED_TRANSITION: DiagCode = DiagCode::new(Family::FluidNet, 14);
    /// `E0215` -- WO-132 (charter 43 sec. 1 rule 4): a declared `loads:`
    /// entry cannot reach any source bus by walking the net's declared
    /// `feeders:` edges -- the power discipline's reachability check,
    /// the same shape as calcite's `E0207`/`E0205`.
    // frob:doc docs/modules/regolith-diag.md#code
    // frob:ticket T-0007
    pub const POWER_LOAD_UNREACHABLE: DiagCode = DiagCode::new(Family::FluidNet, 15);
    /// `E0216` -- WO-133 deliverable 6 (D255, the cross-standard
    /// guard): a power branch's apparatus record declares a
    /// `standard_family` (IEC/NEC/ANSI-NEMA) that disagrees with
    /// another apparatus/conductor record in the SAME subnet. Mixing
    /// standard families is not forbidden (real plants mix) -- mixing
    /// SILENTLY is; this names both families, both records, and the
    /// claim at stake so the author either declares the crossing
    /// deliberately (`assume!` with a basis) or fixes it. Never a
    /// conversion table (D250 forbids translating one family's rating
    /// into another's assumption).
    // frob:doc docs/modules/regolith-diag.md#code
    // frob:ticket T-0008
    pub const POWER_CROSS_STANDARD_MIX: DiagCode = DiagCode::new(Family::FluidNet, 16);
    /// `E0217` -- WO-133 deliverable 2 (coordinator adjudication
    /// F-WO133-1, D250.3 exactly): a `PowerNetPayload` REQUIRED field
    /// (`Bus.nominal_voltage`, `Bus.phases`, `Load.connected_kva`) has
    /// no declared source reaching it -- neither a per-item `buses:`/
    /// `loads:` property (`mainbus(nominal_voltage=480V, phases=3)`)
    /// nor an unambiguous propagated apparatus value (a source's
    /// declared voltage, a transformer's declared secondary, ...).
    /// Refused, never fabricated: payload emission for the whole net
    /// stops rather than filling the field with a guessed value.
    // frob:doc docs/modules/regolith-diag.md#code
    // frob:ticket T-0008
    pub const POWER_PAYLOAD_FIELD_UNRESOLVED: DiagCode = DiagCode::new(Family::FluidNet, 17);
    /// `E0301` -- an entity query matched more than one entity.
    // frob:doc docs/modules/regolith-diag.md#code
    pub const AMBIGUOUS_SELECTION: DiagCode = DiagCode::new(Family::References, 1);
    /// `E0302` -- conflicting borrow of an owned region.
    // frob:doc docs/modules/regolith-diag.md#code
    pub const BORROW_CONFLICT: DiagCode = DiagCode::new(Family::References, 2);
    /// `E0303` -- WO-33 D98: a claim projection (`max`/`min`/`at`/
    /// `slope`) names a field no `compute` claim in scope declares (the
    /// unresolved-reference family, mirroring `E0301`).
    // frob:doc docs/modules/regolith-diag.md#code
    pub const UNRESOLVED_FIELD_REFERENCE: DiagCode = DiagCode::new(Family::References, 3);
    /// `E0304` -- a change that alters an entity's structure class.
    // frob:doc docs/modules/regolith-diag.md#code
    pub const STRUCTURE_CLASS_CHANGE: DiagCode = DiagCode::new(Family::References, 4);
    /// `E0305` -- WO-33 D98: a `compute` claim's `over` clause
    /// (directly or transitively) references itself as a given,
    /// forming a cycle in the computed-field promise DAG. Names the
    /// full chain.
    // frob:doc docs/modules/regolith-diag.md#code
    pub const COMPUTE_FIELD_CYCLE: DiagCode = DiagCode::new(Family::References, 5);
    /// `E0306` -- WO-34 deliverable 2 (D99): a `harness:` run's `from`/
    /// `to` endpoints resolve to two different nets with no inline
    /// component between them. Names both nets.
    // frob:doc docs/modules/regolith-diag.md#code
    pub const RUN_CROSS_NET: DiagCode = DiagCode::new(Family::References, 6);
    /// `E0307` -- WO-34 deliverable 2: a `harness:` run's `from`/`to`
    /// header text does not spell a non-empty endpoint on one (or
    /// both) sides after the `from`/`to` keyword -- a dangling
    /// endpoint elaboration cannot resolve. Distinct from the D1
    /// parse-time `E0106` (which only checks the keywords are
    /// present): this fires when a keyword is present but names no
    /// endpoint text.
    // frob:doc docs/modules/regolith-diag.md#code
    pub const RUN_DANGLING_ENDPOINT: DiagCode = DiagCode::new(Family::References, 7);
    /// `E0308` -- WO-34 deliverable 2: a `harness:` run's `bundle`
    /// clause is present but names no group text (an empty/malformed
    /// `bundle` line) -- the co-routing group is unknown.
    // frob:doc docs/modules/regolith-diag.md#code
    pub const RUN_UNKNOWN_BUNDLE: DiagCode = DiagCode::new(Family::References, 8);
    /// `E0309` -- WO-34 deliverable 2: a `harness:` run's `along`
    /// structural ref failed extraction through the shared WO-32 seam
    /// (no realized record, an empty path, or an unknown roughness
    /// class -- see `regolith_lower::extract::ExtractError`).
    // frob:doc docs/modules/regolith-diag.md#code
    pub const RUN_EXTRACT_FAILED: DiagCode = DiagCode::new(Family::References, 9);
    /// `E0407` -- an enclosing system's boundary envelope is not
    /// contained in an imported/child artifact's proven boundary
    /// (boundary subsumption, INV-7).
    // frob:doc docs/modules/regolith-diag.md#code
    pub const BOUNDARY_NOT_SUBSUMED: DiagCode = DiagCode::new(Family::Contracts, 7);
    /// `E0410` -- a demanded capability exceeds the supplied one.
    // frob:doc docs/modules/regolith-diag.md#code
    pub const CAPABILITY_VS_DEMAND: DiagCode = DiagCode::new(Family::Contracts, 10);
    /// `E0420` -- a ledger imbalance (DOF / driver / domain-crossing).
    // frob:doc docs/modules/regolith-diag.md#code
    pub const LEDGER_IMBALANCE: DiagCode = DiagCode::new(Family::Contracts, 20);
    /// `E0432` -- a budget cannot close at its worst-case corner.
    // frob:doc docs/modules/regolith-diag.md#code
    pub const BUDGET_CANNOT_CLOSE: DiagCode = DiagCode::new(Family::Contracts, 32);
    /// `E0433` -- a compute intent is realized by other than exactly one
    /// workload (zero or two-or-more), naming both sides (cuprite/05 sec.
    /// 1 rule 1, EOPEN-15's realization ledger).
    // frob:doc docs/modules/regolith-diag.md#code
    pub const REALIZATION_NOT_EXACTLY_ONE: DiagCode = DiagCode::new(Family::Contracts, 33);
    /// `E0434` -- an interface-side promised bound field has no
    /// same-name field on the impl side (or vice versa): conformance
    /// windows match by field NAME (WO-26 D104), so a name present on
    /// only one side is a constructive diagnostic naming both.
    // frob:doc docs/modules/regolith-diag.md#code
    pub const PROMISED_BOUND_UNMATCHED: DiagCode = DiagCode::new(Family::Contracts, 34);
    /// `E0435` -- a temporal REDUCTION claim form (`peak`/`rms`/
    /// `overshoot`) was recognized but carries no trailing external
    /// comparator (WO-26 D102): a reduction yields a scalar and always
    /// needs one, so a missing comparator is rejected at compile time
    /// rather than silently deferred.
    // frob:doc docs/modules/regolith-diag.md#code
    pub const TEMPORAL_REDUCTION_MISSING_COMPARATOR: DiagCode =
        DiagCode::new(Family::Contracts, 35);
    /// `E0436` -- a temporal CONTAINMENT claim form (`settles`/
    /// `stays_within`) was recognized but carries a trailing external
    /// comparator (WO-26 D102): a containment's own parameters (`to=`
    /// tolerance, `mask=` reference) ARE the acceptance, so a trailing
    /// comparator is a shape error, not an extra check.
    // frob:doc docs/modules/regolith-diag.md#code
    pub const TEMPORAL_CONTAINMENT_UNEXPECTED_COMPARATOR: DiagCode =
        DiagCode::new(Family::Contracts, 36);
    /// `E0437` -- a general comparison claim line carries MORE than one
    /// top-level comparator (WO-26 D103: exactly ONE per claim line --
    /// each side is an ordinary quantity expression; chained or
    /// double-bounded comparisons have no defined lowering).
    // frob:doc docs/modules/regolith-diag.md#code
    pub const GENERAL_COMPARISON_MULTIPLE_COMPARATORS: DiagCode =
        DiagCode::new(Family::Contracts, 37);
    /// `E0438` -- an `mfg.cost(...)` claim's argument list is malformed
    /// (WO-54, toolchain/27 sec. 1.1): the accepted shape is
    /// `mfg.cost(<subject>[, profile=<name>])` -- a missing/empty
    /// subject, a duplicate or empty `profile=`, an unknown keyword,
    /// or a stray positional argument is rejected at compile time with
    /// the offending argument named, never silently deferred.
    // frob:doc docs/modules/regolith-diag.md#code
    pub const COST_CLAIM_MALFORMED: DiagCode = DiagCode::new(Family::Contracts, 38);
    /// `E0440` -- a numeric L2 solve (rigid statics, stiffness network)
    /// hit a singular or rank-deficient system: an under-determined
    /// support set, a disconnected stiffness network, or an
    /// ill-conditioned assembly (WO-23). Always a diagnostic, never a
    /// panic and never a NaN/non-finite value escaping the solve.
    // frob:doc docs/modules/regolith-diag.md#code
    pub const SINGULAR_SYSTEM: DiagCode = DiagCode::new(Family::Contracts, 40);
    /// `E0441` -- an exactly-constrained sketch (WO-11's conservative
    /// DOF ledger reports residual zero) whose numeric residual closure
    /// does not converge to zero: the declared constraints are
    /// mutually inconsistent, not merely under/over-counted (WO-23,
    /// hematite/07 OPEN-5/D65).
    // frob:doc docs/modules/regolith-diag.md#code
    pub const SKETCH_RESIDUAL_INCONSISTENT: DiagCode = DiagCode::new(Family::Contracts, 41);
    /// `E0442` -- a profile `constraints:` item references a segment
    /// name that no walk-step label binds (D150: segment names are
    /// syntax, `a: line right`; a comment is not a binding). The
    /// diagnostic is constructive: it names the walk's steps and the
    /// label spelling.
    // frob:doc docs/modules/regolith-diag.md#code
    pub const UNBOUND_SEGMENT_LABEL: DiagCode = DiagCode::new(Family::Contracts, 42);
    /// `E0443` -- a `then:` feature op has no projection into the v1
    /// `FeatureProgram` op set (WO-51 d2): the part's program is
    /// emitted without it and this NAMED warning records the gap --
    /// never silent truncation.
    // frob:doc docs/modules/regolith-diag.md#code
    pub const UNSUPPORTED_FEATURE_OP: DiagCode = DiagCode::new(Family::Contracts, 43);
    /// `E0444` -- a `.cavity(inlet=..., outlet=...)` query names a
    /// port whose feature binding no `then:` op in the part declares
    /// (D152 misuse; constructive: lists the part's op bindings).
    // frob:doc docs/modules/regolith-diag.md#code
    pub const CAVITY_PORT_UNRESOLVED: DiagCode = DiagCode::new(Family::Contracts, 44);
    /// `E0445` -- a cavity's inlet->outlet feature-op chain contains
    /// an op the v1 feature-op set cannot express, so no wetted path
    /// can be derived (hematite/07 sec. 2a's named escalation
    /// diagnostic -- the syntax-gap criterion, not a reopen).
    // frob:doc docs/modules/regolith-diag.md#code
    pub const CAVITY_CHAIN_INEXPRESSIBLE: DiagCode = DiagCode::new(Family::Contracts, 45);
    /// `E0446` -- a `by select(...)` (WO-56, D161) candidate list
    /// names the same impl-ref twice. Constructive: the check names
    /// the repeated candidate and its subject, since a duplicate
    /// candidate can never change a search's outcome and is always a
    /// authoring mistake (a copy/paste or a stale edit), never a
    /// legal "weight" on one alternative to preserve.
    // frob:doc docs/modules/regolith-diag.md#code
    pub const SELECT_DUPLICATE_CANDIDATE: DiagCode = DiagCode::new(Family::Contracts, 46);
    /// `E0447` -- a walk with a labeled `close` edge (an unconstrained
    /// 2-DOF vector, WO-62 D171/AD-32) still carries an explicit `free`
    /// segment length: closure gives the close edge both equations, so
    /// there is nothing left to determine the other free length --
    /// under-constrained, naming the residual segment and the missing
    /// constraint class (assert its length or remove the `close`
    /// label). The over-constrained sibling is `E0441`.
    // frob:doc docs/modules/regolith-diag.md#code
    pub const SKETCH_CLOSE_EDGE_UNDERCONSTRAINED: DiagCode = DiagCode::new(Family::Contracts, 47);
    /// `E0448` -- a sheet-metal `Blank(...)` op has no thickness value
    /// source: no explicit `thickness=` arg AND no enclosing
    /// `process=<proc>(sheet=<t>)` gauge source (WO-62 D171/AD-32,
    /// INV-21's `cause: process(<proc>.sheet)` API). A gauge-less
    /// unasserted sheet part is a compile diagnostic, never a silently
    /// unthickened blank.
    // frob:doc docs/modules/regolith-diag.md#code
    pub const SHEET_BLANK_NO_GAUGE_SOURCE: DiagCode = DiagCode::new(Family::Contracts, 48);
    /// `E0449` -- a `plan: extern(<ref>, <dialect>)` field (WO-69,
    /// regolith/08 sec. 4's L6 row) is malformed: the extern ref string
    /// is missing, OR the dialect is not a registered `fmt.gcode_*`
    /// name (`gcode_fanuc`/`gcode_marlin`). No `cam.*` obligations are
    /// emitted for a malformed clause (honest silence, never a guess);
    /// this diagnostic is the only signal.
    // frob:doc docs/modules/regolith-diag.md#code
    pub const PLAN_CLAUSE_MALFORMED: DiagCode = DiagCode::new(Family::Contracts, 49);
    /// `E0450` -- a `forall <var> in <domain>:` sweep names a BARE PLURAL
    /// (`boards`, `assemblies`) that resolves to no declared domain, so
    /// the sweep silently covers zero points -- a vacuous pass, the
    /// honesty gap WO-90 closes. A declared domain (`[lo, hi]` interval,
    /// `{a, b}` discrete set, `registry(<family>)`, `<Entity>.members.all`,
    /// or a dotted pack ref) is legal; an explicitly EMPTY declared
    /// domain stays legal (empty sweep = zero obligations, honestly). Only
    /// the undeclared bare-plural name trips this diagnostic.
    // frob:doc docs/modules/regolith-diag.md#code
    pub const FORALL_DOMAIN_UNDECLARED: DiagCode = DiagCode::new(Family::Contracts, 50);
    /// `E0451` -- a material-removal family constructor (`Ribs`,
    /// `PocketGrid`, `Shell`, `Lattice` -- charter 34 phase 1, D200/
    /// WO-77) spells malformed parameters: a missing required slot, an
    /// unknown/duplicate slot, a wrong-dimension value (an int slot
    /// given a length, a length slot given a bare number), a `density`
    /// outside `[0, 1]`, or an unknown lattice `cell` name. Constructive:
    /// the diagnostic names the family's full signature and the exact
    /// offending slot; the op is omitted from the emitted feature
    /// program (never a guessed value, never silent truncation).
    // frob:doc docs/modules/regolith-diag.md#code
    pub const REMOVAL_FAMILY_MALFORMED: DiagCode = DiagCode::new(Family::Contracts, 51);
    /// `E0452` -- an `elec.impedance(...) within [lo, hi]` claim
    /// (WO-78, charter 35 sec. 1.2) names no net: the call's first
    /// argument is empty or keyword-only, so there is nothing to
    /// attribute the impedance window to. Constructive: the message
    /// names the accepted shape (`elec.impedance(<net>[, role=...,
    /// stackup=..., layer=..., w=...]) within [lo, hi]`); the claim is
    /// not lowered (never a guessed subject).
    // frob:doc docs/modules/regolith-diag.md#code
    pub const SI_IMPEDANCE_MALFORMED: DiagCode = DiagCode::new(Family::Contracts, 52);
    /// `E0501` -- positional index used where a domain is required.
    // frob:doc docs/modules/regolith-diag.md#code
    pub const INDEX_VS_DOMAIN: DiagCode = DiagCode::new(Family::Instances, 1);
    /// `E0502` -- `any` over a broken (non-uniform) orbit.
    // frob:doc docs/modules/regolith-diag.md#code
    pub const BROKEN_ORBIT_ANY: DiagCode = DiagCode::new(Family::Instances, 2);
    /// `E0503` -- a generic declaration is never instantiated (a dead
    /// generic: a monomorphization point-set with no points, INV-11).
    // frob:doc docs/modules/regolith-diag.md#code
    pub const DEAD_GENERIC: DiagCode = DiagCode::new(Family::Instances, 3);
    /// `E0504` -- a use-site generic instantiation supplies the wrong
    /// number of arguments for its declaration, so no static check can
    /// run at that point (an un-expandable instantiation, INV-11).
    // frob:doc docs/modules/regolith-diag.md#code
    pub const GENERIC_ARITY_MISMATCH: DiagCode = DiagCode::new(Family::Instances, 4);
    /// `E0601` -- a rule pack's static rule evaluated `false` against a
    /// matched entity (`pack.rule` provenance, `why:` rendered).
    // frob:doc docs/modules/regolith-diag.md#code
    pub const RULE_VIOLATION: DiagCode = DiagCode::new(Family::RulePacks, 1);
    /// `E0602` -- two attached rule packs declare a rule of the same
    /// qualified name (`pack.rule`): union composition with no priority
    /// arithmetic means a collision is an error, never silent shadowing
    /// (design doc D-C).
    // frob:doc docs/modules/regolith-diag.md#code
    pub const RULE_NAME_COLLISION: DiagCode = DiagCode::new(Family::RulePacks, 2);
    /// `E0603` -- a rule's predicate references a fact no layer (static
    /// entity DB, WO-22/24 realized-fact extraction) provides: a compile
    /// error on the rule itself (design doc D-E), not a deferral.
    // frob:doc docs/modules/regolith-diag.md#code
    pub const RULE_FACT_UNPROVIDED: DiagCode = DiagCode::new(Family::RulePacks, 3);
    /// `E0604` -- a `resolves:` clause names a field that is never
    /// `free` at any use site in the corpus (a stale resolver, mirror of
    /// `E0701`).
    // frob:doc docs/modules/regolith-diag.md#code
    pub const RULE_STALE_RESOLVER: DiagCode = DiagCode::new(Family::RulePacks, 4);
    /// `E0701` -- a declared waiver matched no claim or rule (stale).
    // frob:doc docs/modules/regolith-diag.md#code
    pub const STALE_WAIVER: DiagCode = DiagCode::new(Family::Evidence, 1);
    /// `E0702` -- a waiver carries no mandatory `basis:` (regolith/12
    /// rule 2): an unjustified concession, rejected as an INV-2 ladder
    /// overreach rather than accepted.
    // frob:doc docs/modules/regolith-diag.md#code
    pub const WAIVER_MISSING_BASIS: DiagCode = DiagCode::new(Family::Evidence, 2);
    /// `L0801` -- WO-40: an `import` line whose bound name is never
    /// referenced anywhere else in the same file (a dead import).
    // frob:doc docs/modules/regolith-diag.md#code
    pub const UNUSED_IMPORT: DiagCode = DiagCode::new(Family::Lint, 1);
    /// `L0802` -- WO-40: source text spells a retired project name
    /// (`mill`, `loom`, `dcad`, `deda`, `quarry`, `lodestone`, or the
    /// dead `.calc` extension spelling) as an identifier/word token --
    /// the "dead names are DEAD" CLAUDE.md rule, made mechanically
    /// checkable (design-log verbatim history and negative-fixture
    /// filenames are exempt, see `lints::retired_vocabulary`).
    // frob:doc docs/modules/regolith-diag.md#code
    pub const RETIRED_VOCABULARY_USAGE: DiagCode = DiagCode::new(Family::Lint, 2);
    /// `L0803` -- WO-40: one advisory per file summarizing its `todo!`/
    /// `assume!` count + locations (the honest-deferral surface; not a
    /// nag per line).
    // frob:doc docs/modules/regolith-diag.md#code
    pub const TODO_ASSUME_INVENTORY: DiagCode = DiagCode::new(Family::Lint, 3);
    /// `E0703` -- WO-40/D117: a `waive` block's target spells a lint
    /// code (`Lxxxx`, case-insensitive) instead of a `Group.claim`/rule
    /// reference. Deliberately in `Family::Evidence`, NOT `Family::Lint`
    /// (`apply_lint_config` only ever touches the `Lint` family): the
    /// waive ladder cannot silence its own audit, so this rejection can
    /// never itself be configured away by `[lints]`.
    // frob:doc docs/modules/regolith-diag.md#code
    pub const WAIVE_NAMES_LINT_CODE: DiagCode = DiagCode::new(Family::Evidence, 3);

    /// `E0901` -- WO-131/D247.2: a shipped gerber/fab-package set is
    /// missing a required charter 41 sec. 3 layer. BACKFILLED from the
    /// bare Python string `fab_set_incomplete`
    /// (`regolith.backends.elec_fabset`, WO-124) -- no grandfathering
    /// (D247.2).
    // frob:doc docs/modules/regolith-diag.md#code
    pub const FAB_SET_INCOMPLETE: DiagCode = DiagCode::new(Family::Emission, 1);
    /// `E0902` -- WO-131/D247.2: a drafting audit rule failed on a
    /// gating sheet (`regolith.backends.drawings.audit`, WO-123).
    /// BACKFILLED from the bare Python string `drafting_audit_refused`
    /// -- no grandfathering (D247.2).
    // frob:doc docs/modules/regolith-diag.md#code
    pub const DRAFTING_AUDIT_REFUSED: DiagCode = DiagCode::new(Family::Emission, 2);
    /// `E0903` -- WO-131/D247.2: a shipped package's artifact index
    /// (the manifest's file list) drifts from what the package
    /// actually wrote. RESERVED: named in D247.2 as one of the three
    /// E09xx meanings, but no current producer raises it (the sweep
    /// this WO ran found no live artifact-index-drift check to
    /// backfill) -- registered here so a future producer does not
    /// have to open a second home. See WO-131 close-out escalation
    /// F-WO131-1.
    // frob:doc docs/modules/regolith-diag.md#code
    pub const ARTIFACT_INDEX_DRIFT: DiagCode = DiagCode::new(Family::Emission, 3);

    /// `E1001` -- RESERVED for WO-129A (D246): an override applied
    /// through the D243 injection channel with no author/reason
    /// attached (an unexplained override). Not raised by this WO;
    /// registered per the WO-131 deliverable 3 instruction so WO-129A
    /// can raise it without a second registry.
    // frob:doc docs/modules/regolith-diag.md#code
    pub const UNEXPLAINED_OVERRIDE: DiagCode = DiagCode::new(Family::Injection, 1);
    /// `E1002` -- RESERVED for WO-129A (D246): an override targets a
    /// SOURCE-only claim (the D246 claims/evidence boundary) rather
    /// than an evidence-backed one. Not raised by this WO.
    // frob:doc docs/modules/regolith-diag.md#code
    pub const SOURCE_ONLY_TARGET_REFUSED: DiagCode = DiagCode::new(Family::Injection, 2);
    /// `E1003` -- RESERVED for WO-129A (D246): an override names a
    /// target that cannot be resolved anywhere in the build. Not
    /// raised by this WO.
    // frob:doc docs/modules/regolith-diag.md#code
    pub const UNRESOLVABLE_OVERRIDE_TARGET: DiagCode = DiagCode::new(Family::Injection, 3);

    /// `E1101` -- WO-131/D247.2: an `expected_signals.json` carries a
    /// provenance ref that does not resolve inside the package, or a
    /// populated expected value with no units (D224). BACKFILLED from
    /// the bare Python string `expectation_provenance_unresolved`
    /// (`regolith.backends.harness_pack`, WO-126) -- no grandfathering
    /// (D247.2).
    // frob:doc docs/modules/regolith-diag.md#code
    pub const EXPECTATION_PROVENANCE_UNRESOLVED: DiagCode = DiagCode::new(Family::BringUp, 1);
    /// `E1102` -- WO-131/D247.1 (D237.1): a debug-profile ship
    /// manifest is refused as release-gate evidence.
    /// BACKFILLED from the bare Python string
    /// `debug_not_release_evidence` (`regolith.backends.manifest`,
    /// function `release_gate_refuses_debug_evidence`, WO-125) -- no
    /// grandfathering (D247.2).
    // frob:doc docs/modules/regolith-diag.md#code
    pub const RELEASE_GATE_REFUSES_DEBUG_EVIDENCE: DiagCode = DiagCode::new(Family::BringUp, 2);
    /// `E1103` -- WO-131/D247.2: a debug tap map disagrees with the
    /// artifact it claims to describe. BACKFILLED from the bare
    /// Python string `tap_map_artifact_mismatch`
    /// (`regolith.backends.debug_taps`) -- no grandfathering (D247.2).
    // frob:doc docs/modules/regolith-diag.md#code
    pub const TAP_MAP_DISAGREEMENT: DiagCode = DiagCode::new(Family::BringUp, 3);

    /// Every registered code paired with its Rust symbol name, for the
    /// completeness sweep (D247.4) and for the generated Python
    /// constants (the `make codes` single-sourcing precedent, WO-131
    /// deliverable 2). A code minted here and left out of this slice
    /// is a build error (see `regolith_diag::explain`'s completeness
    /// test) -- this is what makes D247.4's rule able to FAIL.
    // frob:doc docs/modules/regolith-diag.md#code
    // frob:ticket T-0008
    pub const ALL: &[(&str, DiagCode)] = &[
        ("INCOMPATIBLE_QUANTITIES", INCOMPATIBLE_QUANTITIES),
        ("EQUALITY_ON_CONTINUOUS", EQUALITY_ON_CONTINUOUS),
        ("INTERVAL_RANGE_CONFUSION", INTERVAL_RANGE_CONFUSION),
        ("ILLEGAL_LOG_SUM", ILLEGAL_LOG_SUM),
        ("COMBINATIONAL_CYCLE", COMBINATIONAL_CYCLE),
        ("RUN_MISSING_ENDPOINT", RUN_MISSING_ENDPOINT),
        ("SELECT_EMPTY_CANDIDATE_LIST", SELECT_EMPTY_CANDIDATE_LIST),
        ("IMPOSER_FREE_SUBNET", IMPOSER_FREE_SUBNET),
        ("UNJOINED_TERMINAL", UNJOINED_TERMINAL),
        ("TRANSIENT_NO_COMPLIANCE", TRANSIENT_NO_COMPLIANCE),
        ("SPACE_NOT_IN_CIRCULATION", SPACE_NOT_IN_CIRCULATION),
        ("CIRCULATION_UNREACHABLE", CIRCULATION_UNREACHABLE),
        ("EGRESS_EDGE_UNDECLARED", EGRESS_EDGE_UNDECLARED),
        ("MEMBER_UNSUPPORTED", MEMBER_UNSUPPORTED),
        ("STRUCTURE_NO_SUPPORT", STRUCTURE_NO_SUPPORT),
        (
            "MEMBER_UNJOINED_OR_TRIBUTARY_MISMATCH",
            MEMBER_UNJOINED_OR_TRIBUTARY_MISMATCH,
        ),
        ("MEDIUM_MISMATCH", MEDIUM_MISMATCH),
        ("POINT_LOAD_NEEDS_STATION", POINT_LOAD_NEEDS_STATION),
        ("POWER_SUBNET_UNSOURCED", POWER_SUBNET_UNSOURCED),
        (
            "POWER_UNDECLARED_PARALLEL_PATH",
            POWER_UNDECLARED_PARALLEL_PATH,
        ),
        ("POWER_UNPROTECTED_TRANSITION", POWER_UNPROTECTED_TRANSITION),
        ("POWER_LOAD_UNREACHABLE", POWER_LOAD_UNREACHABLE),
        ("POWER_CROSS_STANDARD_MIX", POWER_CROSS_STANDARD_MIX),
        (
            "POWER_PAYLOAD_FIELD_UNRESOLVED",
            POWER_PAYLOAD_FIELD_UNRESOLVED,
        ),
        ("AMBIGUOUS_SELECTION", AMBIGUOUS_SELECTION),
        ("BORROW_CONFLICT", BORROW_CONFLICT),
        ("UNRESOLVED_FIELD_REFERENCE", UNRESOLVED_FIELD_REFERENCE),
        ("STRUCTURE_CLASS_CHANGE", STRUCTURE_CLASS_CHANGE),
        ("COMPUTE_FIELD_CYCLE", COMPUTE_FIELD_CYCLE),
        ("RUN_CROSS_NET", RUN_CROSS_NET),
        ("RUN_DANGLING_ENDPOINT", RUN_DANGLING_ENDPOINT),
        ("RUN_UNKNOWN_BUNDLE", RUN_UNKNOWN_BUNDLE),
        ("RUN_EXTRACT_FAILED", RUN_EXTRACT_FAILED),
        ("BOUNDARY_NOT_SUBSUMED", BOUNDARY_NOT_SUBSUMED),
        ("CAPABILITY_VS_DEMAND", CAPABILITY_VS_DEMAND),
        ("LEDGER_IMBALANCE", LEDGER_IMBALANCE),
        ("BUDGET_CANNOT_CLOSE", BUDGET_CANNOT_CLOSE),
        ("REALIZATION_NOT_EXACTLY_ONE", REALIZATION_NOT_EXACTLY_ONE),
        ("PROMISED_BOUND_UNMATCHED", PROMISED_BOUND_UNMATCHED),
        (
            "TEMPORAL_REDUCTION_MISSING_COMPARATOR",
            TEMPORAL_REDUCTION_MISSING_COMPARATOR,
        ),
        (
            "TEMPORAL_CONTAINMENT_UNEXPECTED_COMPARATOR",
            TEMPORAL_CONTAINMENT_UNEXPECTED_COMPARATOR,
        ),
        (
            "GENERAL_COMPARISON_MULTIPLE_COMPARATORS",
            GENERAL_COMPARISON_MULTIPLE_COMPARATORS,
        ),
        ("COST_CLAIM_MALFORMED", COST_CLAIM_MALFORMED),
        ("SINGULAR_SYSTEM", SINGULAR_SYSTEM),
        ("SKETCH_RESIDUAL_INCONSISTENT", SKETCH_RESIDUAL_INCONSISTENT),
        ("UNBOUND_SEGMENT_LABEL", UNBOUND_SEGMENT_LABEL),
        ("UNSUPPORTED_FEATURE_OP", UNSUPPORTED_FEATURE_OP),
        ("CAVITY_PORT_UNRESOLVED", CAVITY_PORT_UNRESOLVED),
        ("CAVITY_CHAIN_INEXPRESSIBLE", CAVITY_CHAIN_INEXPRESSIBLE),
        ("SELECT_DUPLICATE_CANDIDATE", SELECT_DUPLICATE_CANDIDATE),
        (
            "SKETCH_CLOSE_EDGE_UNDERCONSTRAINED",
            SKETCH_CLOSE_EDGE_UNDERCONSTRAINED,
        ),
        ("SHEET_BLANK_NO_GAUGE_SOURCE", SHEET_BLANK_NO_GAUGE_SOURCE),
        ("PLAN_CLAUSE_MALFORMED", PLAN_CLAUSE_MALFORMED),
        ("FORALL_DOMAIN_UNDECLARED", FORALL_DOMAIN_UNDECLARED),
        ("REMOVAL_FAMILY_MALFORMED", REMOVAL_FAMILY_MALFORMED),
        ("SI_IMPEDANCE_MALFORMED", SI_IMPEDANCE_MALFORMED),
        ("INDEX_VS_DOMAIN", INDEX_VS_DOMAIN),
        ("BROKEN_ORBIT_ANY", BROKEN_ORBIT_ANY),
        ("DEAD_GENERIC", DEAD_GENERIC),
        ("GENERIC_ARITY_MISMATCH", GENERIC_ARITY_MISMATCH),
        ("RULE_VIOLATION", RULE_VIOLATION),
        ("RULE_NAME_COLLISION", RULE_NAME_COLLISION),
        ("RULE_FACT_UNPROVIDED", RULE_FACT_UNPROVIDED),
        ("RULE_STALE_RESOLVER", RULE_STALE_RESOLVER),
        ("STALE_WAIVER", STALE_WAIVER),
        ("WAIVER_MISSING_BASIS", WAIVER_MISSING_BASIS),
        ("UNUSED_IMPORT", UNUSED_IMPORT),
        ("RETIRED_VOCABULARY_USAGE", RETIRED_VOCABULARY_USAGE),
        ("TODO_ASSUME_INVENTORY", TODO_ASSUME_INVENTORY),
        ("WAIVE_NAMES_LINT_CODE", WAIVE_NAMES_LINT_CODE),
        ("FAB_SET_INCOMPLETE", FAB_SET_INCOMPLETE),
        ("DRAFTING_AUDIT_REFUSED", DRAFTING_AUDIT_REFUSED),
        ("ARTIFACT_INDEX_DRIFT", ARTIFACT_INDEX_DRIFT),
        ("UNEXPLAINED_OVERRIDE", UNEXPLAINED_OVERRIDE),
        ("SOURCE_ONLY_TARGET_REFUSED", SOURCE_ONLY_TARGET_REFUSED),
        ("UNRESOLVABLE_OVERRIDE_TARGET", UNRESOLVABLE_OVERRIDE_TARGET),
        (
            "EXPECTATION_PROVENANCE_UNRESOLVED",
            EXPECTATION_PROVENANCE_UNRESOLVED,
        ),
        (
            "RELEASE_GATE_REFUSES_DEBUG_EVIDENCE",
            RELEASE_GATE_REFUSES_DEBUG_EVIDENCE,
        ),
        ("TAP_MAP_DISAGREEMENT", TAP_MAP_DISAGREEMENT),
    ];
}

#[cfg(test)]
mod tests {
    use super::codes;
    use super::{DiagCode, Family};

    #[test]
    // frob:ticket T-0008
    fn code_renders_zero_padded() {
        assert_eq!(codes::AMBIGUOUS_SELECTION.to_string(), "E0301");
        assert_eq!(codes::BUDGET_CANNOT_CLOSE.to_string(), "E0432");
        assert_eq!(codes::INCOMPATIBLE_QUANTITIES.to_string(), "E0101");
        assert_eq!(codes::BROKEN_ORBIT_ANY.to_string(), "E0502");
        assert_eq!(codes::COMBINATIONAL_CYCLE.to_string(), "E0105");
        assert_eq!(codes::SELECT_EMPTY_CANDIDATE_LIST.to_string(), "E0107");
        assert_eq!(codes::SELECT_DUPLICATE_CANDIDATE.to_string(), "E0446");
        assert_eq!(
            codes::SKETCH_CLOSE_EDGE_UNDERCONSTRAINED.to_string(),
            "E0447"
        );
        assert_eq!(codes::SHEET_BLANK_NO_GAUGE_SOURCE.to_string(), "E0448");
        assert_eq!(codes::REMOVAL_FAMILY_MALFORMED.to_string(), "E0451");
        assert_eq!(codes::SI_IMPEDANCE_MALFORMED.to_string(), "E0452");
        assert_eq!(codes::IMPOSER_FREE_SUBNET.to_string(), "E0201");
        assert_eq!(codes::UNJOINED_TERMINAL.to_string(), "E0202");
        assert_eq!(codes::TRANSIENT_NO_COMPLIANCE.to_string(), "E0203");
        assert_eq!(codes::MEDIUM_MISMATCH.to_string(), "E0210");
        assert_eq!(codes::SPACE_NOT_IN_CIRCULATION.to_string(), "E0204");
        assert_eq!(codes::CIRCULATION_UNREACHABLE.to_string(), "E0205");
        assert_eq!(codes::EGRESS_EDGE_UNDECLARED.to_string(), "E0206");
        assert_eq!(codes::MEMBER_UNSUPPORTED.to_string(), "E0207");
        assert_eq!(codes::STRUCTURE_NO_SUPPORT.to_string(), "E0208");
        assert_eq!(
            codes::MEMBER_UNJOINED_OR_TRIBUTARY_MISMATCH.to_string(),
            "E0209"
        );
        assert_eq!(codes::POINT_LOAD_NEEDS_STATION.to_string(), "E0211");
        assert_eq!(codes::POWER_SUBNET_UNSOURCED.to_string(), "E0212");
        assert_eq!(codes::POWER_UNDECLARED_PARALLEL_PATH.to_string(), "E0213");
        assert_eq!(codes::POWER_UNPROTECTED_TRANSITION.to_string(), "E0214");
        assert_eq!(codes::POWER_LOAD_UNREACHABLE.to_string(), "E0215");
        assert_eq!(codes::POWER_CROSS_STANDARD_MIX.to_string(), "E0216");
        assert_eq!(codes::POWER_PAYLOAD_FIELD_UNRESOLVED.to_string(), "E0217");
    }

    #[test]
    fn family_base_maps_hundreds_digit() {
        assert_eq!(Family::FluidNet.base(), 200);
        assert_eq!(Family::Evidence.base(), 700);
        assert_eq!(DiagCode::new(Family::Evidence, 3).number(), 703);
        assert_eq!(Family::Emission.base(), 900);
        assert_eq!(Family::Injection.base(), 1000);
        assert_eq!(Family::BringUp.base(), 1100);
    }

    #[test]
    fn code_round_trips_json() {
        let json = serde_json::to_string(&codes::BORROW_CONFLICT).unwrap();
        let back: DiagCode = serde_json::from_str(&json).unwrap();
        assert_eq!(back, codes::BORROW_CONFLICT);
    }

    /// D247.2: the three WO-131 families render with the E-prefix and
    /// the expected four-digit numbers (900/1000/1100 bases).
    #[test]
    fn wo131_families_render() {
        assert_eq!(codes::FAB_SET_INCOMPLETE.to_string(), "E0901");
        assert_eq!(codes::DRAFTING_AUDIT_REFUSED.to_string(), "E0902");
        assert_eq!(codes::ARTIFACT_INDEX_DRIFT.to_string(), "E0903");
        assert_eq!(codes::UNEXPLAINED_OVERRIDE.to_string(), "E1001");
        assert_eq!(codes::SOURCE_ONLY_TARGET_REFUSED.to_string(), "E1002");
        assert_eq!(codes::UNRESOLVABLE_OVERRIDE_TARGET.to_string(), "E1003");
        assert_eq!(
            codes::EXPECTATION_PROVENANCE_UNRESOLVED.to_string(),
            "E1101"
        );
        assert_eq!(
            codes::RELEASE_GATE_REFUSES_DEBUG_EVIDENCE.to_string(),
            "E1102"
        );
        assert_eq!(codes::TAP_MAP_DISAGREEMENT.to_string(), "E1103");
    }

    /// D247.4: `codes::ALL` is the completeness sweep's source of
    /// truth -- no duplicate symbol names, no duplicate numeric codes,
    /// and every declared `pub const` above is actually listed (a
    /// crude but effective count check: bump this alongside any new
    /// `pub const`).
    #[test]
    // frob:ticket T-0008
    fn all_registry_has_no_duplicates() {
        let mut names = std::collections::HashSet::new();
        let mut numbers = std::collections::HashSet::new();
        for (name, code) in codes::ALL {
            assert!(names.insert(*name), "duplicate symbol {name}");
            assert!(
                numbers.insert(code.to_string()),
                "duplicate numeric code {code}"
            );
        }
        assert_eq!(
            codes::ALL.len(),
            79,
            "codes::ALL count drifted; if you added a code, bump this and \
             the completeness registry in explain.rs"
        );
    }
}
