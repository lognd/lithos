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
}

impl Family {
    /// The numeric base of this family (`E03xx` -> `300`).
    #[must_use]
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
        }
    }
}

/// A stable diagnostic code: a family plus its within-family offset.
/// Renders as `E0301` (family base + offset, zero-padded to four
/// digits).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct DiagCode {
    /// The owning family.
    pub family: Family,
    /// Offset within the family (`E0301` -> `1`).
    pub offset: u16,
}

impl DiagCode {
    /// Construct a code in `family` at `offset`.
    #[must_use]
    pub const fn new(family: Family, offset: u16) -> DiagCode {
        DiagCode { family, offset }
    }

    /// The full numeric code (`E0301` -> `301`).
    #[must_use]
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
    pub const INCOMPATIBLE_QUANTITIES: DiagCode = DiagCode::new(Family::Parse, 1);
    /// `E0102` -- `==` used on a continuous quantity (equality ban).
    pub const EQUALITY_ON_CONTINUOUS: DiagCode = DiagCode::new(Family::Parse, 2);
    /// `E0103` -- a `[a, b]` interval and a `[i .. j]` index range were
    /// confused: both separators in one bracket, or a range endpoint
    /// carrying a unit/fractional literal (regolith/02 sec. 3).
    pub const INTERVAL_RANGE_CONFUSION: DiagCode = DiagCode::new(Family::Parse, 3);
    /// `E0104` -- an illegal logarithmic-unit sum: after cancelling
    /// subtracted references against added ones, more than one reference
    /// survives (`dBm + dBm`) or a subtracted reference is uncancelled
    /// (regolith/02 sec. 5a; the linear product/quotient is not a valid
    /// quantity).
    pub const ILLEGAL_LOG_SUM: DiagCode = DiagCode::new(Family::Parse, 4);
    /// `E0105` -- a combinational (instantaneous `=`) cycle entirely
    /// within one clock/continuous domain, with no converter or register
    /// delta to break it (an algebraic loop, INV-16). A cross-domain edge
    /// always passes through a converter (a ZOH delta by type), so no
    /// zero-delay cycle can cross the continuous/discrete boundary; this
    /// code flags only a within-domain loop the source actually declares.
    pub const COMBINATIONAL_CYCLE: DiagCode = DiagCode::new(Family::Parse, 5);
    /// `E0106` -- a `run <name>:` line inside a `harness:` block (D99,
    /// WO-34 deliverable 1) whose header does not spell both a `from`
    /// and a `to` endpoint. Parse-time structural validation only
    /// (required-field presence): it does not resolve the endpoint refs
    /// (that is elaboration's job, WO-34 deliverable 2) -- only that the
    /// two keywords are both present, so a run with no path to extract
    /// a length over is rejected as close to the source as possible.
    pub const RUN_MISSING_ENDPOINT: DiagCode = DiagCode::new(Family::Parse, 6);
    /// `E0107` -- `by select(...)` (WO-56, D161) declared with an
    /// empty candidate list. A choice point over zero candidates has
    /// nothing to search, so it is rejected as a structural,
    /// parse-adjacent malformation (same L1 tier as
    /// `RUN_MISSING_ENDPOINT`) rather than surfacing as an empty
    /// domain at the optimizer.
    pub const SELECT_EMPTY_CANDIDATE_LIST: DiagCode = DiagCode::new(Family::Parse, 7);
    /// `E0201` -- a flownet subnet with no pressure imposer (reference,
    /// regulator, pump curve, or `Imposer`): the network is singular by
    /// construction and is rejected at COMPILE time, never at solve time
    /// (fluorite/02 sec. 4, the AD-23 fluid discipline).
    pub const IMPOSER_FREE_SUBNET: DiagCode = DiagCode::new(Family::FluidNet, 1);
    /// `E0202` -- a declared flownet node that no edge joins and that is
    /// not the reference (an unjoined terminal in the fluorite terminal
    /// ledger, fluorite/02 sec. 4): a dangling node cannot participate in
    /// the solved network.
    pub const UNJOINED_TERMINAL: DiagCode = DiagCode::new(Family::FluidNet, 2);
    /// `E0203` -- a transient/volume-budget claim (`fluids.volume_consumed`,
    /// `peak(...)`) names an edge with neither a compliance record nor an
    /// extractable wall (fluorite/03 sec. 1): the claim would be
    /// undischargeable, so lowering rejects it at compile time rather
    /// than leaving it to fail at solve time. WO-32 deliverable 5.
    pub const TRANSIENT_NO_COMPLIANCE: DiagCode = DiagCode::new(Family::FluidNet, 3);
    /// `E0204` -- a circulation net declares no `edges:` and no
    /// `reference:` (calcite/03 sec. 3, the circulation discipline's
    /// whole-net imposer-free-subnet analog; WO-47 deliverable 4). The
    /// per-space unjoined-terminal half of the sec. 3 ledger needs a
    /// connectivity extraction this front-end layer does not have (see
    /// `regolith_lower::calcite`'s module doc comment).
    pub const SPACE_NOT_IN_CIRCULATION: DiagCode = DiagCode::new(Family::FluidNet, 4);
    /// `E0205` -- a space cannot reach a reference (exit) through
    /// circulation edges (calcite/03 sec. 3, reference reachability).
    /// NOT YET DECIDABLE at this front-end layer without a new
    /// reachability traversal beyond the existing imposer-counting
    /// `net_core` (WO-47 close-out cut; see the crate's `calcite`
    /// module doc comment for the escalation).
    pub const CIRCULATION_UNREACHABLE: DiagCode = DiagCode::new(Family::FluidNet, 5);
    /// `E0206` -- an egress edge on a required path with zero/undeclared
    /// width or `path_length` (calcite/03 sec. 3).
    pub const EGRESS_EDGE_UNDECLARED: DiagCode = DiagCode::new(Family::FluidNet, 6);
    /// `E0207` -- a member cannot reach a support through transfer edges
    /// (calcite/03 sec. 3, the load-LEAK check). Same reachability cut
    /// as `E0205` -- see `CIRCULATION_UNREACHABLE`'s doc comment.
    pub const MEMBER_UNSUPPORTED: DiagCode = DiagCode::new(Family::FluidNet, 7);
    /// `E0208` -- a structure subnet has no `support:` node (calcite/03
    /// sec. 3, the load-path discipline's imposer-counting analog; WO-47
    /// deliverable 4).
    pub const STRUCTURE_NO_SUPPORT: DiagCode = DiagCode::new(Family::FluidNet, 8);
    /// `E0209` -- a member end/bearing terminal is unjoined and not
    /// `unloaded`, or declared tributary shares fail to partition their
    /// loaded surface (calcite/03 sec. 3; two conditions share one code
    /// per the spec's own allocation).
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
    pub const MEDIUM_MISMATCH: DiagCode = DiagCode::new(Family::FluidNet, 10);
    /// `E0301` -- an entity query matched more than one entity.
    pub const AMBIGUOUS_SELECTION: DiagCode = DiagCode::new(Family::References, 1);
    /// `E0302` -- conflicting borrow of an owned region.
    pub const BORROW_CONFLICT: DiagCode = DiagCode::new(Family::References, 2);
    /// `E0303` -- WO-33 D98: a claim projection (`max`/`min`/`at`/
    /// `slope`) names a field no `compute` claim in scope declares (the
    /// unresolved-reference family, mirroring `E0301`).
    pub const UNRESOLVED_FIELD_REFERENCE: DiagCode = DiagCode::new(Family::References, 3);
    /// `E0304` -- a change that alters an entity's structure class.
    pub const STRUCTURE_CLASS_CHANGE: DiagCode = DiagCode::new(Family::References, 4);
    /// `E0305` -- WO-33 D98: a `compute` claim's `over` clause
    /// (directly or transitively) references itself as a given,
    /// forming a cycle in the computed-field promise DAG. Names the
    /// full chain.
    pub const COMPUTE_FIELD_CYCLE: DiagCode = DiagCode::new(Family::References, 5);
    /// `E0306` -- WO-34 deliverable 2 (D99): a `harness:` run's `from`/
    /// `to` endpoints resolve to two different nets with no inline
    /// component between them. Names both nets.
    pub const RUN_CROSS_NET: DiagCode = DiagCode::new(Family::References, 6);
    /// `E0307` -- WO-34 deliverable 2: a `harness:` run's `from`/`to`
    /// header text does not spell a non-empty endpoint on one (or
    /// both) sides after the `from`/`to` keyword -- a dangling
    /// endpoint elaboration cannot resolve. Distinct from the D1
    /// parse-time `E0106` (which only checks the keywords are
    /// present): this fires when a keyword is present but names no
    /// endpoint text.
    pub const RUN_DANGLING_ENDPOINT: DiagCode = DiagCode::new(Family::References, 7);
    /// `E0308` -- WO-34 deliverable 2: a `harness:` run's `bundle`
    /// clause is present but names no group text (an empty/malformed
    /// `bundle` line) -- the co-routing group is unknown.
    pub const RUN_UNKNOWN_BUNDLE: DiagCode = DiagCode::new(Family::References, 8);
    /// `E0309` -- WO-34 deliverable 2: a `harness:` run's `along`
    /// structural ref failed extraction through the shared WO-32 seam
    /// (no realized record, an empty path, or an unknown roughness
    /// class -- see `regolith_lower::extract::ExtractError`).
    pub const RUN_EXTRACT_FAILED: DiagCode = DiagCode::new(Family::References, 9);
    /// `E0407` -- an enclosing system's boundary envelope is not
    /// contained in an imported/child artifact's proven boundary
    /// (boundary subsumption, INV-7).
    pub const BOUNDARY_NOT_SUBSUMED: DiagCode = DiagCode::new(Family::Contracts, 7);
    /// `E0410` -- a demanded capability exceeds the supplied one.
    pub const CAPABILITY_VS_DEMAND: DiagCode = DiagCode::new(Family::Contracts, 10);
    /// `E0420` -- a ledger imbalance (DOF / driver / domain-crossing).
    pub const LEDGER_IMBALANCE: DiagCode = DiagCode::new(Family::Contracts, 20);
    /// `E0432` -- a budget cannot close at its worst-case corner.
    pub const BUDGET_CANNOT_CLOSE: DiagCode = DiagCode::new(Family::Contracts, 32);
    /// `E0433` -- a compute intent is realized by other than exactly one
    /// workload (zero or two-or-more), naming both sides (cuprite/05 sec.
    /// 1 rule 1, EOPEN-15's realization ledger).
    pub const REALIZATION_NOT_EXACTLY_ONE: DiagCode = DiagCode::new(Family::Contracts, 33);
    /// `E0434` -- an interface-side promised bound field has no
    /// same-name field on the impl side (or vice versa): conformance
    /// windows match by field NAME (WO-26 D104), so a name present on
    /// only one side is a constructive diagnostic naming both.
    pub const PROMISED_BOUND_UNMATCHED: DiagCode = DiagCode::new(Family::Contracts, 34);
    /// `E0435` -- a temporal REDUCTION claim form (`peak`/`rms`/
    /// `overshoot`) was recognized but carries no trailing external
    /// comparator (WO-26 D102): a reduction yields a scalar and always
    /// needs one, so a missing comparator is rejected at compile time
    /// rather than silently deferred.
    pub const TEMPORAL_REDUCTION_MISSING_COMPARATOR: DiagCode =
        DiagCode::new(Family::Contracts, 35);
    /// `E0436` -- a temporal CONTAINMENT claim form (`settles`/
    /// `stays_within`) was recognized but carries a trailing external
    /// comparator (WO-26 D102): a containment's own parameters (`to=`
    /// tolerance, `mask=` reference) ARE the acceptance, so a trailing
    /// comparator is a shape error, not an extra check.
    pub const TEMPORAL_CONTAINMENT_UNEXPECTED_COMPARATOR: DiagCode =
        DiagCode::new(Family::Contracts, 36);
    /// `E0437` -- a general comparison claim line carries MORE than one
    /// top-level comparator (WO-26 D103: exactly ONE per claim line --
    /// each side is an ordinary quantity expression; chained or
    /// double-bounded comparisons have no defined lowering).
    pub const GENERAL_COMPARISON_MULTIPLE_COMPARATORS: DiagCode =
        DiagCode::new(Family::Contracts, 37);
    /// `E0438` -- an `mfg.cost(...)` claim's argument list is malformed
    /// (WO-54, toolchain/27 sec. 1.1): the accepted shape is
    /// `mfg.cost(<subject>[, profile=<name>])` -- a missing/empty
    /// subject, a duplicate or empty `profile=`, an unknown keyword,
    /// or a stray positional argument is rejected at compile time with
    /// the offending argument named, never silently deferred.
    pub const COST_CLAIM_MALFORMED: DiagCode = DiagCode::new(Family::Contracts, 38);
    /// `E0440` -- a numeric L2 solve (rigid statics, stiffness network)
    /// hit a singular or rank-deficient system: an under-determined
    /// support set, a disconnected stiffness network, or an
    /// ill-conditioned assembly (WO-23). Always a diagnostic, never a
    /// panic and never a NaN/non-finite value escaping the solve.
    pub const SINGULAR_SYSTEM: DiagCode = DiagCode::new(Family::Contracts, 40);
    /// `E0441` -- an exactly-constrained sketch (WO-11's conservative
    /// DOF ledger reports residual zero) whose numeric residual closure
    /// does not converge to zero: the declared constraints are
    /// mutually inconsistent, not merely under/over-counted (WO-23,
    /// hematite/07 OPEN-5/D65).
    pub const SKETCH_RESIDUAL_INCONSISTENT: DiagCode = DiagCode::new(Family::Contracts, 41);
    /// `E0442` -- a profile `constraints:` item references a segment
    /// name that no walk-step label binds (D150: segment names are
    /// syntax, `a: line right`; a comment is not a binding). The
    /// diagnostic is constructive: it names the walk's steps and the
    /// label spelling.
    pub const UNBOUND_SEGMENT_LABEL: DiagCode = DiagCode::new(Family::Contracts, 42);
    /// `E0443` -- a `then:` feature op has no projection into the v1
    /// `FeatureProgram` op set (WO-51 d2): the part's program is
    /// emitted without it and this NAMED warning records the gap --
    /// never silent truncation.
    pub const UNSUPPORTED_FEATURE_OP: DiagCode = DiagCode::new(Family::Contracts, 43);
    /// `E0444` -- a `.cavity(inlet=..., outlet=...)` query names a
    /// port whose feature binding no `then:` op in the part declares
    /// (D152 misuse; constructive: lists the part's op bindings).
    pub const CAVITY_PORT_UNRESOLVED: DiagCode = DiagCode::new(Family::Contracts, 44);
    /// `E0445` -- a cavity's inlet->outlet feature-op chain contains
    /// an op the v1 feature-op set cannot express, so no wetted path
    /// can be derived (hematite/07 sec. 2a's named escalation
    /// diagnostic -- the syntax-gap criterion, not a reopen).
    pub const CAVITY_CHAIN_INEXPRESSIBLE: DiagCode = DiagCode::new(Family::Contracts, 45);
    /// `E0446` -- a `by select(...)` (WO-56, D161) candidate list
    /// names the same impl-ref twice. Constructive: the check names
    /// the repeated candidate and its subject, since a duplicate
    /// candidate can never change a search's outcome and is always a
    /// authoring mistake (a copy/paste or a stale edit), never a
    /// legal "weight" on one alternative to preserve.
    pub const SELECT_DUPLICATE_CANDIDATE: DiagCode = DiagCode::new(Family::Contracts, 46);
    /// `E0501` -- positional index used where a domain is required.
    pub const INDEX_VS_DOMAIN: DiagCode = DiagCode::new(Family::Instances, 1);
    /// `E0502` -- `any` over a broken (non-uniform) orbit.
    pub const BROKEN_ORBIT_ANY: DiagCode = DiagCode::new(Family::Instances, 2);
    /// `E0503` -- a generic declaration is never instantiated (a dead
    /// generic: a monomorphization point-set with no points, INV-11).
    pub const DEAD_GENERIC: DiagCode = DiagCode::new(Family::Instances, 3);
    /// `E0504` -- a use-site generic instantiation supplies the wrong
    /// number of arguments for its declaration, so no static check can
    /// run at that point (an un-expandable instantiation, INV-11).
    pub const GENERIC_ARITY_MISMATCH: DiagCode = DiagCode::new(Family::Instances, 4);
    /// `E0601` -- a rule pack's static rule evaluated `false` against a
    /// matched entity (`pack.rule` provenance, `why:` rendered).
    pub const RULE_VIOLATION: DiagCode = DiagCode::new(Family::RulePacks, 1);
    /// `E0602` -- two attached rule packs declare a rule of the same
    /// qualified name (`pack.rule`): union composition with no priority
    /// arithmetic means a collision is an error, never silent shadowing
    /// (design doc D-C).
    pub const RULE_NAME_COLLISION: DiagCode = DiagCode::new(Family::RulePacks, 2);
    /// `E0603` -- a rule's predicate references a fact no layer (static
    /// entity DB, WO-22/24 realized-fact extraction) provides: a compile
    /// error on the rule itself (design doc D-E), not a deferral.
    pub const RULE_FACT_UNPROVIDED: DiagCode = DiagCode::new(Family::RulePacks, 3);
    /// `E0604` -- a `resolves:` clause names a field that is never
    /// `free` at any use site in the corpus (a stale resolver, mirror of
    /// `E0701`).
    pub const RULE_STALE_RESOLVER: DiagCode = DiagCode::new(Family::RulePacks, 4);
    /// `E0701` -- a declared waiver matched no claim or rule (stale).
    pub const STALE_WAIVER: DiagCode = DiagCode::new(Family::Evidence, 1);
    /// `E0702` -- a waiver carries no mandatory `basis:` (regolith/12
    /// rule 2): an unjustified concession, rejected as an INV-2 ladder
    /// overreach rather than accepted.
    pub const WAIVER_MISSING_BASIS: DiagCode = DiagCode::new(Family::Evidence, 2);
    /// `L0801` -- WO-40: an `import` line whose bound name is never
    /// referenced anywhere else in the same file (a dead import).
    pub const UNUSED_IMPORT: DiagCode = DiagCode::new(Family::Lint, 1);
    /// `L0802` -- WO-40: source text spells a retired project name
    /// (`mill`, `loom`, `dcad`, `deda`, `quarry`, `lodestone`, or the
    /// dead `.calc` extension spelling) as an identifier/word token --
    /// the "dead names are DEAD" CLAUDE.md rule, made mechanically
    /// checkable (design-log verbatim history and negative-fixture
    /// filenames are exempt, see `lints::retired_vocabulary`).
    pub const RETIRED_VOCABULARY_USAGE: DiagCode = DiagCode::new(Family::Lint, 2);
    /// `L0803` -- WO-40: one advisory per file summarizing its `todo!`/
    /// `assume!` count + locations (the honest-deferral surface; not a
    /// nag per line).
    pub const TODO_ASSUME_INVENTORY: DiagCode = DiagCode::new(Family::Lint, 3);
    /// `E0703` -- WO-40/D117: a `waive` block's target spells a lint
    /// code (`Lxxxx`, case-insensitive) instead of a `Group.claim`/rule
    /// reference. Deliberately in `Family::Evidence`, NOT `Family::Lint`
    /// (`apply_lint_config` only ever touches the `Lint` family): the
    /// waive ladder cannot silence its own audit, so this rejection can
    /// never itself be configured away by `[lints]`.
    pub const WAIVE_NAMES_LINT_CODE: DiagCode = DiagCode::new(Family::Evidence, 3);
}

#[cfg(test)]
mod tests {
    use super::codes;
    use super::{DiagCode, Family};

    #[test]
    fn code_renders_zero_padded() {
        assert_eq!(codes::AMBIGUOUS_SELECTION.to_string(), "E0301");
        assert_eq!(codes::BUDGET_CANNOT_CLOSE.to_string(), "E0432");
        assert_eq!(codes::INCOMPATIBLE_QUANTITIES.to_string(), "E0101");
        assert_eq!(codes::BROKEN_ORBIT_ANY.to_string(), "E0502");
        assert_eq!(codes::COMBINATIONAL_CYCLE.to_string(), "E0105");
        assert_eq!(codes::SELECT_EMPTY_CANDIDATE_LIST.to_string(), "E0107");
        assert_eq!(codes::SELECT_DUPLICATE_CANDIDATE.to_string(), "E0446");
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
    }

    #[test]
    fn family_base_maps_hundreds_digit() {
        assert_eq!(Family::FluidNet.base(), 200);
        assert_eq!(Family::Evidence.base(), 700);
        assert_eq!(DiagCode::new(Family::Evidence, 3).number(), 703);
    }

    #[test]
    fn code_round_trips_json() {
        let json = serde_json::to_string(&codes::BORROW_CONFLICT).unwrap();
        let back: DiagCode = serde_json::from_str(&json).unwrap();
        assert_eq!(back, codes::BORROW_CONFLICT);
    }
}
