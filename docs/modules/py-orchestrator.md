# py-orchestrator

The build orchestrator: obligation-driven optimize/discharge loop,
resolvers (frame/material/fluid), staging (plan/dfm), evidence
caches (payload/nogood), acceptance/costing, and the lockfile/
programs translation layer. See `docs/spec/toolchain/00-architecture.md`
for the orchestrator's place in the pipeline (AD-1..-39) and
`docs/spec/regolith/13-invariants.md` for the guarantees
(determinism, cache soundness) each module below upholds. This doc
is a symbol-level index into that design, not a restatement of it.

## acceptance

<a id="acceptance"></a>
### `python/regolith/orchestrator/acceptance.py`

Consume the payload's ``WaiveLedger`` at the release gate (WO-98).

The Rust core builds the todo/assume/waive ledger (INV-12 audit surface)
and puts it on ``BuildPayload.ledger``; this module turns that ledger
into the Python release gate's ACCEPTANCE decision (INV-24 completed,
D206): which otherwise-unresolved obligations are *accepted deviations*
and which remain refusing.

Load-bearing honesty rules (regolith/12 sec. 3, D206/D207):

* An evidence-carrying waiver whose evidence meets the target claim's
  trust floor (INV-14) ACCEPTS the obligations it matched: their true
  status is untouched (INV-2 -- an acceptance never forges ``discharged``),
  the release passes WITH the deviation listed.
* A bare (evidence-less) waiver and an ``assume!``/``todo!`` remain
  release-gated: durable acceptance needs evidence; per-item CLI
  acknowledgment (``--accept``) is exploration-only (rule 9) and the
  report says so.
* An expired waiver behaves as absent (its matched obligations refuse
  again) and surfaces the stale error (rule 8) -- the Rust
  ``release_blocked`` does NOT check expiry, so the gate owns it here.
* A stale waiver (``WaiverKind::Stale``) is already a Rust diagnostic
  (E0701 -> the build is not clean); the gate does not double-report it.
* A ``by doc(<ref>)`` evidence ref (D207) resolves through the record-
  path machinery to an in-project engineering memo (``memos/*.md``),
  hash-pinned; an unsigned memo confers ``community`` tier (INV-14). A
  dangling memo ref refuses loudly.

## cache

<a id="cache"></a>
### `python/regolith/orchestrator/cache.py`

The harness evidence cache (regolith/09 sec. 2-3; INV-1/INV-10/BE-1).

The Rust core caches the *static* discharge subset under ``.regolith/``;
this is the orchestrator's cache for the *harness* discharge it owns
(AD-1). It is keyed the same way the Rust obligation key is keyed -- the
obligation's own content plus the harness model-registry version folded
in -- so the two caches agree on what invalidates evidence: any semantic
change to the obligation, OR a model-registry bump, is a cache MISS
(INV-1). Bit-reproducible: canonical JSON (sorted keys) hashed with
blake3, matching the core's hasher, so identical inputs give an identical
key on every platform (INV-10).

The store is a plain content-addressed map persisted as JSON. It never
raises for a recoverable condition: a corrupt or unreadable cache file is
an ``OrchestratorError`` value the caller decides about (rebuild vs fail).

## costing

<a id="costing"></a>
### `python/regolith/orchestrator/costing.py`

Cost-profile resolution: profile -> record set -> estimator inputs
(WO-54 deliverable 4; toolchain/27 sec. 1.2-1.3, AD-29).

This module owns the orchestrator half of the costing charter: loading
a project's ``[profiles.cost.<name>]`` tables, resolving every record
ref a selected profile names (rates by exact key; pricing/unit-cost
sources by key PREFIX, first source pricing an item wins), checking
``valid_until`` expiry, staging the estimator-inputs ``table`` payload
(one per cost obligation, resolved by the std.cost models through the
ordinary D96 channel), and recording every consumed record as an
INV-22 lockfile pin. The obligation-to-request lowering itself stays
in :mod:`regolith.orchestrator.translate` (which maps this module's
error values onto its own ``Deferral`` surface).

Clock note (the expiry rule's time source): the toolchain deliberately
has NO ambient build clock -- the mech realizer NORMALIZES wall-clock
export timestamps OUT of content-addressed artifacts (AD-6/INV-10),
and the only wall-clock use anywhere is the harness adapter's
``timeout_s`` infrastructure guard. Expiry follows the same line: the
build date enters at ONE seam (:func:`load_cost_context`'s ``as_of``,
defaulting to today's UTC date exactly there and nowhere else), and an
expired record produces a DEFERRAL -- which is never cached and never
content-addressed -- so wall-clock time still never enters any hashed
artifact. Callers that need reproducibility (tests, golden fixtures)
pass ``as_of`` explicitly.

## dfm_staging

<a id="dfm_staging"></a>
### `python/regolith/orchestrator/dfm_staging.py`

`manufacturable(<process>)` staging: the build's own FeatureProgram +
realized-geometry facts reaching the `mfg.manufacturable` model
(WO-110 headline; F130 census item 4, D232.2).

Mirrors `plan_staging`'s posture exactly: this module owns DERIVING the
staged `dfm_part`/`dfm_tools` payload records from data the build
already produced -- the payload's `feature_programs` (WO-51),
`snapshots` (subject-hash -> scope name), and the staged-build loop's
realized inputs (`geometry.realized`, AD-25) -- and staging them into
the build's ONE `PayloadStore` (D96/D154). The obligation-to-request
lowering stays in :mod:`regolith.orchestrator.translate`
(`_translate_manufacturable`), which maps this module's honest gaps
onto its own `Deferral` surface, same split as costing/plan staging.

ONE HOME for the process vocabulary (the tripwire rule applied to
process words): the claim-token map (`manufacturable(milled)` ->
family) and the stage-process map (`process=cnc_mill` -> family) live
here and nowhere else.

v1 grounding scope (named cuts, all reported in the WO close-out):

- Only the MILL family grounds (the existing `[[machine]]`/`[[tool]]`
  record vocabulary is mill-class); every other family defers with the
  reason naming what would ground it.
- Only `hole`-kind feature ops feed the tool-fit check (pocket ops
  carry no width scalar today); a mill-stage hole whose diameter or
  depth is not a spelled literal defers NAMING the parameter (the
  D224/WO-113 enrichment surface, never a guess).
- A part with more than one realized geometry subject (weldments)
  defers stock fit: per-piece boxes live in per-piece frames, so no
  assembly-level bounding box is derivable without RealizedAssembly
  consumption (a named cut).

## discharge

<a id="discharge"></a>
### `python/regolith/orchestrator/discharge.py`

Route obligations to the harness, with caching and honest deferral.

This is the orchestrator's half of the AD-1 split: the harness *selects
and computes* evidence; the orchestrator *owns caching, ordering, and the
loop*. Each obligation is (1) keyed (registry version folded in, INV-1),
(2) served from cache on a hit, else (3) lowered to a
:class:`DischargeRequest` and handed to the model registry -- which is
TOTAL, so a no-model obligation comes back as an explicit ``indeterminate``
evidence value, surfaced here as a :class:`Deferral`, never a silent pass.

Obligations are consumed in the source order the core emitted them (INV-10
determinism); results carry the obligation key so the lockfile and the
release gate can reason over them.

## fluid_resolve

<a id="fluid_resolve"></a>
### `python/regolith/orchestrator/fluid_resolve.py`

Fluid medium-record chain resolution: a `fluids.dp(...)` claim's
missing `density_kgm3` input walks obligation -> flownet payload ->
`medium.records` -> the std.fluid `[[medium]]` property record
(WO-112 Class 4, the F131.4 chain half of `fluids.dp_inputs_missing`).

The fluorite corpus declares its medium properties BY REFERENCE
(`medium BrewWater: liquid` / `props: registry(water_iapws_liquid)`),
and the Rust lowering threads those names into the flownet payload's
`medium.records` -- but nothing ever WALKED the chain, so every dp
claim deferred naming ALL of its inputs even when density was one
record lookup away. This module is that walk: the flownet payloads
come from the build payload (the `FrameContext.frames` posture), the
`[[medium]]` rows load from the same D192 record search paths every
other record family uses, and a resolved record pins an INV-22 ledger
row. A medium record the design names but the paths do not carry
stays an honest, NAMED gap (the Class D half -- authoring the record
is WO-113/D224 territory, never fabricated here).

## frame_resolve

<a id="frame_resolve"></a>
### `python/regolith/orchestrator/frame_resolve.py`

Frame payload resolution: name-only section/material `RecordRef`s
-> std.civil numeric properties, staged as harness model inputs
(WO-48 slice B/C close-out follow-up -- "frame chain completion").

The frame payload itself is content-addressed at lowering and MUST
NOT be mutated post hoc (AD-18/AD-22): resolution happens here, at
the ORCHESTRATOR boundary, against the same payload bytes the frame
producer (`orchestrate._put_frame_payloads`) already staged into the
WO-30 store. This module mirrors `regolith.orchestrator.costing`'s
seam discipline (the WO-54 precedent): a plain per-family TOML
loader, `row_hash`-pinned records, and an honest `Result` for every
resolution step -- a section/material ref that resolves to no
std.civil record, or a member whose section is still the L3
search placeholder (`RecordRef(name="free", digest="")`), defers by
NAME, never fabricated (D58/AD-25).

Scope note (WO-85 update; the WO-65 note before it is superseded, not
silently dropped): this module resolves SECTION/MATERIAL numeric
properties (`resolve_member`) AND the full per-member gravity demand
surface (`member_demand` -> `MemberDemand`): directly-targeted line
loads (`kN/m on [...]`, SCHEMA 27's `line` kind, calcite/03 sec. 4),
tributary-transfer demand via `resolve_tributary_demand` (feldspar
WO-23's `resolve_tributary_loads` seam, mirrored in-repo since
feldspar is a separate distribution this toolchain does not import --
WO-27; fed by `FramePayload.transfers`, D176), stationed POINT loads
(`on [G1@0.5]`, D194), and column AXIAL demand from incoming gravity
load paths (`_axial_demand` -- the "axial pinned at 0" wall is dead).
A member with no resolvable demand source at all still defers
`frame_load_untargeted`, naming exactly that combined gap.

WO-65 reopen (this module's newest addition): a `section: free`
member carrying a DECLARED candidate family (WO-68's
`FrameMember.section_domain`, `section: in registry(<family>)`) no
longer stops at the blanket `frame_section_domain_unsearched`
deferral -- :func:`search_free_section` runs a real section search
over that family's std.civil catalog rows, through the SANCTIONED
`regolith.orchestrator.optimize.optimize_discrete` driver (AD-30: no
private scoring path). Candidate feasibility is DISCHARGE-COHERENT
by construction: each candidate is evaluated through the SAME
harness models the claims later discharge with
(`BeamUtilizationModel` for the member's declared `civil.utilization`
limit, `BeamServiceDeflectionModel` for its declared
`mech.deflection(...) <= span/N` bound -- the bounds come from the
build's OWN obligations via `translate.frame_claim_bounds`, never
invented) under the SAME `value + eps <= limit` margin rule the
evidence layer applies (`harness/evidence.py`) -- so a search winner
cannot fail its own claims at discharge. A claim form with no
harness model (e.g. `mech.first_mode`) gates nothing: it stays
honestly deferred at translate time whatever section wins, and a
gate the pipeline could never check would be a private scoring path.

Capacity-form provenance (the WO-65 dispatch's feldspar question):
feldspar's `mech.member.flexural_yield_capacity_f2` (AISC 360-16
F2.1, `Mn = Fy*Zx`) needs a PLASTIC section modulus; NO std.civil
section record carries a Zx field, only the elastic `s_mm3`/`s_in3`,
and fabricating Zx from S via a shape-factor guess is the "invented
equivalence" D58/WO-60's honesty note forbids. The search therefore
evaluates through the toolchain's landed elastic-interaction model
(`beam_utilization.py`, `|M|/(S*Fy) + |P|/(A*Fy)` with its own
declared 8 percent eps) -- the exact model the claim discharges with.
WO-85/D194 wired the AXIAL term: `member_demand` resolves a column's
axial demand from its incoming gravity load paths (`_axial_demand`),
so both the search and the discharge path now exercise the full
interaction (feldspar's `axial_yield_buckling_capacity_e3` -- true
buckling with Ag/r/KL -- remains a recorded feldspar-side follow-up;
the elastic interaction here is the landed in-tree tier).

The objective is mass-per-length (`area_m2 *
material.density_kg_m3`, ascending -- no corpus design declares a
`policy:` block for its structural claims, so this is the WO-56
disclosed tie-break default, not a silent choice). The winner is
pinned the ONE canonical way: its `OptimizationTrace` persisted via
`optimize.store_trace` (when the build threads a payload store) and
its lockfile row built by `optimize.winner_lock_row`
(`cause: optimize(mass_per_length, trace=<digest>)`, INV-21/INV-22),
accumulated on `FrameContext.winner_rows` +
`FrameContext.consumed_pins` for the build report to collect.

A `section: free` member with NO declared domain still defers
`frame_section_free` unchanged (D181: no reinterpretation); a
declared family with no std.civil rows defers
`frame_section_family_not_landed`; a declared family whose rows all
lack the properties its declared claims need defers
`capacity_unresolved`; a family whose rows resolve but no candidate
satisfies every declared bound defers
`frame_section_search_infeasible` -- four distinct, honest reasons,
never a blanket catch-all.

## lockfile

<a id="lockfile"></a>
### `python/regolith/orchestrator/lockfile.py`

The lockfile: the reviewable pin surface (WO-14).

Spec: regolith/09 sec. 2-3; regolith/03 sec. 2. Every non-literal
resolution lands here with its cause, so a number that changes in review
names why it changed. The text format is line-oriented, sorted, ASCII,
and bit-reproducible: identical inputs produce byte-identical output.
Resolutions come from the Rust core (WO-04 ``Resolution`` via the WO-18
facade); this module authors the TOML/text surface only.

Text shape (one lockfile, sections in sorted-name order, rows in
sorted-slot order within a section, record pins in sorted-key order):

    # regolith.lock tool_version=0.1.0
    [section ""]
    flange.radius = 2.4mm         cause: dfm(sheet.min_bend_radius)
    seat.runout = +-0.015         cause: budget(mesh_alignment)
                                   policy: prefer(low_cost)
    pin jlc.pcb@2.3.0 = sha256:aa10f3

    [section "flight"]
    net.vdd.width = 0.3mm         cause: drc(jlc_2l.current_capacity)

Each row is ``<slot> = <value>         cause: <cause>`` with an optional
trailing ``         policy: <note>``; the double-space gap keeps the
columns diff-stable without needing fixed-width padding. A ``pin`` line
is ``pin <package>@<version> = <revision hash>``.

## loop

<a id="loop"></a>
### `python/regolith/orchestrator/loop.py`

The lazy optimization loop with sensitivity hooks (regolith/12).

The default build resolves once (eager) and discharges once. ``optimize``
(tier T2) adds this loop: after a discharge pass, each registered
:class:`SensitivityHook` may propose a *refined* obligation set -- a
tightened tolerance, a re-allocated budget share, a narrowed choice -- and
the loop re-discharges only when something actually moved (lazy). It runs
to a fixpoint (no hook proposes a change) or a bounded iteration cap, and
is deterministic: hooks are consulted in registration order and the first
one that proposes a change wins the round (INV-10).

Crucially, the loop only ever changes *inputs* and re-keys obligations
(INV-2 ladder safety): it can never relabel a verdict, because every
proposed obligation set is discharged afresh through the same total
harness path. A wrong refinement can only fail to converge, never lie.

## material_resolve

<a id="material_resolve"></a>
### `python/regolith/orchestrator/material_resolve.py`

Material-record bound resolution: `material.<prop>` entity-derived
claim bounds -> std.materials numeric properties (WO-112 Class 2, the
D103 ref-resolution residual named by F130/F131.2).

A corpus claim like `shell: peak(mech.stress.von_mises, at=...) <
material.sigma_y / 2.5` carries its bound in a MATERIAL RECORD, not a
literal: the declaring part pins `material: AL_5052_H32` (threaded by
the Rust lowering into `given.materials`), and the yield stress lives
in `std.materials`' records. Records are magnetite/Python domain
(D192/D193 -- the Rust core never reads TOML), so the bound
literalizes HERE, at the orchestrator boundary, exactly where
`frame_resolve` literalizes std.civil section refs.

One loader home (NO DUPLICATION): this module does not parse record
TOML itself -- it reuses :func:`frame_resolve.load_frame_records`,
whose `[[material]]` reader already walks every package's
`records/*.toml` under the search paths (std.materials included) and
reduces rows to SI-unit :class:`frame_resolve.MaterialProps`. This
module only adds the build-level context object (records +
consumed-pin ledger, the `CostContext`/`FrameContext` posture) and
the INV-22 pin collector.

## nogood_cache

<a id="nogood_cache"></a>
### `python/regolith/orchestrator/nogood_cache.py`

Cross-run nogood cache (cuprite/08 EOPEN-13, D75).

D75 closes EOPEN-13 on one soundness rule: learned nogoods are per-run
solver state in v1 (never lockfile content), and cross-run reuse of a
nogood is sound IFF the cache key includes every catalog record
revision the nogood's blame set consumed -- the INV-1 discipline
(``regolith/07`` sec. 7) applied to search state instead of evidence.

This module is the persistence layer implementing that rule. A nogood
is addressed by the rejected ``(block, record_key)`` pair PLUS the full
blamed trial: every candidate's ``record_key``/``content_hash`` that
entered the budget computation the trial violated, and the budget set
itself. Mutate any blamed record (a new revision, hence a new content
hash) and the key changes, so a stale nogood is a natural MISS -- there
is no separate invalidation pass, exactly the same content-addressing
argument `regolith.orchestrator.cache.EvidenceStore` already makes for
harness evidence.

The store lives beside the harness evidence cache under `.regolith/`
(AD-10; gitignored, project-local) in its own file so the two caches
never share rows.

## optimize

<a id="optimize"></a>
### `python/regolith/orchestrator/optimize.py`

The optimization engine (WO-55; toolchain/28-optimization.md, AD-30).

ONE engine home (`regolith.orchestrator.optimize`, AD-1): two drivers,
one contract. `optimize_discrete` is a policy-ordered greedy/backjumping
search over declared candidate domains (`ChoicePoint`-shaped: registry
queries, `by select(...)` lists -- D161, WO-56); `optimize_continuous`
is bounded `in [lo, hi]` refinement via in-house, deterministic, seeded
strategies (`golden_section`, `nelder_mead`; no scipy, AD-30).

Evaluation IS the pipeline (charter sec. 1.2): neither driver ever
scores a candidate itself. Both take an ``Evaluator`` callable that the
CALLER wires to the real `build`/`staged_build` + discharge path (T2
tier); this module only ever calls the injected evaluator, never
touches the compiler or harness directly. This is the seam WO-57 (the
staged-loop realized-domain optimizer) plugs `staged_build` into without
any change here: it only needs a different ``Evaluator`` closure, same
driver signatures.

Objective extraction (deliverable 2) is likewise a caller-supplied
``tuple[ObjectiveDirection, ...]`` in declared lexicographic order
(regolith/03 sec. 2, regolith/12 sec. 4: per-variable `minimize`/
`maximize`, then a `policy: minimize` list) -- this module never parses
`policy:` blocks itself (no new grammar); WO-56/57 are the callers that
read the lowered payload/lockfile surfaces and build this tuple.

Determinism (INV-30): every domain is an ordered ``tuple`` (AD-6), every
strategy is a pure seeded function, and the trace is content-addressed
(`OptimizationTrace.content_digest`-equivalent: `PayloadStore.put`'s
fresh blake3 of the JSON bytes -- the WO-42/WO-54 precedent for
Python-produced payloads with no Rust-computed AD-18 digest to
reproduce, `costing.py::persist_estimates`).

## optimize_sketch

<a id="optimize_sketch"></a>
### `python/regolith/orchestrator/optimize_sketch.py`

WO-97 / D209 coupling: pin a bounded sketch-segment optimize slot from
a REAL per-candidate discharge-margin search.

D209 ruled that a bounded geometric slot's optimizer evaluator IS the
discharge pipeline specialized per candidate -- there is no new evaluator
concept. This module is that specialization for the corpus's bounded
profile-width slots (`<seg>.length = in [lo, hi] minimize`) whose owning
part carries a cantilever-deflection claim:

    per candidate width `b`
      -> section second moment I(b)                       (geometry-at-b)
      -> `mech.beam.cantilever_deflection` DischargeRequest (the model
         channel `beam_bending.py` already registers -- F126.1's gap was
         that a label-named `mech.deflection(...)` claim never REACHED it;
         here the coupling recognizes the claim by its call form and
         drives the model directly, geometry in hand)
      -> feasible iff the deflection margin discharges (>= 0)
      -> objective = the slot value itself (minimize)

The winner is a genuine search result, pinned as a `LockRow.cause =
optimize(...)` (never a guessed literal). A part whose deflection inputs
do NOT resolve from declared data (e.g. `uav_talon` WingSpar, whose gust
reaction is `derived(sf=1.5)` with no declared scalar) stays honestly
`optimizer_evaluator_deferred` -- this module never fabricates a load.

Provenance of the model: Euler-Bernoulli cantilever, end point load,
`delta = F*L**3 / (3*E*I)` (`beam_bending.py`'s cited formula). The
section orientation is DOCUMENTED, not inferred: the optimized width `b`
is the bending depth (the flat plate resists the tip load about the axis
perpendicular to `b`), so `I = t * b**3 / 12` with `t` the plate
thickness -- deflection shrinks as `b` grows, which is exactly what makes
`minimize b` a constrained search rather than a free ride to the lower
bound in the general case.

E2 (the WO-97 result-to-part linkage gap) is resolved by CONSTRUCTION
here: the coupling works from the declared part (its `FeatureProgram`
`part_name` and its named deflection claim), never from an
`ObligationResult.subject_ref` content hash -- so "the part's governing
claim" is selected by name, no new content-hash-to-part channel needed.

## orchestrate

<a id="orchestrate"></a>
### `python/regolith/orchestrator/orchestrate.py`

The build driver: tiers -> discharge -> loop -> release gate (AD-1).

This is the top of the orchestrator: it drives the compiler facade to get
obligations, routes them through the harness at the tiers that discharge
(T1+), runs the lazy loop at the optimizing tier (T2+), and enforces
release-gate totality at T3 (INV-24). It owns the caching and ordering;
the harness owns selection and physics; the core owns everything static.

The release gate is the load-bearing honesty property: a ``--release``
report contains zero *unaccepted* ``violated`` or ``indeterminate``
obligations (INV-24). Acceptance is the ledger channel (WO-98, D206):
this layer consumes the payload's ``WaiveLedger`` (regolith/12 rungs
6-7), so an evidence-carrying waiver whose evidence meets the target
claim's trust floor counts as an ACCEPTED DEVIATION -- the obligation's
true status stands (INV-2), the release passes with the deviation listed
and counted DISTINCTLY from ``discharged``. A bare waiver or ``assume!``/
``todo!`` keeps refusing (durable acceptance needs evidence; ``--accept``
is exploration-only). Verdict math is untouched: an acceptance never
converts a status.

## payload_store

<a id="payload_store"></a>
### `python/regolith/orchestrator/payload_store.py`

The orchestrator-owned content-addressed payload store (D96, sec. 8.3).

The generalized payload-ref channel (`PayloadRef.digest`) is a blake3
digest into THIS store: packs never do their own storage IO (AD-17
lowering stays IO-free too) -- they receive a resolver handle at
discharge and call :meth:`PayloadStore.resolve`. Files live under
``.regolith/payloads/`` (beside the evidence cache, AD-10; gitignored),
named by their digest so a re-``put`` of identical bytes is a no-op.

## plan_staging

<a id="plan_staging"></a>
### `python/regolith/orchestrator/plan_staging.py`

`plan:` linkage staging: extern plan bytes + machine/tooling/target
records reaching the landed `std.cam` pack (WO-69; regolith/08 sec. 4's
L6 row, WO-67's close-out ledger follow-up).

Mirrors `regolith.orchestrator.costing`'s staged-doc precedent: this
module owns resolving the source-declared `machine=`/`tooling=` record
refs (the ``[[machine]]``/``[[tool]]``/``[[stock_target]]`` local
record tables, same `key = "..."`/local-path-only posture as
`costing.load_cost_records`) and reading the extern-referenced plan
bytes off disk, staging both into the build's ONE `PayloadStore`
(D96/D154) so the `std.cam` models' `plan`/`cam_machine`/`cam_tooling`/
`cam_target` ports resolve. The obligation-to-request lowering itself
stays in :mod:`regolith.orchestrator.translate` (`_translate_cam`),
which maps this module's error values onto its own `Deferral` surface
-- same split as costing/translate.

Every consumed record lands in `PlanContext.consumed_pins` (INV-22),
read out by :func:`record_pins` post-discharge, mirroring
`costing.record_pins` exactly.

## planner

<a id="planner"></a>
### `python/regolith/orchestrator/planner.py`

The planner-model shape (WO-26 D105c): one home, no new evidence kind.

D105(c): a plan artifact is a ``plan``-kind payload on the D96 channel
(content-addressed through the orchestrator :class:`PayloadStore`), and
every lockfile row a planner pins carries ``cause: planner(<what>)``
(regolith/07 sec. 6's "plan = evidence", INV-21 provenance) -- NO new
evidence shape. This module is that shape's single home: the cause
formatter every planner writes through, and the adapter base class
that turns a planner's decisions into its content-addressed payload
ref plus lockfile rows. The WO-24 binding search and the WO-35 pin-mux
planner are the retrofitted customers (their cause literals moved
here; one shape, NO DUPLICATION).

## programs

<a id="programs"></a>
### `python/regolith/orchestrator/programs.py`

Pipeline-produced realizer programs (WO-51 deliverable 4).

Promote the ``feature_programs`` the Rust ``lower.programs`` pass emits
into ``BuildPayload`` (scalar ops + D150 promoted sketches + D151/D152
cavity-derived ``flow_paths``) into the realizer's input contract
(:class:`regolith.realizer.mech.schema.FeatureProgram`), keyed by the
``from=<ref>`` subject each flow path's selector names -- so
:func:`regolith.orchestrator.orchestrate.staged_build` no longer needs
caller-supplied programs (the caller channel stays as an override for
tests, AD-22).

HONESTY CONTRACT (AD-25, D151/D152 verbatim): a program converts ONLY
when every field the realizer contract requires is DECLARED in the
emitted IR -- a fully pinned promoted sketch (the outline is a
cumulative cardinal walk over exact declared lengths -- arithmetic on
declared facts, never computed geometry), a blank/pocket op with a
declared depth (the solid), and per-segment declared
diameter/depth/elevation/roughness facts. Anything indeterminate makes
the program non-convertible: it is SKIPPED with a named reason at INFO
(the subject stays pending and its obligations stay honestly
indeterminate) -- never guessed.

## si_stackups

<a id="si_stackups"></a>
### `python/regolith/orchestrator/si_stackups.py`

Stackup-record resolution for signal-integrity claims (WO-78).

This module owns the orchestrator half of charter 35 sec. 1.1-1.2's
record story: loading fab-published `[[stackup]]` record rows
(``stdlib/std.elec.stackups`` and any local package roots) and
resolving an ``elec.impedance(<net>, stackup=<key>, ...)`` claim's
dielectric geometry (h/er/t) from the named record instead of from
in-claim folklore numbers. The obligation-to-request lowering itself
stays in :mod:`regolith.orchestrator.translate` (the
``costing``/``plan_staging`` split, applied to SI).

Honesty rules carried from the record file's own ledger
(`stdlib/std.elec.stackups/records/jlcpcb.toml`):

- Microstrip (outer layer) is the ONLY stackup-derived mapping: the
  fab publishes the outer prepreg span + material Dk + outer copper,
  which are exactly Hammerstad-Jensen's h/er/t. The single-core
  2-layer record uses its core span/Dk the same way.
- Stripline cavity heights are NOT derived (no per-layer role table is
  published); a stripline claim supplies ``b``/``er`` explicitly and
  the deferral for a stackup-derived request names this residual.

## tiers

<a id="tiers"></a>
### `python/regolith/orchestrator/tiers.py`

Build tiers: the T0..T3 progression (regolith/09 sec. 1).

Every regolith build runs at one tier, and each tier is a strict superset
of the work of the tier below it -- ``check`` (T0) is pure static analysis,
``build`` (T1) adds realization + harness discharge, ``optimize`` (T2)
adds the orchestrator loop, and ``release`` (T3) adds the totality gate
(INV-24). The tiers form a total order so a caller can ask "does this tier
include that work?" without re-encoding the ladder anywhere else.

## translate

<a id="translate"></a>
### `python/regolith/orchestrator/translate.py`

Translate a serialized ``Obligation`` into a harness ``DischargeRequest``.

Extracting a numeric discharge request from a serialized obligation is
orchestrator territory (regolith/07 sec. 2 note on ``DischargeRequest``):
the obligation's quantity expressions are text until resolution pins them,
and the harness consumes only the resolved form. This module does that
lowering for the scalar-comparison claim form and reports an explicit
:class:`Deferral` for anything it cannot resolve numerically -- never a
silent drop (INV-24 totality feeds on honest deferrals).

The numeric parsing here is deliberately conservative: it reads a bare
literal off a `given.loads`/`given.refs` value (:func:`_parse_float`) and
defers when a value is not yet a literal. A claim's COMPARATOR BOUND is
different: :func:`_resolve_bound` (WO-122, F132.2) is the ONE home every
bound-text route (kwargs routes, window halves, temporal reductions, the
generic fallback, `mech.critical_speed`) uses to reduce a `<number> <unit>`
or one-multiplication scalar-arithmetic bound through `regolith-qty`'s unit
table -- never `_parse_float`'s leading-float truncation, which silently
dropped a unit (`<= 0.10 mrad` read as unitless 0.10) or a trailing factor
(`> 1.4 * 9200rpm` truncated to 1.4). An unresolvable bound defers NAMED
(`bound_unit_unresolved`/`bound_expression_unresolved`), never a truncated
number.
