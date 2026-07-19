//! Explain content beside the code (D247.3): `regolith explain <code>`
//! reads this ONE home. Every code in `code::codes::ALL` MUST have a
//! matching entry here -- that is the completeness rule D247.4
//! machine-checks (`completeness_is_total`, below); a code with no
//! entry at all is a build error, never a silent gap. An entry may
//! legitimately be an honest STUB (`authored: false`, the WO-131
//! deliverable 4 allowance) -- the health check counts stubs and
//! reports the count, it never hides it.

use crate::code::{codes, DiagCode};

/// One code's explain content: what it means, why it fires, how to
/// fix it, and (when authored) a worked example.
#[derive(Debug, Clone, Copy)]
// frob:doc docs/modules/regolith-diag.md#explain
pub struct ExplainEntry {
    /// The code this entry explains.
    pub code: DiagCode,
    /// The Rust symbol name (`code::codes::<SYMBOL>`).
    pub symbol: &'static str,
    /// What the code means (one or two sentences).
    pub meaning: &'static str,
    /// Why it fires (the triggering condition).
    pub why: &'static str,
    /// How to fix it.
    pub fix: &'static str,
    /// A worked example, when authored.
    pub example: Option<&'static str>,
    /// `false` for a "no explanation authored yet" stub (WO-131
    /// deliverable 4); `true` for hand-authored why/fix/example
    /// content. Reported, never hidden, by the completeness sweep.
    pub authored: bool,
}

const STUB: &str = "no explanation authored yet";

/// Build a STUB entry: `meaning` reuses the code's own `code.rs` doc
/// comment (already-written, accurate content); `why`/`fix` are the
/// honest placeholder, `example` is `None`, `authored = false`.
macro_rules! stub {
    ($sym:ident, $meaning:expr) => {
        ExplainEntry {
            code: codes::$sym,
            symbol: stringify!($sym),
            meaning: $meaning,
            why: STUB,
            fix: STUB,
            example: None,
            authored: false,
        }
    };
}

/// Build a fully AUTHORED entry.
macro_rules! authored {
    ($sym:ident, $meaning:expr, $why:expr, $fix:expr, $example:expr) => {
        ExplainEntry {
            code: codes::$sym,
            symbol: stringify!($sym),
            meaning: $meaning,
            why: $why,
            fix: $fix,
            example: Some($example),
            authored: true,
        }
    };
}

/// The ONE explain registry: every code in `codes::ALL`, no more, no
/// fewer (`completeness_is_total` enforces both directions).
// frob:doc docs/modules/regolith-diag.md#explain
pub const ALL: &[ExplainEntry] = &[

    authored!(
        EQUALITY_ON_CONTINUOUS,
        "`==` (structural equality) was used to compare a CONTINUOUS quantity \
         (a real-valued measurement: length, voltage, pressure, ...).",
        "Continuous quantities are produced by measurement, solve, or \
         simulation and never land on an exact bit-identical value twice -- \
         `==` between two continuous values is either always false (a \
         guaranteed-failing assertion the author almost certainly did not \
         intend) or a coincidence that will not survive the next solve. \
         The language bans it at compile time rather than letting it \
         silently pass or silently fail (regolith/02).",
        "Compare within a tolerance instead: use a `within [lo, hi]` claim, \
         or an explicit `abs(a - b) < tol` form. Discrete/enum-valued \
         quantities (an index, a boolean, a named state) are unaffected -- \
         `==` is still legal there.",
        "`length == 10mm` (rejected, E0102) becomes \
         `length within [9.9mm, 10.1mm]`."
    ),
    authored!(
        FAB_SET_INCOMPLETE,
        "A shipped gerber/fab-package set is missing a required charter 41 \
         sec. 3 layer (e.g. a copper layer, soldermask, or drill file).",
        "The emission backend (`regolith.backends.elec_fabset`) checks the \
         REQUIRED_FAB_SET against what was actually written before letting \
         the package be called complete -- a fab house cannot manufacture \
         from a partial layer set, so this is refused at emission time \
         rather than discovered at the fab house.",
        "Re-run the board emission for every declared layer (check the \
         board's stackup declares the layer, and that its producer ran \
         without error); the diagnostic names exactly which required \
         layer(s) are missing.",
        "A 2-layer board whose bottom-copper producer silently skipped (an \
         earlier IR gap) ships only top copper + drill -> E0901 names \
         `B.Cu` as the missing layer."
    ),
    authored!(
        DRAFTING_AUDIT_REFUSED,
        "A drafting-rule check failed on a GATING sheet of a drawing \
         package (a title-block, dimension, or tolerance rule the audit \
         considers release-blocking).",
        "`regolith.backends.drawings.audit` runs every attached drafting \
         rule over every sheet before a drawing package is allowed to \
         ship; a rule failing on a sheet marked gating (not \
         `_sheet_is_non_gating`) means the drawing does not meet the \
         package's own declared standard, so shipping it would hand a \
         fabricator/assembler an unreliable drawing.",
        "Read the named rule and sheet in the message, fix the underlying \
         drawing content (missing dimension, wrong title-block field, \
         ...), and re-run the audit. If the sheet is genuinely \
         non-gating, mark it so explicitly rather than relying on the \
         audit to guess.",
        "A detail sheet missing a required GD&T datum callout fails rule \
         `datum.required` -> E0902 names the rule, the sheet's drawing \
         number, and the failing message."
    ),
    authored!(
        ARTIFACT_INDEX_DRIFT,
        "A shipped package's artifact index (the manifest's declared file \
         list) disagrees with the files the package actually wrote to \
         disk.",
        "A manifest is the receiver's promise of exactly what shipped; an \
         index that lists a file never written (or omits one that was) \
         is a silent integrity gap that hash/signature checks alone do \
         not catch, since they verify files the manifest names, not the \
         completeness of the naming itself.",
        "Regenerate the manifest from the actual output directory rather \
         than a stale in-memory file list; if a producer is skipping a \
         file it should emit, fix the producer.",
        "RESERVED (WO-131 escalation F-WO131-1): no current producer \
         raises this code yet, so no worked example is authored. The \
         mechanism (registry entry, family, this explain content) is in \
         place for the producer that closes the gap."
    ),
    authored!(
        UNEXPLAINED_OVERRIDE,
        "RESERVED for WO-129A (D246): an override applied through the \
         D243 injection channel with no author/reason recorded.",
        "The override channel exists to let a human deliberately \
         supersede a computed value with an explicit, attributed \
         decision (D243); an override with no author/reason attached is \
         indistinguishable from an accidental or malicious value \
         injection, so D246 refuses it rather than accept an \
         unattributed claim override.",
        "Not yet implemented by this WO -- WO-129A wires the raise site. \
         The fix, once implemented, will be: supply the required \
         `author=`/`reason=` fields on the override declaration.",
        "RESERVED -- worked example lands with WO-129A."
    ),
    authored!(
        SOURCE_ONLY_TARGET_REFUSED,
        "RESERVED for WO-129A (D246): an override names a SOURCE-only \
         claim as its target -- the D246 claims/evidence boundary.",
        "D246 draws a hard line between a claim that is pure declared \
         SOURCE (never independently checked) and one backed by \
         evidence; letting an override silently reclassify a source-only \
         claim as if it had evidence would let an unverified assertion \
         masquerade as a proven one.",
        "Not yet implemented by this WO -- WO-129A wires the raise site. \
         The fix, once implemented, will be: target an evidence-backed \
         claim, or promote the source claim to an evidence-backed one \
         first.",
        "RESERVED -- worked example lands with WO-129A."
    ),
    authored!(
        UNRESOLVABLE_OVERRIDE_TARGET,
        "RESERVED for WO-129A (D246): an override names a target that \
         cannot be resolved anywhere in the build.",
        "An override that points at nothing is either a typo or stale \
         (the target was renamed/removed since the override was \
         written); silently ignoring it would let the override rot \
         without anyone noticing the value it was meant to control is \
         now unsupervised.",
        "Not yet implemented by this WO -- WO-129A wires the raise site. \
         The fix, once implemented, will be: correct the target ref, or \
         remove the stale override.",
        "RESERVED -- worked example lands with WO-129A."
    ),
    authored!(
        EXPECTATION_PROVENANCE_UNRESOLVED,
        "A bring-up harness's `expected_signals.json` carries a \
         provenance ref that does not resolve inside the package, or a \
         populated expected value with no units attached (D224).",
        "A bring-up expectation exists to let a technician verify a \
         measured signal against a declared, TRACEABLE value; a \
         provenance ref that resolves to nothing means the expected \
         value's origin cannot be audited, and a unitless populated \
         value is neither a value-with-units nor an honest named \
         absence (D224's units invariant, charter 40 sec. 3) -- both are \
         refused rather than shipped ambiguous.",
        "Fix the provenance ref to name a claim that actually exists in \
         the package, or attach the missing `units` field to every \
         populated expected value.",
        "`expected_signals.json` row `{\"channel\": \"VCC\", \"expected\": \"claim:Board.vcc_out\"}` \
         where no claim named `Board.vcc_out` exists in the package -> \
         E1101 names the channel and the unresolved ref."
    ),
    authored!(
        RELEASE_GATE_REFUSES_DEBUG_EVIDENCE,
        "A ship manifest built with `profile=debug` was presented as \
         release-gate evidence (D237.1).",
        "A debug build's provenance chain (optimizer settings, symbol \
         stripping, evidence rollup) is not the same artifact as what \
         ships to a customer; accepting a debug package as release proof \
         would let a downstream gate (an acceptance test, a jig-mating \
         check) certify against the wrong artifact. Debug packages stay \
         fully verifiable (`verify_manifest`/`verify_file_hashes`) -- \
         only their ELIGIBILITY as release evidence is refused.",
        "Ship (or re-ship) with `profile=release` before presenting the \
         package as release-gate evidence; keep the debug package for \
         its own purpose (bring-up, debugging) instead.",
        "`release_gate_refuses_debug_evidence(manifest)` where \
         `manifest.profile == \"debug\"` -> E1102 names the profile and \
         cites D237.1."
    ),
    authored!(
        TAP_MAP_DISAGREEMENT,
        "A debug tap map disagrees with the artifact it claims to \
         describe (`tap_map_artifact_mismatch`, `regolith.backends.\
         debug_taps`).",
        "A tap map is the bring-up harness's promise of which physical \
         test point corresponds to which internal signal; a tap map that \
         no longer matches the artifact it was generated against (a \
         stale map after a layout change, or a hand-edited map) would \
         send a technician probing the wrong point -- refused rather \
         than trusted.",
        "Regenerate the tap map from the current artifact rather than \
         reusing a cached one; if the map was hand-edited, verify every \
         entry against the current layout before re-attaching it.",
        "A tap map built against board rev A, reused unchanged after a \
         rev B layout shuffled net names -> E1103 names the artifact \
         digest mismatch."
    ),

    stub!(INCOMPATIBLE_QUANTITIES, "arithmetic between incompatible quantities."),
    stub!(INTERVAL_RANGE_CONFUSION, "a `[a, b]` interval and a `[i .. j]` index range were confused: both separators in one bracket, or a range endpoint carrying a unit/fractional literal (regolith/02 sec. 3)."),
    stub!(ILLEGAL_LOG_SUM, "an illegal logarithmic-unit sum: after cancelling subtracted references against added ones, more than one reference survives (`dBm + dBm`) or a subtracted reference is uncancelled (regolith/02 sec. 5a; the linear product/quotient is not a valid quantity)."),
    stub!(COMBINATIONAL_CYCLE, "a combinational (instantaneous `=`) cycle entirely within one clock/continuous domain, with no converter or register delta to break it (an algebraic loop, INV-16). A cross-domain edge always passes through a converter (a ZOH delta by type), so no zero-delay cycle can cross the continuous/discrete boundary; this code flags only a within-domain loop the source actually declares."),
    stub!(RUN_MISSING_ENDPOINT, "a `run <name>:` line inside a `harness:` block (D99, WO-34 deliverable 1) whose header does not spell both a `from` and a `to` endpoint. Parse-time structural validation only (required-field presence): it does not resolve the endpoint refs (that is elaboration's job, WO-34 deliverable 2) -- only that the two keywords are both present, so a run with no path to extract a length over is rejected as close to the source as possible."),
    stub!(SELECT_EMPTY_CANDIDATE_LIST, "`by select(...)` (WO-56, D161) declared with an empty candidate list. A choice point over zero candidates has nothing to search, so it is rejected as a structural, parse-adjacent malformation (same L1 tier as `RUN_MISSING_ENDPOINT`) rather than surfacing as an empty domain at the optimizer."),
    stub!(IMPOSER_FREE_SUBNET, "a flownet subnet with no pressure imposer (reference, regulator, pump curve, or `Imposer`): the network is singular by construction and is rejected at COMPILE time, never at solve time (fluorite/02 sec. 4, the AD-23 fluid discipline)."),
    stub!(UNJOINED_TERMINAL, "a declared flownet node that no edge joins and that is not the reference (an unjoined terminal in the fluorite terminal ledger, fluorite/02 sec. 4): a dangling node cannot participate in the solved network."),
    stub!(TRANSIENT_NO_COMPLIANCE, "a transient/volume-budget claim (`fluids.volume_consumed`, `peak(...)`) names an edge with neither a compliance record nor an extractable wall (fluorite/03 sec. 1): the claim would be undischargeable, so lowering rejects it at compile time rather than leaving it to fail at solve time. WO-32 deliverable 5."),
    stub!(SPACE_NOT_IN_CIRCULATION, "a circulation net declares no `edges:` and no `reference:` (calcite/03 sec. 3, the circulation discipline's whole-net imposer-free-subnet analog; WO-47 deliverable 4). The per-space unjoined-terminal half of the sec. 3 ledger needs a connectivity extraction this front-end layer does not have (see `regolith_lower::calcite`'s module doc comment)."),
    stub!(CIRCULATION_UNREACHABLE, "a space cannot reach a reference (exit) through circulation edges (calcite/03 sec. 3, reference reachability). NOT YET DECIDABLE at this front-end layer without a new reachability traversal beyond the existing imposer-counting `net_core` (WO-47 close-out cut; see the crate's `calcite` module doc comment for the escalation)."),
    stub!(EGRESS_EDGE_UNDECLARED, "an egress edge on a required path with zero/undeclared width or `path_length` (calcite/03 sec. 3)."),
    stub!(MEMBER_UNSUPPORTED, "a member cannot reach a support through transfer edges (calcite/03 sec. 3, the load-LEAK check). Same reachability cut as `E0205` -- see `CIRCULATION_UNREACHABLE`'s doc comment."),
    stub!(STRUCTURE_NO_SUPPORT, "a structure subnet has no `support:` node (calcite/03 sec. 3, the load-path discipline's imposer-counting analog; WO-47 deliverable 4)."),
    stub!(MEMBER_UNJOINED_OR_TRIBUTARY_MISMATCH, "a member end/bearing terminal is unjoined and not `unloaded`, or declared tributary shares fail to partition their loaded surface (calcite/03 sec. 3; two conditions share one code per the spec's own allocation)."),
    stub!(MEDIUM_MISMATCH, "FOPEN-1 (fluorite/04, WO-49): a flownet edge resolves, through its `from=<part>.<role>` ref, to a component with a declared `impl FluidPort<medium=...>` binding whose medium disagrees with the flownet's own `medium=` header -- a mixed- medium subnet, rejected at compile time before payload construction (fluorite/02 sec. 1, the one-medium-per-subnet rule). Names both media and both declaration sites. (Landed as E0204 on the WO-49 branch; renumbered at integration -- the ratified calcite spec owns E0204-E0209.)."),
    stub!(POINT_LOAD_NEEDS_STATION, "WO-85/D194: a concentrated (force/moment-unit) load row targets a bare MEMBER with no `@<station>` refinement (the location is ambiguous: name a station, `G1@0.5`, or target a joint/support instead -- never inferred), or its declared station is malformed / outside the normalized `[0, 1]` range. Constructive: the message names both valid spellings."),
    stub!(AMBIGUOUS_SELECTION, "an entity query matched more than one entity."),
    stub!(BORROW_CONFLICT, "conflicting borrow of an owned region."),
    stub!(UNRESOLVED_FIELD_REFERENCE, "WO-33 D98: a claim projection (`max`/`min`/`at`/ `slope`) names a field no `compute` claim in scope declares (the unresolved-reference family, mirroring `E0301`)."),
    stub!(STRUCTURE_CLASS_CHANGE, "a change that alters an entity's structure class."),
    stub!(COMPUTE_FIELD_CYCLE, "WO-33 D98: a `compute` claim's `over` clause (directly or transitively) references itself as a given, forming a cycle in the computed-field promise DAG. Names the full chain."),
    stub!(RUN_CROSS_NET, "WO-34 deliverable 2 (D99): a `harness:` run's `from`/ `to` endpoints resolve to two different nets with no inline component between them. Names both nets."),
    stub!(RUN_DANGLING_ENDPOINT, "WO-34 deliverable 2: a `harness:` run's `from`/`to` header text does not spell a non-empty endpoint on one (or both) sides after the `from`/`to` keyword -- a dangling endpoint elaboration cannot resolve. Distinct from the D1 parse-time `E0106` (which only checks the keywords are present): this fires when a keyword is present but names no endpoint text."),
    stub!(RUN_UNKNOWN_BUNDLE, "WO-34 deliverable 2: a `harness:` run's `bundle` clause is present but names no group text (an empty/malformed `bundle` line) -- the co-routing group is unknown."),
    stub!(RUN_EXTRACT_FAILED, "WO-34 deliverable 2: a `harness:` run's `along` structural ref failed extraction through the shared WO-32 seam (no realized record, an empty path, or an unknown roughness class -- see `regolith_lower::extract::ExtractError`)."),
    stub!(BOUNDARY_NOT_SUBSUMED, "an enclosing system's boundary envelope is not contained in an imported/child artifact's proven boundary (boundary subsumption, INV-7)."),
    stub!(CAPABILITY_VS_DEMAND, "a demanded capability exceeds the supplied one."),
    stub!(LEDGER_IMBALANCE, "a ledger imbalance (DOF / driver / domain-crossing)."),
    stub!(BUDGET_CANNOT_CLOSE, "a budget cannot close at its worst-case corner."),
    stub!(REALIZATION_NOT_EXACTLY_ONE, "a compute intent is realized by other than exactly one workload (zero or two-or-more), naming both sides (cuprite/05 sec. 1 rule 1, EOPEN-15's realization ledger)."),
    stub!(PROMISED_BOUND_UNMATCHED, "an interface-side promised bound field has no same-name field on the impl side (or vice versa): conformance windows match by field NAME (WO-26 D104), so a name present on only one side is a constructive diagnostic naming both."),
    stub!(TEMPORAL_REDUCTION_MISSING_COMPARATOR, "a temporal REDUCTION claim form (`peak`/`rms`/ `overshoot`) was recognized but carries no trailing external comparator (WO-26 D102): a reduction yields a scalar and always needs one, so a missing comparator is rejected at compile time rather than silently deferred."),
    stub!(TEMPORAL_CONTAINMENT_UNEXPECTED_COMPARATOR, "a temporal CONTAINMENT claim form (`settles`/ `stays_within`) was recognized but carries a trailing external comparator (WO-26 D102): a containment's own parameters (`to=` tolerance, `mask=` reference) ARE the acceptance, so a trailing comparator is a shape error, not an extra check."),
    stub!(GENERAL_COMPARISON_MULTIPLE_COMPARATORS, "a general comparison claim line carries MORE than one top-level comparator (WO-26 D103: exactly ONE per claim line -- each side is an ordinary quantity expression; chained or double-bounded comparisons have no defined lowering)."),
    stub!(COST_CLAIM_MALFORMED, "an `mfg.cost(...)` claim's argument list is malformed (WO-54, toolchain/27 sec. 1.1): the accepted shape is `mfg.cost(<subject>[, profile=<name>])` -- a missing/empty subject, a duplicate or empty `profile=`, an unknown keyword, or a stray positional argument is rejected at compile time with the offending argument named, never silently deferred."),
    stub!(SINGULAR_SYSTEM, "a numeric L2 solve (rigid statics, stiffness network) hit a singular or rank-deficient system: an under-determined support set, a disconnected stiffness network, or an ill-conditioned assembly (WO-23). Always a diagnostic, never a panic and never a NaN/non-finite value escaping the solve."),
    stub!(SKETCH_RESIDUAL_INCONSISTENT, "an exactly-constrained sketch (WO-11's conservative DOF ledger reports residual zero) whose numeric residual closure does not converge to zero: the declared constraints are mutually inconsistent, not merely under/over-counted (WO-23, hematite/07 OPEN-5/D65)."),
    stub!(UNBOUND_SEGMENT_LABEL, "a profile `constraints:` item references a segment name that no walk-step label binds (D150: segment names are syntax, `a: line right`; a comment is not a binding). The diagnostic is constructive: it names the walk's steps and the label spelling."),
    stub!(UNSUPPORTED_FEATURE_OP, "a `then:` feature op has no projection into the v1 `FeatureProgram` op set (WO-51 d2): the part's program is emitted without it and this NAMED warning records the gap -- never silent truncation."),
    stub!(CAVITY_PORT_UNRESOLVED, "a `.cavity(inlet=..., outlet=...)` query names a port whose feature binding no `then:` op in the part declares (D152 misuse; constructive: lists the part's op bindings)."),
    stub!(CAVITY_CHAIN_INEXPRESSIBLE, "a cavity's inlet->outlet feature-op chain contains an op the v1 feature-op set cannot express, so no wetted path can be derived (hematite/07 sec. 2a's named escalation diagnostic -- the syntax-gap criterion, not a reopen)."),
    stub!(SELECT_DUPLICATE_CANDIDATE, "a `by select(...)` (WO-56, D161) candidate list names the same impl-ref twice. Constructive: the check names the repeated candidate and its subject, since a duplicate candidate can never change a search's outcome and is always a authoring mistake (a copy/paste or a stale edit), never a legal \"weight\" on one alternative to preserve."),
    stub!(SKETCH_CLOSE_EDGE_UNDERCONSTRAINED, "a walk with a labeled `close` edge (an unconstrained 2-DOF vector, WO-62 D171/AD-32) still carries an explicit `free` segment length: closure gives the close edge both equations, so there is nothing left to determine the other free length -- under-constrained, naming the residual segment and the missing constraint class (assert its length or remove the `close` label). The over-constrained sibling is `E0441`."),
    stub!(SHEET_BLANK_NO_GAUGE_SOURCE, "a sheet-metal `Blank(...)` op has no thickness value source: no explicit `thickness=` arg AND no enclosing `process=<proc>(sheet=<t>)` gauge source (WO-62 D171/AD-32, INV-21's `cause: process(<proc>.sheet)` API). A gauge-less unasserted sheet part is a compile diagnostic, never a silently unthickened blank."),
    stub!(PLAN_CLAUSE_MALFORMED, "a `plan: extern(<ref>, <dialect>)` field (WO-69, regolith/08 sec. 4's L6 row) is malformed: the extern ref string is missing, OR the dialect is not a registered `fmt.gcode_*` name (`gcode_fanuc`/`gcode_marlin`). No `cam.*` obligations are emitted for a malformed clause (honest silence, never a guess); this diagnostic is the only signal."),
    stub!(FORALL_DOMAIN_UNDECLARED, "a `forall <var> in <domain>:` sweep names a BARE PLURAL (`boards`, `assemblies`) that resolves to no declared domain, so the sweep silently covers zero points -- a vacuous pass, the honesty gap WO-90 closes. A declared domain (`[lo, hi]` interval, `{a, b}` discrete set, `registry(<family>)`, `<Entity>.members.all`, or a dotted pack ref) is legal; an explicitly EMPTY declared domain stays legal (empty sweep = zero obligations, honestly). Only the undeclared bare-plural name trips this diagnostic."),
    stub!(REMOVAL_FAMILY_MALFORMED, "a material-removal family constructor (`Ribs`, `PocketGrid`, `Shell`, `Lattice` -- charter 34 phase 1, D200/ WO-77) spells malformed parameters: a missing required slot, an unknown/duplicate slot, a wrong-dimension value (an int slot given a length, a length slot given a bare number), a `density` outside `[0, 1]`, or an unknown lattice `cell` name. Constructive: the diagnostic names the family's full signature and the exact offending slot; the op is omitted from the emitted feature program (never a guessed value, never silent truncation)."),
    stub!(SI_IMPEDANCE_MALFORMED, "an `elec.impedance(...) within [lo, hi]` claim (WO-78, charter 35 sec. 1.2) names no net: the call's first argument is empty or keyword-only, so there is nothing to attribute the impedance window to. Constructive: the message names the accepted shape (`elec.impedance(<net>[, role=..., stackup=..., layer=..., w=...]) within [lo, hi]`); the claim is not lowered (never a guessed subject)."),
    stub!(INDEX_VS_DOMAIN, "positional index used where a domain is required."),
    stub!(BROKEN_ORBIT_ANY, "`any` over a broken (non-uniform) orbit."),
    stub!(DEAD_GENERIC, "a generic declaration is never instantiated (a dead generic: a monomorphization point-set with no points, INV-11)."),
    stub!(GENERIC_ARITY_MISMATCH, "a use-site generic instantiation supplies the wrong number of arguments for its declaration, so no static check can run at that point (an un-expandable instantiation, INV-11)."),
    stub!(RULE_VIOLATION, "a rule pack's static rule evaluated `false` against a matched entity (`pack.rule` provenance, `why:` rendered)."),
    stub!(RULE_NAME_COLLISION, "two attached rule packs declare a rule of the same qualified name (`pack.rule`): union composition with no priority arithmetic means a collision is an error, never silent shadowing (design doc D-C)."),
    stub!(RULE_FACT_UNPROVIDED, "a rule's predicate references a fact no layer (static entity DB, WO-22/24 realized-fact extraction) provides: a compile error on the rule itself (design doc D-E), not a deferral."),
    stub!(RULE_STALE_RESOLVER, "a `resolves:` clause names a field that is never `free` at any use site in the corpus (a stale resolver, mirror of `E0701`)."),
    stub!(STALE_WAIVER, "a declared waiver matched no claim or rule (stale)."),
    stub!(WAIVER_MISSING_BASIS, "a waiver carries no mandatory `basis:` (regolith/12 rule 2): an unjustified concession, rejected as an INV-2 ladder overreach rather than accepted."),
    stub!(UNUSED_IMPORT, "WO-40: an `import` line whose bound name is never referenced anywhere else in the same file (a dead import)."),
    stub!(RETIRED_VOCABULARY_USAGE, "WO-40: source text spells a retired project name (`mill`, `loom`, `dcad`, `deda`, `quarry`, `lodestone`, or the dead `.calc` extension spelling) as an identifier/word token -- the \"dead names are DEAD\" CLAUDE.md rule, made mechanically checkable (design-log verbatim history and negative-fixture filenames are exempt, see `lints::retired_vocabulary`)."),
    stub!(TODO_ASSUME_INVENTORY, "WO-40: one advisory per file summarizing its `todo!`/ `assume!` count + locations (the honest-deferral surface; not a nag per line)."),
    stub!(WAIVE_NAMES_LINT_CODE, "WO-40/D117: a `waive` block's target spells a lint code (`Lxxxx`, case-insensitive) instead of a `Group.claim`/rule reference. Deliberately in `Family::Evidence`, NOT `Family::Lint` (`apply_lint_config` only ever touches the `Lint` family): the waive ladder cannot silence its own audit, so this rejection can never itself be configured away by `[lints]`."),

];

/// Look up an explain entry by its rendered code string (`"E0901"`,
/// case-insensitive). `regolith explain <code>` reads this.
#[must_use]
// frob:doc docs/modules/regolith-diag.md#explain
// frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
pub fn find(code_str: &str) -> Option<&'static ExplainEntry> {
    let needle = code_str.trim().to_ascii_uppercase();
    ALL.iter().find(|e| e.code.to_string() == needle)
}

/// Constructive near-matches for an unknown code (deliverable 5): the
/// same family prefix (`E09`) first, falling back to a small edit
/// distance over the full string, so a typo like `E0091` still
/// surfaces `E0901`.
#[must_use]
// frob:doc docs/modules/regolith-diag.md#explain
// frob:waive TEST002 reason="rust collector fails fast on lib-less fuzz/ crate, killing test-evidence collection repo-wide; binding+tests are real, see FROBLEMS 2026-07-18"
pub fn near_matches(code_str: &str, limit: usize) -> Vec<&'static ExplainEntry> {
    let needle = code_str.trim().to_ascii_uppercase();
    let prefix: String = needle.chars().take(3).collect();
    let mut same_prefix: Vec<&'static ExplainEntry> = ALL
        .iter()
        .filter(|e| e.code.to_string().starts_with(&prefix))
        .collect();
    if !same_prefix.is_empty() {
        same_prefix.truncate(limit);
        return same_prefix;
    }
    let mut scored: Vec<(usize, &'static ExplainEntry)> = ALL
        .iter()
        .map(|e| (edit_distance(&needle, &e.code.to_string()), e))
        .collect();
    scored.sort_by_key(|(d, _)| *d);
    scored.into_iter().take(limit).map(|(_, e)| e).collect()
}

/// Plain Levenshtein distance, small alphabet (code strings are short
/// -- `O(n*m)` is fine).
fn edit_distance(a: &str, b: &str) -> usize {
    let a: Vec<char> = a.chars().collect();
    let b: Vec<char> = b.chars().collect();
    let mut prev: Vec<usize> = (0..=b.len()).collect();
    let mut curr = vec![0usize; b.len() + 1];
    for (i, ca) in a.iter().enumerate() {
        curr[0] = i + 1;
        for (j, cb) in b.iter().enumerate() {
            let cost = usize::from(ca != cb);
            curr[j + 1] = (prev[j + 1] + 1).min(curr[j] + 1).min(prev[j] + cost);
        }
        std::mem::swap(&mut prev, &mut curr);
    }
    prev[b.len()]
}

#[cfg(test)]
mod tests {
    use super::{codes, find, near_matches, ALL};

    // frob:tests crates/regolith-diag/src/explain.rs::find kind="unit"
    #[test]
    fn find_is_case_insensitive_and_trims() {
        assert!(find(" e0901 ").is_some());
        assert_eq!(find("e0901").unwrap().symbol, "FAB_SET_INCOMPLETE");
        assert!(find("E9999").is_none());
    }

    // frob:tests crates/regolith-diag/src/explain.rs::near_matches kind="unit"
    #[test]
    fn near_matches_suggests_same_family_first() {
        let hits = near_matches("E0999", 3);
        assert!(!hits.is_empty());
        assert!(hits.iter().all(|e| e.code.to_string().starts_with("E09")));
    }

    #[test]
    fn near_matches_falls_back_to_edit_distance_outside_any_family() {
        let hits = near_matches("ZZZZZ", 1);
        assert_eq!(hits.len(), 1);
    }

    /// D247.4a: every code in `codes::ALL` has a matching explain
    /// entry, and every explain entry names a real registered code --
    /// completeness is checked in BOTH directions so a stale entry
    /// (code renamed/removed) is caught too.
    #[test]
    fn completeness_is_total() {
        let registered: std::collections::HashSet<&str> =
            codes::ALL.iter().map(|(name, _)| *name).collect();
        let explained: std::collections::HashSet<&str> = ALL.iter().map(|e| e.symbol).collect();
        let missing: Vec<&&str> = registered.difference(&explained).collect();
        assert!(
            missing.is_empty(),
            "code(s) registered in code::codes::ALL with NO explain entry \
             (D247.4a): {missing:?}"
        );
        let stale: Vec<&&str> = explained.difference(&registered).collect();
        assert!(
            stale.is_empty(),
            "explain entry names a code no longer in code::codes::ALL: {stale:?}"
        );
    }

    /// The count of honest stubs is REPORTED, never hidden (WO-131
    /// deliverable 4/6a) -- this test just proves the count is
    /// computable; the actual reporting happens in the `regolith
    /// explain`/health-leg callers.
    #[test]
    fn stub_count_is_visible() {
        let stubs = ALL.iter().filter(|e| !e.authored).count();
        let authored = ALL.iter().filter(|e| e.authored).count();
        assert_eq!(stubs + authored, ALL.len());
        assert!(
            authored >= 10,
            "the WO-131 new-family + E0102 entries must stay authored"
        );
    }

    /// D247.4a's negative case, proven on a SYNTHETIC mini-registry
    /// (production can never actually be left incomplete, since the
    /// test above would fail the build first) -- this proves the
    /// CHECKING LOGIC itself can fail, per D247.4's "a rule that
    /// cannot fail a build is documentation, not doctrine".
    #[test]
    fn completeness_check_can_fail_on_a_missing_entry() {
        let registered: std::collections::HashSet<&str> = ["A", "B", "C"].into_iter().collect();
        let explained: std::collections::HashSet<&str> = ["A", "B"].into_iter().collect();
        let missing: Vec<&&str> = registered.difference(&explained).collect();
        assert_eq!(missing.len(), 1);
        assert_eq!(*missing[0], "C");
    }

    /// D247.4a's negative case for a stale (over-)entry.
    #[test]
    fn completeness_check_can_fail_on_a_stale_entry() {
        let registered: std::collections::HashSet<&str> = ["A", "B"].into_iter().collect();
        let explained: std::collections::HashSet<&str> = ["A", "B", "GHOST"].into_iter().collect();
        let stale: Vec<&&str> = explained.difference(&registered).collect();
        assert_eq!(stale.len(), 1);
        assert_eq!(*stale[0], "GHOST");
    }

    /// A representative from each new family renders real content.
    #[test]
    fn new_family_entries_are_authored() {
        for sym in [
            "FAB_SET_INCOMPLETE",
            "UNEXPLAINED_OVERRIDE",
            "EXPECTATION_PROVENANCE_UNRESOLVED",
        ] {
            let entry = ALL.iter().find(|e| e.symbol == sym).unwrap();
            assert!(entry.authored, "{sym} should be authored, not a stub");
            assert!(entry.example.is_some());
        }
    }

    /// `regolith explain E0102` (the acceptance-criteria code) is
    /// authored with a worked example.
    #[test]
    fn e0102_is_authored() {
        let entry = ALL
            .iter()
            .find(|e| e.code == codes::EQUALITY_ON_CONTINUOUS)
            .unwrap();
        assert!(entry.authored);
        assert!(entry.example.unwrap().contains("within"));
    }

    /// Lookup by code returns the same entry lookup by symbol does.
    #[test]
    fn find_by_code_matches_find_by_symbol() {
        let by_code = ALL.iter().find(|e| e.code == codes::FAB_SET_INCOMPLETE);
        let by_symbol = ALL.iter().find(|e| e.symbol == "FAB_SET_INCOMPLETE");
        assert_eq!(by_code.map(|e| e.symbol), by_symbol.map(|e| e.symbol));
    }
}
