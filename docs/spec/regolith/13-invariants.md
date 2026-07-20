# The Invariant Ledger

> Regolith spec. Added in cycle 4. Every load-bearing guarantee the
> languages make, with its enforcing mechanism and the argument for why
> it holds. This ledger is **normative**: a spec change that breaks a
> proof argument must update this file in the same change, and WO-17
> turns each invariant into an executable test family. "Provably
> invariant" here means: the argument reduces to construction
> (something the checker computes), to content addressing, or to a
> stated per-model obligation -- never to designer discipline.

Format: statement / mechanism / argument / test family.

Index by theme:

- *Foundation*: INV-17 type soundness, INV-18 reference determinism,
  INV-6 snapshot isolation, INV-23 region exclusivity, INV-5
  ownership finality, INV-11 monomorphization totality
- *Contracts*: INV-19 promises-not-actuals, INV-7 boundary
  subsumption, INV-13 no dead uppers, INV-8 target additivity,
  INV-15 ledger conservation
- *Evidence*: INV-1 evidence binding, INV-9 corner conservatism,
  INV-25 coverage honesty, INV-4 symmetry soundness, INV-14 trust
  totality, INV-16 converter non-instantaneity, INV-28 evidence
  attribution
- *Human redirects*: INV-2 ladder safety, INV-3 hint droppability,
  INV-12 waiver honesty, INV-24 release-gate totality, INV-29 rule
  totality
- *Build*: INV-20 check gating, INV-21 resolution provenance,
  INV-22 foreign-content pinning, INV-10 reproducibility, INV-27
  file-layout invariance, INV-26 defaults-test compliance (meta)

## INV-1 Evidence binding

**Every evidence item is bound to the exact obligation it discharged.**
Mechanism: obligations are content-addressed over (claim, subject
snapshot, givens, registry record hashes, model-registry version);
evidence is keyed by obligation hash. Argument: any semantic input to
a verdict is part of the key, so no source edit can re-label existing
evidence -- editing boundary truth, materials, or contracts produces a
*different* obligation with no evidence yet. Test: mutate each key
component; assert cache miss.

## INV-2 Ladder safety

**No override mechanism converts `violated` into `discharged`.**
Mechanism: rungs 1/2/4/5 act upstream of obligation identity (they
change inputs or choices, hence the obligation hash -- INV-1); rung 3
is verdict-invariant (INV-3); rungs 6/7 attach **acceptance records**
that reference the evidence hash and never modify status -- the ledger
and build report always show true status plus acceptance. Argument:
by case analysis over the closed list of rungs; the list is closed
because `12-overrides-and-hints.md` is the single home for redirect
mechanisms. Test: per rung, apply the override to a violated claim;
assert reported status unchanged (or obligation re-keyed).

## INV-3 Hint droppability

**For a fixed resolved design, verdicts are invariant under removal of
all `@hint`s; `policy: prefer` only reorders exploration among
claim-satisfying candidates.** Mechanism: hints are passed to models
as search guidance only; the model API gives them no role in domain
validity or coverage claims; preferences act in candidate enumeration
order, and every candidate still faces full verification. Argument:
anything load-bearing must arrive as a checked fact (entity DB), a
registry record, or an `assume!` -- the hint channel structurally
cannot carry it. Test: run discharge with hints stripped; diff
verdicts (cost may differ).

## INV-4 Symmetry soundness

**Entity-DB symmetry is under-approximate: a false symmetry is never
asserted. Orbit-based discharge extension is legal only when the
obligation's givens are invariant under the orbit's group.**
Mechanism: the artifact group is the intersection of per-construct
*declared* contributions (conservative by construction); the
discharging model must check givens-invariance (or use the
orbit-worst-case envelope) before extending one instance's result
across an orbit. Argument: intersection of sound under-approximations
is a sound under-approximation; the givens check closes the
asymmetric-load hole (a symmetric bolt circle under a moment does not
license verify-one). Test: symmetric subject + asymmetric load must
refuse extension.

## INV-5 Ownership finality

**Single ownership and borrow verdicts hold on the realized artifact.**
Mechanism: L3 checks run on per-construct predicted deltas; constructs
declared data-dependent are re-checked at L4; the mandatory
post-realization pass verifies all predictions and blames the feature
class (its pack) on mismatch. Argument: every path to L5/L6 passes the
L4 verification gate, so no evidence is ever emitted against a
realization whose ownership story diverged from prediction. Test:
a deliberately lying feature-class delta must fail at L4 with pack
provenance.

## INV-6 Snapshot isolation

**No statement observes a sibling's effects.** Mechanism: sibling
exports are not name-resolvable within the scope; queries evaluate
against the scope-entry snapshot by definition; profile exports are
placeless until feature-anchored (closing the laundering hole);
datums are immutable captures. Argument: all reference channels
(names, queries, datums, profile exports) individually enforce
entry-snapshot semantics; there is no other channel. Test: each
channel attempted against a sibling; all must fail statically.

## INV-7 Boundary subsumption

**Evidence transfers into any context whose boundary is contained in
the proven one.** Mechanism: boundary entries are, by definition,
tolerated envelopes; the L2 check requires enclosing subset of
imported per shared quantity. Argument: a claim discharged for all
environments in E holds for all environments in any subset of E --
monotone by construction; the phrasing rule (envelopes, not point
conditions) is what makes one containment direction uniformly safe.
Test: widen an enclosing ambient past an import's; must fail at L2.

## INV-8 Target additivity

**Contract-level base evidence is always valid under a target;
realization-level base evidence is reused only when the base
realization is unchanged -- and that is guaranteed by construction
when target content realizes inside reserved regions only.**
Mechanism: targets cannot modify base contracts (syntactic); target
realization is constrained to reserves with the base realization
reused verbatim; content addressing (INV-1) keys base evidence to the
base snapshot. Argument: if the base snapshot byte-matches, its
evidence keys match; if a target perturbs it, keys differ and
re-verification is forced -- reuse is never silent. Test: a target
whose added routing would cross a base region must be rejected; a
base-perturbing target must invalidate exactly the touched subjects.

## INV-9 Corner conservatism

**Every check is evaluated at its own worst-case corner.** Mechanism:
corner maps are part of each model's contract; interval arithmetic in
budgets/ledgers is outward-rounding. Argument: this one reduces to a
*per-model obligation*, not a global proof -- a model with a wrong
corner map is unsound, which is why corner maps are registry content
subject to versioning/evidence, and why the model test family (WO-17)
sweeps corners against the model's selection. Honesty note: this is
the weakest link in the chain and is flagged as such deliberately.

## INV-10 Reproducibility

**Given (source, lockfile, tool versions): all decisions and evidence
identities are bit-reproducible; numerical evidence values are
reproducible per each model's declared `deterministic:` flag, with
seeds/settings folded into evidence hash inputs otherwise.**
Mechanism: canonical `any` representatives, pinned solver branches,
lockfile-pinned resolutions, content addressing. Argument: every
nondeterminism source is either pinned (decisions) or declared and
hashed (numerics) -- so identity never lies even where values wobble.
Test: double-build diff on lockfile + evidence keys.

## INV-11 Monomorphization totality

**Every static check runs at every instantiation point of every
discrete domain (integers, enums, variants).** Mechanism: discrete
domains expand before L3 checks; a source must be valid for the whole
domain or the domain must shrink. Argument: expansion is exhaustive by
construction; variants are externally-chosen so no point is skippable.
Test: a per-point-only failure must fail the build.

## INV-12 Waiver honesty

**A waiver never alters evidence status; its match set is
lockfile-recorded; growth of the match set surfaces in the diff and
build report; a waiver matching nothing, or past its `expires:` date,
is an error.** Mechanism: acceptance records (INV-2) + lockfile
materialization + the stale/expiry checks. Argument: every waiver
consequence lands on an auditable surface; silent absorption of new
failures is prevented by the recorded-match-set diff. Test: introduce
a second failure under an unscoped waiver; assert warning naming it.

## INV-13 No dead uppers

**When both an upper contract and a lower realization are written, a
conformance obligation exists between them.** Mechanism: the compiler
emits equivalence/T2/T3 obligations by construction for every
impl/extern/import binding; insufficient coverage is `indeterminate`
(release-gated), never a pass. Argument: there is no code path that
registers a lower-level realization without an upper binding except
authoring *only* the lower level (where the contract is authored there
-- nothing is shadowed because nothing else exists). Test: a spec
contradicted by its hand-written impl must fail equivalence.

## INV-14 Trust totality

**Every evidence item -- registry records, overrides, test reports,
deviations -- carries a trust tier, and trust floors compare totally.**
Mechanism: the evidence clause is mandatory at every entry point
(records, overrides, deviations); tiers form a total order
(certified > tested > community). Argument: by construction of the
entry points; F54 closed the deviation gap. Test: a deviation below
the claim group's floor must stay release-gated.

## INV-15 Ledger conservation

**Every conservation ledger (DOF, sketch DOF, driver/load,
domain-crossing, flow, intent-realization, terminal) is a complete
accounting: declared items sum against a declared free set, and
nothing participates outside the ledger.** Mechanism: participation is
syntactic (every mating declares `dof:`, every walk entity its
constraints or declared free variables, every port a direction, every
flow endpoints, every workload its `realizes`); the ledgers run at
L2/L3 before anything expensive.
Argument: completeness is enumerability of declared constructs -- there
is no undeclared way to remove a freedom, drive a net, or serve an
intent. Test: one fixture per ledger with a deliberate leak.

## INV-16 Converter non-instantaneity

**No algebraic loop crosses the continuous/discrete boundary.**
Mechanism: every converter port kind samples the pre-instant value and
applies updates post-instant (ZOH) -- a delta by type, not by
analysis; direct reads of continuous quantities inside clocked bodies
are compile errors. Argument: any cross-boundary cycle contains a
converter, and every converter contains a delta, so no zero-delay
cycle exists; within-domain combinational cycles are separately
rejected (acyclicity check). Test: comparator-feeds-own-threshold
fixture must be structurally legal and loop-free in semantics; a
combinational cycle must fail statically.

## INV-17 Type soundness

**No dimensionally inconsistent expression, no `==` on a continuous
quantity, and no interval/range confusion survives L1.** Mechanism:
dimensional analysis at parse time -- including the logarithmic-view
reference algebra (a sum of log terms is legal iff at most one
referenced term remains after cancellation; `dBm + dBm` dies at L1,
regolith `02` sec. 5a); the equality ban (applying to the linear
quantity under any log view); `[a, b]` (closed interval) and
`[i .. j]` (half-open positional range) are distinct,
non-interconvertible types. Argument: all are total functions of the
typed AST -- there is no untyped numeric slot (the value-source
grammar covers every position), and log views store linear so no
second numeric domain exists. Test: one fixture per violation class,
including the two-reference log sum; all must die at L1 with E01xx.

## INV-18 Reference determinism

**Every resolved reference has exactly one interpretation.**
Mechanism: cardinality typing (`Entity` / `Set[;n]` / `Set` with
`.all/.only/.any` intents); `any` legal only on intact orbits with a
canonical lockfile-recorded representative; cross-owner selection
requires explicit joins; ambiguity is E0301, never a heuristic pick.
Argument: the resolver either produces a unique answer consistent with
the declared cardinality or fails -- there is no tie-break path; `any`
is unique-up-to-orbit and then pinned. This is mantra 1 as a checkable
property. Test: over/under-match, broken-orbit `any`, cross-owner
without join -- all must fail constructively.

## INV-19 Promises, not actuals

**No system-level verdict depends on an artifact's internals except
through a declared escalation edge.** Mechanism: the L2 solver reads
contract IR only (promises, connection models, boundary); escalations
(`model=fea_contact`, `stiffness=measured`, `spice_extracted`) are
explicit opt-ins recorded as build-graph dependency edges. Argument:
by construction of the L2 input set -- artifact internals are not
reachable from it; the escalation edge set is syntactically closed.
This is what makes artifact edits leave promise-backed system evidence
untouched (with INV-1). Test: edit an artifact internal without
contract change; assert zero system-obligation re-runs absent
escalation edges.

## INV-20 Check gating

**Nothing expensive runs until everything cheaper has passed for the
affected subjects.** Mechanism: the pipeline gates L(n) on L(<n)
verdicts per subject (static before structural before physical);
realizers and the harness are invoked only by the orchestrator, which
enforces the gate. Argument: single invocation path + per-subject
gating; there is no user-reachable "just simulate it" entry that skips
the static tiers. Test: a file with an L1 unit error must produce zero
kernel/solver invocations (observable via pass logging).

## INV-21 Resolution provenance

**Every number the designer did not write literally appears in the
lockfile with its resolving cause.** Mechanism: the resolver API
cannot construct a resolved value without a `Cause` (dfm/drc,
obligation, budget, topology, planner, extern, derived-intent, policy
annotation); the lockfile writer serializes all of them. Argument: by
construction of the resolution type -- causeless values are
unrepresentable (WO-04 encodes this). This is the defaults test's
third prong as a type-system fact. Test: golden lockfiles enumerate
every non-literal slot in the examples corpus.

## INV-22 Foreign-content pinning

**All foreign content -- imports, externs, registry records, format
readers, toolchains -- is hash-pinned; drift is an error, never a
silent rebuild input.** Mechanism: content addressing at every entry
point (import stages, `extern(ref)`, record revisions, `formats`
packages, `toolchain:` pins); the build compares against lockfile
pins. Argument: the entry-point list is closed (INV-1's key components
plus L0 imports); a changed file fails the pin comparison before
anything consumes it. Corollary (cycle 8, with the registry hosting
model, `11` sec. 10): no registry source, mirror, or fetch path is
part of any key -- hosting can affect *availability*, never meaning;
a poisoned mirror can only produce this invariant's loud drift error.
Test: mutate an imported STEP/Verilog/plan file without updating pins;
build must halt naming the drift; serve a tampered archive under a
pinned hash; fetch must fail the pin comparison.

## INV-23 Region exclusivity

**Nothing enters an owned exclusion region without a declared overlap
join.** Mechanism: regions are first-class owned entities with
exclusion/arbitration policy; placement, routing, features, and memory
partitions all pass the same region-intersection check in the
ownership tier; overlap-where-permitted is an explicit join
declaration. Argument: every spatial/resource occupancy is an entity
creation or modification, and all of those pass the ownership checker
-- there is no occupancy channel outside the entity DB. Test: route
into a keepout, feature into a fixture volume, partition overlap --
all must fail as borrow conflicts, not post-hoc rule hits.

## INV-24 Release-gate totality

**A `--release` build's report contains zero unaccepted violated or
indeterminate obligations, and every acceptance is listed.**
Mechanism: the set of failure-acceptance mechanisms is closed
(`todo!`, `assume!`, `waive`/deviations, per-item CLI
acknowledgments); all are ledgered; the release gate enumerates the
ledger against the evidence set. Argument: INV-2 guarantees no
mechanism hides a failure by re-labeling; this invariant guarantees
the *gate* sees every remaining failure -- together: a green release
means "proven, or explicitly accepted by a named human reason, with
nothing in between." Test: each acceptance mechanism exercised;
release report must list it; an unaccepted violation must fail the
release build. WO-98 completes the gate half: the Python release gate
now CONSUMES the payload's `WaiveLedger` (the Rust ledger was audited
on one side of the FFI only) -- an evidence-carrying waiver whose
evidence meets the target claim's trust floor (INV-14) is an accepted
DEVIATION counted distinctly (`GateCounts.accepted_deviation`, never
folded into discharged); bare waivers / `assume!` / `todo!` keep
refusing; expired waivers behave as absent and error; `by doc(<memo>)`
resolves to a hash-pinned in-project engineering memo conferring
community tier (D207). See
`tests/invariants/test_inv_24_release_gate_totality.py`
(deviation-passes-and-is-listed, evidence-removed-refuses,
trust-floor-exceeding-cannot-be-memo-waived, expired-refuses,
ship-package-carries-the-ledger).

## INV-25 Coverage honesty

**Evidence states the coverage it achieved, and partial coverage never
reads as full.** Mechanism: swept obligations carry their domain;
evidence carries `coverage:` (`corners`, `grid(k)`, `analytic`, per
declared model shape such as monotonicity -- a registry-versioned
model property, not a hint); extension across instances only via
INV-4. Argument: the discharge rule compares claimed coverage against
the obligation's domain; a gap yields `indeterminate` by the margin
rule's domain check. Test: a sweep discharged at corners by a model
without declared monotonicity must come back indeterminate.

## INV-26 Defaults-test compliance (meta-invariant)

**Every default behavior in either language is conservative, local in
effect, and lockfile-materialized.** Mechanism: this is an invariant
*over the spec itself*: the defaults are enumerable (free-variable
resolution, implicit `by spec`, local tolerance allocation, canonical
`any`, eager candidate acceptance, derived workloads); each must cite
its three prongs where defined. Argument: enforced editorially at spec
time and executably at test time -- WO-17 maintains the enumeration,
and each default gets a spurious-failure-not-silent-pass test.
Test family: per default, construct the case where the default is
wrong; assert the failure mode is loud.

## INV-27 File-layout invariance

**For a fixed set of top-level declarations and pinned dependencies,
verdicts, resolutions, and evidence identities are invariant under how
the declarations are distributed across source files.** Mechanism: all
cross-declaration references are by name through imports; resolution
binds to declaration identity, never file identity; obligation keys
(INV-1) contain claims, subject snapshots, givens, and record hashes
-- no source paths (extern/import *content* is hashed, and its path is
part of the declaration itself, not of which file holds it). Argument:
no consumer of a declaration can observe its file -- the post-import
namespace is the same flat declaration set however it is split, and
every downstream key is content-derived. This is what makes file
organization a pure team-workflow choice (`11-packages-and-stdlib.md`
sec. 9). Test: split a golden example into two files joined by an
import; assert identical verdicts, lockfile rows, and evidence keys.

## INV-28 Evidence attribution

**Computed evidence is attributable: a solver signs the evidence it
produces, the consumer verifies that signature against its own key set,
and a claim's trust floor applies to computed evidence exactly as it
does to records (INV-14) -- an unverifiable signature is indeterminate,
never a silent pass.** Mechanism: an `Attestation` (regolith-oblig
schema) is an ENVELOPE whose signature covers the evidence's AD-18
content address, not a hash input; verification (`harness/attest.py`)
is a total three-valued function -- `Valid(tier)` against a designated
magnetite key, `Unsigned` (the `community` floor) when absent, or
`Invalid(reason)` when present but unverifiable -- and the release gate
refuses any discharged result whose claim floor exceeds its conferred
tier. Argument: the signature binds to the content address, whose
collision resistance is blake3's, so it cannot be transferred to other
evidence; the tier is decided entirely by the consumer key set, so
storage/hosting confers nothing and a re-designation flips the earned
tier without re-signing (the INV-14 argument, unchanged); the
invalid-signature path is total because both non-`Valid` arms map to
explicit evidence states (`community` and indeterminate), so no signed
result is ever silently accepted. Test: a signed round trip earns
`Valid(tested)` and keys identically with and without its attestation;
a tampered byte yields `Invalid` -> indeterminate, distinct from
violated; a `certified` floor over a `tested`-designated key is
release-gated until the key is re-designated `certified`.

## INV-29 Rule totality

**No attached rule is silently skipped or loosened: every rule of
every attached pack either evaluates to a verdict (a violation is an
E0601 diagnostic AND a lowered obligation), defers to an obligation
naming what blocks it, or fails compilation on its own definition --
and no mechanism weakens a rule in place.** Mechanism: attachment is
union with qualified-name collision as an error (E0602,
`regolith-lower/src/rules.rs::check_rule_packs`); the one evaluator
(`regolith-lower/src/rule_engine.rs`) classifies each attached rule
per D-E -- statically evaluable predicates get verdicts in
`lower.checks`, while unevaluable ones (unpopulated domains, query
filters, realized facts, out-of-subset shapes) produce DEFERRED
outcomes that `lower.claims` lowers to indeterminate obligations whose
givens name the blocking fact; a `forall`-scoped predicate naming a
field outside its domain's declared measure vocabulary is a compile
error on the rule (E0603), and an attached resolver whose target is
never `free` is E0604. Argument: the evaluation function is TOTAL over
attached rules by construction -- its match arms are exactly
{verdict, deferral, definition error} and none is empty-bodied; a
deferral is an obligation, so the release gate (INV-24) refuses it
until discharged; loosening is unrepresentable because composition has
no priority arithmetic (union + collision error), severity has no
third level, and the only override path is the waive ladder, which by
INV-2 produces acceptance records and can never rewrite a verdict.
Test (tests/invariants/test_inv_29_rule_totality.py): a satisfied
attached rule passes silently while its violated twin yields E0601
plus a waivable obligation; a duplicate qualified name is E0602 (never
a shadowing pick); an unevaluable-domain rule appears as an obligation
naming its domain rather than vanishing; and the obligation set is
byte-identical with and without a waive of the violated rule.

## INV-30 Optimization reproducibility and attribution

**Given identical sources, pinned records, seed, and evaluation budget,
the optimization engine (`regolith.orchestrator.optimize`, AD-30)
produces an identical winner and a byte-identical `OptimizationTrace`;
every pinned winner's lockfile row carries `cause: optimize(<objective>,
trace=<digest>)` naming the exact trace that justifies it.** Mechanism:
both drivers are pure, seeded proposers over ordered (`Vec`/`tuple`,
AD-6) domains -- `optimize_discrete` enumerates each `ChoicePoint`'s
candidates in DECLARED order with a deterministic depth-first
backjumping walk, and `optimize_continuous`'s `golden_section`/
`nelder_mead` strategies derive their entire search path (including
initial-simplex jitter) from the caller's `seed` via one in-house,
platform-independent PRNG (`_splitmix64`, no OS entropy, no
third-party library) -- so two runs with the same seed/budget/domain
call the injected `Evaluator` on the EXACT same assignment sequence.
Every candidate the driver reaches is evaluated ONLY through that
injected evaluator (AD-22's private-scoring-path ban: the engine never
computes an objective itself), which is itself INV-10's pipeline
evaluation; the resulting `OptimizationTrace` records that sequence in
evaluation order (never resorted), so its JSON serialization is a pure
function of the same inputs. The trace is persisted through
`PayloadStore.put`'s fresh blake3 digest of those JSON bytes (the same
content-addressing argument `EvidenceStore`/`NogoodCache` already make
for their own state), and `winner_lock_row` builds the `cause:
optimize(...)` string directly from that stored digest plus the
winning `CandidateEntry`'s own assignment -- so the attribution string
is derived data, never a second hand-authored identity that could drift
from the trace it names. `--resume` replays the prior trace's
candidates by call order (`_ReplayEvaluator`) rather than re-deriving
them, so a resumed run's shared prefix is not just equal but the VERY
SAME serialized bytes, and spends zero additional evaluator calls.
Argument: determinism reduces to "the driver's call sequence to
`Evaluator` is a pure function of (domain, seed, budget)" (shown per
driver above) composed with "the evaluator's own output is a pure
function of its argument" (INV-10, inherited unchanged since `optimize`
calls the identical `build`/`staged_build` + discharge path any other
tier uses) composed with "the trace's serialization is a pure function
of the evaluation sequence" (an ordered `list` field-for-field, no
`dict` iteration anywhere in `OptimizationTrace`); the composition of
three pure functions is pure, so the same inputs give the same trace
bytes and hence the same digest and the same `cause:` string.
Attribution follows from the digest being computed from the ACTUAL
persisted trace bytes (never a value asserted independently of what
was stored), so the lockfile row can always be checked against the
payload store's own content. A `strategy_version` bump is itself a
declared trace field (not silently absorbed): replaying an old seed
against a newer strategy version honestly produces a different trace
rather than a false claim of reproducing the old one.
Test family (`tests/orchestrator/test_optimize.py`): two
`optimize_discrete`/`optimize_continuous_golden_section`/
`optimize_continuous_nelder_mead` runs with identical arguments and
seed produce byte-identical `model_dump_json()` traces; a different
seed produces a different trace while both remain feasible; `--resume`
at a partial budget followed by completion makes zero additional
evaluator calls for the covered prefix and the shared prefix's
candidates are byte-identical to the interrupted run's; budget
exhaustion returns `termination=budget_exhausted` with the
best-feasible-so-far winner rather than raising; an all-infeasible
domain returns `termination=infeasible` with `winner=None` and refuses
to produce a `cause:` row (`winner_lock_row` returns `Err`).

## INV-31 Shipped sheets are legible by construction

**Every sheet artifact `DrawingsBackend.produce` ships (mech/civil/
fluid drawings, opt traces, SI tables; the `contract_graph` and
`harness` diagram kinds are the F142 carve-out -- loudly warned, not
yet gating, until their shared layered-label layout is collision-free)
satisfies charter 41's sheet grammar: no annotation or dimension's
MEASURED placement crosses the sheet's printable frame, no two
annotations' measured bboxes overlap, every title-block field is a
named label+value pair, and no table cell carries pipe-delimited prose
-- a violation REFUSES the ship with a named diagnostic
(`assert_ship_ready`, `backends/drawings/audit.py`) rather than
shipping and merely warning (WO-123, D238.1).** Mechanism: the renderer (`renderer.py`/
`renderer_pdf.py`) and the audit (`audit.py`) share ONE geometry home
-- `measure_text_width_mm`/`wrap_to_width`/`fit_text` (deterministic,
never-under-estimating text measurement) and `DimensionGeometry`
(extension line, dimension line, arrowhead, clamped text position),
both defined once in `renderer.py` and imported by both call sites, so
the audit's clip/overlap check is measuring the EXACT same bbox the
renderer is about to draw -- there is no second, drifted layout
mechanism a defect could hide behind (the F135 root cause: the old
audit's `no-overlapping-annotations` rule compared raw `anchor` points,
not rendered geometry, so two annotations with distinct anchors but
overlapping measured text sailed through). `DrawingsBackend.produce`
calls `assert_ship_ready(model, subject, style)` for every configured
drawing spec BEFORE any file for that subject is rendered; a failing
rule returns `Err(BackendError)` (never raises -- L6 ship failures are
error VALUES, `~/.claude/refs` ground rule / regolith/07 sec. 6), which
propagates through `DrawingsBackend.produce`'s own `Result` return and
therefore through `regolith ship`'s existing all-backends-Ok gate
(the SAME mechanism `release_gate` already uses for obligation
discharge and trust floors -- INV-31 is one more named condition on
that gate, not a second one). Determinism (AD-6/INV-10) holds because
`fit_text`/`DimensionGeometry` are pure functions of
`(DrawingModel, StyleRecord)` with no wall-clock or host input, so the
same model+style always measures (and therefore audits) identically.
Argument: soundness reduces to "the audit measures the renderer's
actual output geometry" (shown above: literally the same functions,
called with the same arguments) composed with "a `Result::Err` from
any backend refuses the whole ship" (existing WO-25 framework
property, unchanged by this WO) -- so a sheet that would clip or
overlap on the page can only reach a shipped package if BOTH the
renderer's own placement math and the audit's independent geometric
recomputation over the SAME model agree it does not, which for pure
functions over identical inputs is definitionally the same computation
twice; a real defect cannot pass one and fail the other silently.
Test family (`tests/backends/test_audit.py`,
`tests/backends/test_drawings.py`): the F135 negative fixtures (a
`DrawingModel` whose annotation text cannot fit between its anchor and
the printable frame even at the floor height; two annotations whose
measured bboxes intersect without sharing an anchor; a table cell built
from `"|".join(...)`; a dimension whose text admits no in-bounds
placement) each make `run_drafting_rules` report exactly the WO-123
rule that catches it and make `assert_ship_ready` return the named
`drafting_audit_refused` error value; a clean sheet passes the gate;
two audit runs over the same model agree rule-for-rule (the purity
leg); and `tests/backends/test_drawings.py`'s producer/renderer suites
hold every current producer's output to the same rules end-to-end
through `DrawingsBackend.produce`.

## INV-32 Tap-map/artifact agreement

**Every row of a debug package's tap map (`harness/tap_map.json`)
corresponds to a tap actually present in the emitted debug artifacts,
and every tap emitted into any artifact appears in the map -- a
shipped debug package never overstates or understates its own
hardware (charter 40 secs. 3, 5; D237; AD-38).** Mechanism: the ship
path (`regolith.backends.ship`) derives the tap set ONCE
(`_prepare_debug_emission`: payload claim-named candidates + explicit
spec-block taps, capacity from the ONE `tap_header` record), threads
it onto the same `BackendInputs` every backend serializes, and then
runs `regolith.backends.debug_taps.check_tap_agreement` over the
EMITTED bytes: the map's allocated `(channel, target_path)` rows on
one side, and every `REGOLITH-TAP ch=<n> target=<path>` marker
re-parsed out of every emitted file on the other (board
`tap_placements.json` rows, the firmware `debug_taps.h` table, the
HDL `debug_taps.v` module all embed the marker verbatim). Either
uncovered difference is a named `tap_map_artifact_mismatch`
diagnostic and `ship` returns `Err` BEFORE the manifest is written --
a disagreeing package cannot exist as a completed ship output.
Argument: the two sides of the comparison are independently derived
-- the map is serialized from the derivation-time tap set plus its
planned family carriage, while the marker scan reads only the bytes
the backends actually wrote -- so agreement cannot be assumed by
construction and must be (and is) checked; allocation is capped by
what an emitting family can actually carry (a board/firmware family
carries every channel; an HDL-only package is capped at its widest
declared debug-pin set; a package with no augmentable family
allocates zero channels), so the "every map row is emitted" direction
is achievable exactly when claimed and any regression in a backend's
marker emission (or a map row claiming carriage nothing provides)
fails the check rather than shipping. The release direction is
vacuous by construction: a release-profile ship never derives a tap
set, never emits a map, and never embeds a marker, so the check does
not run and the release artifact set is untouched (D206/D220.1;
byte-identity pinned by golden equality). Test family
(`tests/backends/test_debug_taps.py`,
`tests/backends/test_debug_emission.py`): agreement holds on a real
debug emission end to end; deleting a marker-bearing artifact fails
the check in the missing-row direction; injecting a forged marker
fails it in the unmapped direction; a release ship emits neither map
nor markers and its file set is byte-identical to a pre-debug-profile
ship of the same build.

## INV-33 RESERVED (parked, D253.4) -- do not reuse this number

INV-33 formerly stated that engineer overrides could not forge a passing
release gate. The invariant is WITHDRAWN from the ledger, and the number
is RESERVED rather than reused.

## INV-34 No bare dimensioned values reach an artifact-rendering interface

**Every artifact-rendering interface that accepts a dimensioned value
accepts a unit-carrying quantity type; a genuinely dimensionless value
carries an EXPLICIT dimensionless marker, never an absent unit --
"bare float plus hope" is not a representable call site (WO-150,
D262).** Mechanism: two complementary halves, per D262's own ruling
structure.

STRUCTURAL (the real enforcement, discharged by unreachability):
`regolith.backends.quantity.DimensionedValue` is a frozen model whose
`unit` field is REQUIRED and whose `model_validator` rejects an empty
or whitespace-only string outright -- so the type itself refuses to
exist in the "unit omitted" state. Every artifact-rendering interface
this WO's audit found actually carrying a bare `float` for a
dimensioned quantity now requires this type instead:
`regolith.backends.hdl.HdlTierRow.value`/`.margin` (previously a bare
`float` with NO unit field reachable at all -- a build/sim tier's
value is genuinely dimensionless, so both now carry the explicit
`DIMENSIONLESS` marker) and
`regolith.backends.instructions.FastenerCallout.value` (previously a
bare `float` next to an independently-defaultable `unit: str` -- the
two are now one atomic value that cannot exist unlabeled). The
calc-sheet (`regolith.backends.calc`) and bring-up
(`regolith.backends.harness_pack`) surfaces already carry unit
attached to a value's own text (the D265 representation choice this
WO's structural half follows) and are confirmed, not re-migrated
(D262 ruling 4; WO-150's own seam-coordination note).

SWEEP (the rot guard for what the type system cannot reach):
`tools.health.units` scans the committed demo proof corpus
(`demos/out/*/PROOF.md`) for dimensioned-looking bare numerals in
prose/markdown table cells -- free-form text a renderer assembles
with plain f-strings, which no type signature governs. Wired into the
`consistency` health leg (`tools/health/consistency.py::_check_units`)
as REPORT-ONLY: it always returns `ok=True` regardless of findings,
per the F154 lesson applied in reverse (a gate promoted before it is
satisfiable is a gate that gets waived) -- promotion to a hard error
is a later, separate reviewed decision once the corpus is observed
clean under it, not taken by this change.

Argument: the structural half's proof is unreachability, the same
shape as INV-28's evidence-attribution proof and D257 ruling 2's
uncited-value proof -- a bare float cannot reach `HdlTierRow`/
`FastenerCallout` because the interface's own type refuses it at
construction (`tests/backends/test_quantity.py`'s
`test_unit_enforcement_*` family proves the refusal is a real
`ValidationError`, not documentation: attempting the old bare-float
call site against either changed signature raises). The sweep half's
argument is empirical, not structural, and is honestly weaker by
design: it is a REPORT-ONLY discharge for the surfaces the type
system cannot reach at all (prose text), so its evidence is "flagged
count observed at each run," not "proven zero" -- the invariant's
claim over those surfaces is therefore a rot-guard claim (a
regression is visible), not an unreachability claim, until a future
change observes the corpus clean and promotes the sweep to gating.
Test family: `tests/backends/test_quantity.py` (the structural
refusal, both changed interfaces); `tools/health/units.py::run`
(report-only, never fails); `tests/backends/test_hdl.py` and
`tests/backends/test_instructions.py` (the changed interfaces'
existing suites, updated to construct through `DimensionedValue`,
still pass end to end).

Why it is gone, plainly: D253 parked the whole engineer-injection channel
(the override ledger, target resolution, the `engineer_override` cause,
the `override` CLI verbs, and WO-130's edit models) to the branch
`experimental/injection-channel`, where every line of it is preserved.
F150 established that the channel was INERT -- nothing in a real build or
ship ever read the ledger -- so INV-33's proof was a proof about a pure
function, not about the pipeline. An invariant whose enforcement is
parked MUST NOT sit in this ledger looking enforced: a green test under
an invariant's name is a claim that the system is protected, and this one
was not. Withdrawing it is the honest state, not a loss of a guarantee
(there was no guarantee in the pipeline to lose).

The number stays reserved so that no future invariant silently inherits
the citations, tests, or close-outs that referenced INV-33. If the
injection channel is ever revived from `experimental/injection-channel`,
it comes back with a proof that runs the REAL pipeline (D226, D252.3) and
takes a NEW invariant number.

## INV-35 (cuprite sim/timing honesty) -- RESERVED/PENDING, WO-154

Number confirmed next-free after INV-34 (do not reuse INV-33,
RESERVED per D253.4). Entry TEXT drafted now per WO-154 (D264); the
ENFORCING code that discharges each leg lands across WO-155 (leg a,
functional sim), WO-156 (timing's share of legs a/c), and WO-157
(the totality of leg c, the coverage sweep) -- per house law "new
guarantees need a proof argument in the SAME change," this entry
stays PARKED/PROVISIONAL until ALL cited WOs land, the same
accretion pattern the ledger already used for INV-24's
acceptance-ledger proof across WO-98 and its dependents.

WO-155 STATUS (partial, this entry still does NOT flip to
`discharged`): leg (a)'s emission/discharge machinery has landed --
`regolith_lower::claims::sim` auto-emits `hdl.sim_assert` off a
declared `require: sim(<stimulus-ref>)` clause on an HDL extern-edge
decl (E0453 the malformed-clause guard); `HdlSimAssertGenericModel`
(`harness/models/hdl/models.py`) discharges it source-generically
from generated-testbench vectors, cache-keyed on
(hdl_src digest x stimulus digest x model version); the
`signal_table` payload (`harness/models/hdl/signal_table.py`)
enforces leg (b)'s authored-only trust-tier vocabulary BY
CONSTRUCTION (E1105 is the untrusted-JSON-on-disk belt to that
suspenders) with NO wire-schema change (the `stimulus_ref` given
rides the existing `Given.loads: Vec<String>` field, so this WO
opens no second cycle-37 `SCHEMA_VERSION` bump, D264 ruling 4).
STILL OPEN, why this entry does not flip: leg (a)'s SHIP-PATH
digest-reverification check (the INV-32 tap-agreement-pattern half
that refuses a `sim/` artifact whose digests do not re-verify) and
the `sim/` artifact family itself (`trace.vcd`/`sim_report.json`,
charter 38 sec. 5) are a `python/regolith/backends/**` emission hook
this WO's implementer escalated rather than landed (a concurrent
agent owns that tree this cycle); leg (c) (the coverage sweep) is
WO-157 entirely, unstarted; leg (a)'s timing share and all of leg
(c)'s timing budget totality are WO-156, unstarted. Do not read this
entry as `discharged` until the cited WOs' close-outs update it.

**Every released cuprite design's simulation and timing verdicts are
grounded: (a) a shipped sim artifact always names the exact
stimulus digest, source digest, and tool version that produced it;
(b) an authored (drawn/typed) stimulus or expectation can never
carry, or upgrade to, a model-backed or measured trust tier; (c) a
behavioral subject with no sim coverage and a clocked subject with
no timing budget appear as named absences on the audit surface,
never as silence.**

Proof-argument sketch (parked; see the PENDING note above):

- (a) by construction: the sim model's evidence is built only from
  the `DischargeRequest`'s own payload digests and the seam-resolved
  tool version (the AD-19 cache-key law already folds tool version
  into `Model.version`, `verilator_adapter.py:8-11`); a ship-path
  check (the INV-32 tap-agreement pattern,
  `../toolchain/40-debug-and-bring-up.md` sec. 3) refuses a `sim/`
  artifact whose digests do not re-verify against the payload store.
- (b) by unreachability (the D246/D260.3 "cannot forge a pass"
  pattern): the stimulus payload model's provenance field for
  authored artifacts has a tier vocabulary containing only
  authored/asserted; no constructor accepts a model/measured tier
  for an authored `signal_table` -- the same unrepresentability move
  as D257's citation-less datasheet value.
- (c) by totality of the coverage sweep: the parity/coverage
  producer enumerates subjects from the SAME lowered entity set the
  build used (not from the claims that happen to exist), so every
  HDL extern edge or `on <clk>` body either matches a sim/timing
  obligation or produces a named-absence row (the WO-114
  zero-unexplained-rows partition precedent,
  `tools/health/fleet.py:36-40`).

Cross-references: `../cuprite/03-behavioral-layer.md` sec. 2 (`by
sim(<stimulus-ref>)`); `../cuprite/04-structural-layer.md` sec. 5a
(the `setup_slack`/`corners` deferral this entry's leg (c) does NOT
cover -- that deferral has its own reopen criterion, independent of
this invariant landing); `../toolchain/38-emission-and-release.md`
sec. 5 (`signal_table`, `sim/` registry additions).
