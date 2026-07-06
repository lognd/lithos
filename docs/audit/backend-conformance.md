# Backend Conformance Audit: regolith-sem / regolith-ir / regolith-oblig / regolith-lower

Date: 2026-07-04. Scope per dispatch: entity DB/queries/ownership-
borrows/stages/symmetry/profiles (regolith-sem); contract IR/ledgers/
budgets/conformance (regolith-ir); claims/obligations/evidence/waivers/
canonical encoding (regolith-oblig); the lowering pipeline
(regolith-lower).

## Summary

The library crates (regolith-sem, regolith-ir, regolith-oblig) are in
good shape: determinism discipline (AD-6) is followed carefully
(IndexMap/BTreeSet only, canonical-order snapshot hashing, ryu/rational
avoided-drift not directly exercised here but no HashMap iteration
reaches output), the canonical CBOR encoder and content_address
function match AD-5/AD-18 exactly, and INV-4/INV-9-adjacent code
(symmetry intersection, orbit legality) is conservative by
construction as specified. The weak point is regolith-lower (WO-19),
which is explicitly and honestly documented as "wired end-to-end,
lowering depth partial": most of the interesting per-invariant
enforcement (ownership/borrow checks, stage graphs, symmetry orbits,
profile DOF ledgers, monomorphization, contract conformance beyond
budget sums) runs over structurally-empty inputs because the grammar
does not yet expose `OpaqueIsland` bodies (mating/connect/impl/walk
blocks). That much is a well-documented, in-scope cut. Two things are
NOT documented as cuts and are flagged HIGH: (1) the obligation content
key omits the harness model-registry version entirely (no field exists
anywhere to carry it), so a model-registry upgrade cannot invalidate
cached evidence -- a real INV-1/INV-10 soundness gap, not a "not yet
lowered" gap; (2) the lowering pipeline's `given:` block is
unconditionally empty for every obligation it builds (materials/loads/
backing always `Vec::new()`), which is mentioned nowhere in the WO-19
status note (only sweep-domain unavailability is called out) even
though it is the exact mechanism INV-1 relies on for evidence-key
sensitivity to loads/materials.

**Coverage note (what was read vs skipped).** Read in full: regolith
05, 06, 07, 13; 00-architecture.md (all of AD-1..18); WO-19; the WO-19
module docstrings for entities.rs/checks.rs/contracts.rs (which
themselves cite WO-07..13's per-file cut notes). Read in full: every
`.rs` file in regolith-oblig/src (obligation, encoding, claim,
evidence, waiver, signature, lib) and regolith-util/src/canon.rs; every
file in regolith-lower/src (lib, claims, entities, checks, contracts,
discharge, output); regolith-sem/src/{symmetry,ownership,entity,query,
stage}.rs; regolith-ir/src/{ledger,budget,conformance}.rs. Skimmed only
(docstring + first section, not full line-by-line): regolith-sem/src/
profile.rs, regolith-ir/src/nodes.rs. Not read: docs/regolith/09, 11,
12 in full (09/11/12 were consulted for waiver/evidence-trust cross-
references via the 07 spec and the waiver.rs/signature.rs
implementations, but not read end-to-end line by line -- a gap in this
audit's own coverage, noted so it is not silently assumed complete).
WO-07..WO-13 bodies were read via their cross-references in the
current source docstrings (each regolith-lower file cites the specific
WO-07..13 cut it depends on) rather than opened as separate files;
their acceptance-criteria text itself was not independently verified
against the WO-19 citations.

## Per-invariant table (INV-1..27)

| INV | Status | Location / gap |
|---|---|---|
| INV-1 Evidence binding | **partial** | `Obligation::content_hash` (regolith-oblig/src/obligation.rs:61) hashes claim+subject_ref+given+hints+sweep, matching the spec's (claim, subject, givens) triple, but has NO field for "registry record hashes" or "model-registry version" (see BE-1). In the current lowering (regolith-lower/src/claims.rs:96-100) `given` is also always empty (see BE-2), so in practice only claim-text and subject snapshot hash vary the key today. |
| INV-2 Ladder safety | **partial** | `WaiveLedger`/`LedgerEntry` (regolith-oblig/src/waiver.rs) never overwrites status, only appends acceptance-shaped entries -- consistent with the mechanism. No rung-1/2/4/5 (todo!/assume!/hint/other overrides) re-keying is wired in regolith-lower yet (claims.rs has no todo!/assume! handling at all -- see BE-3), so the "rungs act upstream of obligation identity" argument is not yet exercised end-to-end. |
| INV-3 Hint droppability | **not-yet** | `Claim.hints`/`Obligation.hints` exist as fields but nothing in discharge.rs reads or excludes them from the margin rule (the toy model ignores hints entirely, which is trivially hint-invariant but not a real test of the property). |
| INV-4 Symmetry soundness | **enforced (structurally)** | `SymmetryGroup::intersect` (regolith-sem/src/symmetry.rs:50-75) collapses any non-representable combination to `Trivial`; `OrbitTable::any_is_legal`/`split_on_break` refuse extension under `Trivial`. Sound by construction. Not yet fed real per-construct contributions in regolith-lower (checks.rs runs over an empty orbit table -- documented cut). |
| INV-5 Ownership finality | **not-yet (documented)** | `BorrowTable::check_conflict`/`merge_analysis` (regolith-sem/src/ownership.rs) implement the borrow-conflict and merge-sign rules correctly and are unit-tested, but `checks.rs` (regolith-lower) never constructs a `BorrowTable` or calls them -- explicitly noted ("ownership/profile/symmetry checks skipped: no structured mating/walk input available yet"). No L4 post-realization re-check exists anywhere (no realizer yet, consistent with Phase-C-not-reached). |
| INV-6 Snapshot isolation | **not-yet (documented)** | `check_sibling_reads` (regolith-sem/src/stage.rs:204) implements the structural sibling-diamond proxy correctly, but is never called from regolith-lower; no `Scope` DAG is built by any pass yet. |
| INV-7 Boundary subsumption | **not-applicable-here** | No boundary/envelope-containment check exists in the audited crates; this is L2 escalation-edge territory not yet reached by WO-19. |
| INV-8 Target additivity | **not-applicable-here** | No target/reserve-region machinery in these crates yet (mech-specific target realization is future work). |
| INV-9 Corner conservatism | **not-applicable-here (per-model obligation)** | Per the spec itself this is a harness-model obligation, not a compiler-side proof; `close_budget` (regolith-ir/src/budget.rs:121-146) does apply outward-rounded worst-case-corner comparison correctly for budgets, which is the one place this crate touches the property. |
| INV-10 Reproducibility | **enforced** | `regolith_util::canon` sorts CBOR map keys canonically and rejects non-finite floats (canon.rs:44-72); `EntityDb::snapshot_hash` explicitly sorts by ascending `EntityId` before hashing rather than using IndexMap iteration order (entity.rs:176-190); `SignatureRegistry::impls_for` uses a stable sort keeping registration order on cost ties (signature.rs:74-82); `close_budget`'s blame-order stable-sorts on ties (budget.rs:156-163). No HashMap use found in any audited output path. |
| INV-11 Monomorphization totality | **not-yet (undocumented gap)** | WO-19's own deliverable list (docs/implementation/WO-19-lowering-pipeline.md:47-48) names "Pass 3 (checks.rs): monomorphization expansion (INV-11)" as an in-scope deliverable, but `checks.rs` (regolith-lower/src/checks.rs) contains **no monomorphization logic at all** -- it only builds an empty `StageGraph` and topo-sorts it. This is a documented-deliverable vs. actual-code mismatch, not merely an opaque-body cut (see BE-4). |
| INV-12 Waiver honesty | **enforced (library)/not-yet (lowering)** | `WaiveLedger::release_blocked`/`check_stale_waivers` (waiver.rs:66-92) implement the stale-match and release-block rules correctly and are unit-tested; no `waive`/`assume!`/`todo!` source construct is parsed or lowered into `LedgerEntry`s anywhere in regolith-lower yet. |
| INV-13 No dead uppers | **not-yet (documented)** | `check_role_kind`/`check_refinement` (regolith-ir/src/conformance.rs) implement role-coverage and promise-narrowing checks correctly, but no pass anywhere (contracts.rs explicitly: "impl...for and connect bodies are opaque islands and are skipped") emits the mandated equivalence/T2/T3 obligation for every impl/extern/import binding. Coverage-insufficiency-is-indeterminate is likewise not wired. |
| INV-14 Trust totality | **not-applicable-here** | No trust-tier comparison code exists in these crates (`Claim.trust_floor` is a bare `Option<String>` with no total-order enforcement anywhere audited). |
| INV-15 Ledger conservation | **partial** | `MechLedger`/`ElecLedger` (regolith-ir/src/ledger.rs) correctly implement over-constraint/contradiction/unfed-flow detection and are unit-tested, but nothing in regolith-lower ever constructs a populated `SystemNode` (matings are always empty per contracts.rs's own doc comment) -- so the ledgers run, but always over empty input in the real pipeline today. |
| INV-16 Converter non-instantaneity | **not-applicable-here** | Behavioral-layer/elec-specific; out of these crates' scope. |
| INV-17 Type soundness | **not-applicable-here** | L1 dimensional analysis lives in regolith-qty/regolith-syntax, not the audited crates. |
| INV-18 Reference determinism | **enforced** | `Query::apply_cardinality` (regolith-sem/src/query.rs:319-363) enforces `.only` exact-one and `.any` orbit-uniformity + canonical (lowest-id) representative selection correctly; cross-owner match without an explicit join is rejected (`has_cross_owner_match`, query.rs:263-269, 367-373) with the ambiguous-selection diagnostic (not a heuristic pick). |
| INV-19 Promises, not actuals | **not-applicable-here** | No L2 solver/escalation-edge machinery audited in this scope. |
| INV-20 Check gating | **partial** | AD-17's per-subject gating principle is not implemented in regolith-lower: `lower()`/`lower_and_discharge()` (lib.rs) run every pass over every file's full diagnostic set with no per-subject exclusion of later passes when an earlier pass produced an error for that subject (there is no subject-keyed skip anywhere in claims.rs/contracts.rs/checks.rs -- every pass runs unconditionally over all `snapshots`). This contradicts AD-17's explicit requirement ("Gating is per subject (INV-20)... a subject with error diagnostics at pass N is excluded from later passes") and WO-19's acceptance criterion ("a file with a parse/L1 error produces zero later-pass span records for that file"). See BE-5. |
| INV-21 Resolution provenance | **partial** | `Resolution::new(Qty, Cause)` (used at entities.rs:161) makes causeless values structurally unrepresentable, matching the type-level guarantee. However `resolution_for_value_source` (entities.rs:142-162) synthesizes a `Cause` by naive substring match on the raw source text (`"derived"`, `"allocated"`, `"in"+bracket`) rather than from actual grammar structure, and defaults everything else (including truly free values) to `Cause::Dfm` -- explicitly flagged in its own doc comment as "best-effort... rather than inventing false specificity." This satisfies INV-21 mechanically (every slot gets *some* Cause) but the Cause is frequently the WRONG one, which is a soundness-adjacent (not just incompleteness) risk for lockfile provenance if consumed as ground truth (documented cut; see BE-6 for suggested containment). |
| INV-22 Foreign-content pinning | **not-applicable-here** | No import/extern/registry-record pinning code in these four crates. |
| INV-23 Region exclusivity | **not-yet (documented)** | `BorrowTable` treats `regions_touched` identically to `modifies` for conflict purposes (ownership.rs:78-83), which is the right mechanism, but (as with INV-5) nothing in regolith-lower ever populates `PredictedDelta.regions_touched` from real source, and no `EntityKind::Region`/`RegionPolicy` construction path exists yet in entities.rs. |
| INV-24 Release-gate totality | **not-applicable-here (orchestrator/Python territory per AD-1)** | The release-gate enumeration is `regolith.orchestrator` scope, out of this Rust-crate audit. |
| INV-25 Coverage honesty | **not-yet** | `Evidence.coverage_bits` field exists and the toy discharge model (discharge.rs:50) always sets it to `1.0` (full coverage) regardless of whether the obligation actually swept anything -- correct for the current always-`sweep: None` reality (claims.rs:102), but will need real wiring once sweep obligations exist; flagged only as not-yet, since single-point obligations are trivially "fully covered." |
| INV-26 Defaults-test compliance | **not-applicable-here (meta/spec-level)** | Out of scope for this crate-level audit. |
| INV-27 File-layout invariance | **enforced (mechanism)/not exercised** | Obligation/snapshot keys never include source paths anywhere audited (`Obligation`, `SnapshotRecord` carry no path field); `parse_sources` preserves caller order rather than re-deriving it from paths. The property is structurally sound but no cross-file-split fixture was found in this scope to confirm end-to-end (WO-19's own INV-27 acceptance fixture is listed as a to-do, not found landed). |

Tally: **enforced: 4** (INV-4, INV-10, INV-18, INV-27-mechanism);
**partial: 8** (INV-1, INV-2, INV-12-library-only, INV-15, INV-20,
INV-21, INV-25 borderline, counted under partial+not-yet split above);
**not-yet: 7** (INV-3, INV-5, INV-6, INV-11, INV-13, INV-23, INV-25);
**not-applicable-here: 8** (INV-7, INV-8, INV-9-mostly, INV-14, INV-16,
INV-17, INV-19, INV-22, INV-24, INV-26 -- 10 total N/A, note table
above has finer per-row detail than this compressed tally; see table
for the authoritative per-INV call).

## Findings

### BE-1 [HIGH] -- Obligation key omits model-registry version entirely

**Citation:** INV-1 (docs/regolith/13-invariants.md lines 33-40):
"obligations are content-addressed over (claim, subject snapshot,
givens, registry record hashes, model-registry version)." Also
regolith/07 sec. 2's example obligation and sec. 4's "Evidence is
content-addressed and cached: unchanged (snapshot, contract,
registry-version) means already discharged."

**Code:** `crates/regolith-oblig/src/obligation.rs` -- the `Obligation`
struct (lines 38-50) has fields `claim, subject_ref, given, hints,
sweep`. There is no field anywhere carrying a harness model-registry
version or identifier. `crates/regolith-lower/src/discharge.rs:30`
keys the `EvidenceCache` purely by `obligation.content_hash()`.

**What is required:** The obligation content address (and therefore
the evidence cache key) must change when the model registry backing
discharge changes version, so a harness model fix/upgrade forces
re-verification rather than silently returning stale cached evidence
computed under the old, possibly-wrong model.

**What the code does:** Nothing in the obligation schema or the cache
key construction references any registry version. A model-registry
bump today would leave every cached `Evidence` entry keyed identically
and reused forever (cache hit), even though the discharge that
produced it may no longer be sound. This is a real (if only just
starting to be reachable) soundness gap in the caching mechanism, not
a documented cut -- neither WO-13-obligations.md's schema nor WO-19's
status note mentions this omission.

**Suggested fix:** Add a `registry_version: String` (or a small
`Vec<(String, String)>` of per-domain registry versions) field to
`Given` or `Obligation`, threaded from the harness's declared registry
version at obligation-construction time, and included in the hashed
struct (it already will be, automatically, once it's a `Serialize`
field on `Obligation`/`Given`). Until the Python harness integration
lands, a placeholder constant field with a tracked TODO is preferable
to a silently-absent one, so the schema shape is stable across the
FFI boundary before real harness data arrives (avoids a second
SCHEMA_VERSION bump later).

### BE-2 [HIGH] -- `given:` is unconditionally empty in the lowering pipeline (undocumented)

**Citation:** INV-1 mechanism (as above) and regolith/07 sec. 2's
worked obligation example, where `given:` carries `material`, `T_env`,
`loads`, `backing` -- load-bearing parts of the key ("any semantic
input to a verdict is part of the key").

**Code:** `crates/regolith-lower/src/claims.rs:96-100` -- every
`Obligation` built by `build_obligations` sets
`given: Given { materials: Vec::new(), loads: Vec::new(), backing:
Vec::new() }` unconditionally, regardless of the claim's actual
predicate text or the declaration's fields.

**What is required:** Per INV-1's own test family ("mutate each key
component; assert cache miss") and WO-19's acceptance criterion ("INV-1
fixture: mutating each obligation key component (claim, subject,
given, record hash) changes the content hash"), a change to a
material/load/backing declaration that a claim's `given:` should
capture must change the obligation's content hash.

**What the code does:** Because `given` is always the same empty
value, two claims that differ ONLY in their governing materials/loads
(e.g. two identical `require` predicates evaluated for different
declared materials) will currently hash to the SAME obligation and
therefore share cached evidence -- exactly the INV-1 failure mode the
invariant exists to prevent ("no source edit can re-label existing
evidence"). Unlike the sweep-domain omission (which claims.rs's module
doc explicitly calls out: "every obligation here is a single-point
obligation... see the WO-19 partial-lowering note"), the `given`-always
-empty fact is not mentioned anywhere in claims.rs's doc comment or in
WO-19-lowering-pipeline.md's "RECORDED PARTIAL" status note (which only
names `resolutions=0`). This makes it an undocumented divergence rather
than a scoped, named cut, even though the underlying cause (no
structured material/load grammar surface yet) is legitimate.

**Suggested fix:** At minimum, extend claims.rs's module doc comment
and WO-19's status note to name this cut explicitly (parity with the
sweep-domain note), so a reader auditing INV-1 doesn't have to
discover it by reading the field initializer. Functionally, thread
whatever structured material/load fields the current WO-05 grammar
DOES expose (e.g. a declaration's own `Field`s, already captured in
`Entity.measures` per entities.rs) into `given.materials`/`given.loads`
rather than leaving them empty, so the obligation key is sensitive to
at least the entity's own measures even before the richer domain-body
lowering lands.

### BE-3 [MEDIUM, known-cut-adjacent] -- Check gating (INV-20) not implemented per-subject

**Citation:** AD-17 (00-architecture.md lines 472-474): "Gating is per
subject (INV-20): a subject with error diagnostics at pass N is
excluded from later passes; the pipeline always completes for
unaffected subjects." WO-19 acceptance: "a file with an L1 unit error
must produce zero kernel/solver invocations" / "zero later-pass span
records for that file."

**Code:** `crates/regolith-lower/src/lib.rs` `lower()`/
`lower_and_discharge()` -- passes run unconditionally: `entities::
build_entities(&parsed)` runs over every parsed file regardless of
that file's own parse diagnostics; `checks::run_checks(&snapshots)`,
`contracts::build_contract_ir(&parsed, &snapshots)`, and `claims::
build_obligations(...)` likewise take the full `snapshots`/`parsed`
sets with no per-subject filtering keyed off earlier-pass diagnostics.

**What is required:** A subject (declaration/scope) that failed an
earlier pass must be excluded from later passes.

**What the code does:** There is no subject-keyed skip logic anywhere
in the four pass functions; every declaration flows through every pass
regardless of earlier errors on that same declaration. Given the
current lowering only produces per-decl entities and no real semantic
checks run yet (checks.rs is a documented stub), this has limited
practical bite today, but it means the INV-20 gating mechanism itself
does not exist in regolith-lower at all -- it will not "just start
working" once richer grammar lands, the way sibling documented cuts
are designed to (e.g. `close_budget` in contracts.rs, which is real
code that correctly reports nothing yet). WO-19's own status note does
not flag this omission; it should, or the gating should be added
before WO-19 is marked done (its own acceptance criteria requires it).

**Suggested fix:** Track a per-subject (declaration name) "has error"
set threaded from `EntitySnapshots.diagnostics`/parse diagnostics, and
filter `snapshots.scopes`/claim iteration in `checks.rs`/`contracts.rs`
/`claims.rs` against it before each subsequent pass.

### BE-4 [MEDIUM, undocumented deliverable gap] -- Monomorphization expansion (INV-11) listed as a WO-19 deliverable but entirely absent

**Citation:** INV-11 (13-invariants.md lines 155-162): "Every static
check runs at every instantiation point of every discrete domain."
WO-19-lowering-pipeline.md line 47-48 lists as deliverable 3:
"monomorphization expansion (INV-11), then queries/ownership/stages/
profiles/symmetry per instantiation point."

**Code:** `crates/regolith-lower/src/checks.rs` -- `run_checks` builds
an empty `StageGraph`, topo-sorts it, and returns; there is no
monomorphization-expansion code, data structure, or even a stubbed
call site (unlike, say, `close_budget`, which IS called with an empty
contribution list as a documented "real code, trivially passes"
placeholder). Monomorphization is not represented at all, not even
vacuously.

**What is required:** Per WO-19's own deliverable list, some
recognizable seam for discrete-domain expansion should exist (even a
documented no-op over the currently-unavailable domain data, mirroring
the `close_budget`/`StageGraph::new()` pattern elsewhere in the same
file).

**What the code does:** No seam exists; the doc comment at the top of
checks.rs explains why ownership/stage/symmetry/profile checks are
vacuous but never mentions monomorphization by name, and the deliverable
is simply missing from the implementation.

**Suggested fix:** Either add a documented vacuous seam (consistent
with the file's own stated pattern) or update WO-19's status note to
explicitly list monomorphization expansion as an outstanding deliverable
(it currently reads only "needs the residual grammar... plus a pass to
quiet spurious diagnostics," which undersells this specific gap).

### BE-5 [MEDIUM, documented] -- Resolution Cause inference is a text heuristic, not structural

**Citation:** INV-21 (13-invariants.md lines 278-288): "the resolver
API cannot construct a resolved value without a Cause... causeless
values are unrepresentable."

**Code:** `crates/regolith-lower/src/entities.rs`
`resolution_for_value_source` (lines 142-162): infers `Cause` from
`text.contains("derived")` / `"allocated"` / bracket-shaped `"in"`
substrings, defaulting everything else (including real `free`
declarations) to `Cause::Dfm`.

**What is required:** The Cause should reflect which rule/obligation/
planner actually resolved the value.

**What the code does:** This is honestly self-documented ("best-effort,
clearly-documented mapping satisfying INV-21 mechanically... rather
than inventing false specificity") and IS a genuine documented cut, not
a silent bug -- included here as MEDIUM (not LOW) only because a
default-to-`Dfm` for the `free` case is arguably actively misleading
(a truly free/unresolved variable being mis-tagged as "DFM-resolved" in
a lockfile is a more specific wrong-data risk than the other two
branches, which at least keyword-match something real). Recommend a
distinct `Cause` variant (or a "not yet structurally derivable" marker)
for the untagged/`free` fallback rather than reusing `Dfm`, so
downstream consumers cannot mistake "we don't know" for "a DFM rule
decided this."

### BE-6 [LOW, documented] -- INV-13 (no dead uppers) not wired; impl/extern/import obligations never emitted

**Citation:** INV-13 (13-invariants.md lines 175-185).

**Code:** `crates/regolith-lower/src/contracts.rs` -- doc comment
explicitly: "impl...for and connect bodies are opaque islands and are
skipped." `ContractGraph.impls`/`matings` are always empty (lines 39,
34).

**What is required:** A conformance obligation (equivalence/T2/T3) for
every impl/extern/import binding.

**What the code does:** No such obligations are ever constructed
because impl/connect bodies are not parsed structurally yet. This is a
cleanly documented, in-scope WO-19 cut (the underlying `check_role_kind`
/`check_refinement` machinery in regolith-ir is correctly implemented
and unit-tested; it is simply never invoked from the pipeline yet).
LOW because it is fully disclosed and gated on grammar work already on
record (WO-05's opaque-island list).

### BE-7 [LOW, documented] -- Ownership/borrow/region/symmetry/stage checks run over structurally-empty input

**Citation:** INV-5, INV-6, INV-23 (13-invariants.md).

**Code:** `crates/regolith-lower/src/checks.rs` (whole file) --
explicitly documents that ownership/profile/symmetry checks are
skipped for lack of structured mating/walk input, and that this is
"real code that correctly reports nothing yet, not a stub."

**What is required:** These invariants need real per-construct
`PredictedDelta`s, `BorrowTable`s, and orbit contributions flowing from
parsed source.

**What the code does:** The underlying regolith-sem primitives
(`BorrowTable::check_conflict`, `check_single_driver`, `OrbitTable`) are
correctly implemented and unit-tested in isolation, but zero real data
reaches them from the current lowering. LOW severity: fully and
accurately self-documented, matches WO-19's stated scope, and the
"moment a later WO structures more of the grammar, real diagnostics
start flowing with no pipeline change" design claim appears to hold up
on inspection (the call sites and data shapes are already correct,
just fed empty inputs).

## Genuine bugs vs. known cuts

- **Genuine, undocumented (fix before closing WO-19 / before relying on
  the evidence cache for anything real):** BE-1 (model-registry version
  missing from the key -- schema gap, will bite the moment a second
  harness model version exists), BE-2 (given always empty, not named in
  WO-19's own status note), BE-4 (monomorphization deliverable silently
  absent rather than vacuously stubbed like its siblings), BE-3 (INV-20
  gating mechanism absent, contradicting the WO's own acceptance
  criterion).
- **Documented, in-scope cuts (correctly disclosed, lower urgency):**
  BE-5 (Cause heuristic, self-documented), BE-6 (INV-13 obligations,
  contracts.rs doc comment), BE-7 (ownership/symmetry/stage checks over
  empty input, checks.rs doc comment).
