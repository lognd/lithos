# cuprite Open Questions

> cuprite spec 0.10. The EOPEN list, plus sequencing questions. Regolith
> questions are [SOPEN-n] in `../regolith/`; mech questions in
> `../hematite/07-open-questions.md`.
> As of cycle 8 the technical queue is EMPTY: every remaining EOPEN was
> closed on existing machinery (section 2) or deferred with a stated
> reopen criterion (section 1a). Naming was settled in cycle 9.

## 1. Open decisions

None. EOPEN-1 CLOSED (cycle 9, D78; renamed cycle 10, owner's
decision): the electrical/computer language is **cuprite** (`.cupr`) --
cuprite is copper ore, and copper is the wire and current the language
reasons about; the mechanical language is **hematite** (`.hema`, iron
ore -> steel/structure); the package manager is **magnetite** (renamed from
quarry/lodestone, cycle 26, D132), and the shared toolchain is
**regolith** -- one geology theme. The corpus-rename sweep has landed.

## 1a. Deferred with reopen criteria (cycle 8; not "open", not forgotten)

Settled v1 postures whose extension is deliberately future work. Each
names the exact evidence that would reopen it. RE-REVIEWED under the
cycle-27 owner closure directive (D146): no new evidence exists for
any item, so every disposition below STANDS; the one
implementation-only item (EOPEN-13's cross-run nogood cache -- not a
spec question, D75) is queued as orchestrator work in TODO.md rather
than held here.

- **EOPEN-5 residue** (incremental re-route protocol): reopen only
  when a real design's *post-layout* claim failure cannot be closed by
  any pre-layout variable within its domain -- that is the first
  legitimate demand for layout-in-the-loop (D69).
- **EOPEN-8 residue** (first-class statechart): reopen only on a
  design needing *transition-graph* verification (unreachable mode,
  illegal transition sequence) that cannot be spelled as claims over
  config domains, mode-entry events, and sequencing masks (D71).
- **EOPEN-13 residue** (cross-run nogood cache): pure orchestrator
  work; the soundness condition is already stated (key on catalog
  record revisions). No spec evidence can reopen this -- it is not a
  spec question (D75).
- **Multi-FPGA floorplanning / partial reconfiguration**: EOPEN-17's
  v1 cut, unchanged.

## 2. Resolved in 0.10 (cycle 8 -- the final-pass closures)

Every item below was closed by *promoting its stated v1 posture to
settled*, with the mantra argument recorded in the cycle-8 log. The
common shape (F90): none of them needed new machinery -- each was
already answered by an existing regolith mechanism, which is the
definition of a spec that is done.

- **EOPEN-5 closed (D69)**: the lazy loop runs over pre-layout
  variables only (component values, budget shares, binding choices);
  layout is realize-once-verify. Post-layout failures blame back to
  pre-layout decisions through the ordinary conflict-driven search
  (blame sets already cross the realization boundary). An incremental
  re-route protocol is an orchestrator *optimization* with a stated
  reopen criterion (sec. 1a), not a held-open language question.
- **EOPEN-6 closed (D70)**: workload content stops at declared demand
  vectors (`loop`/`stream`/`event`/`batch` + typed `work`); v1 ships
  no dataflow sublanguage. This is not a deferral but a consequence of
  D60 (no host language in design source): a workload body expressive
  enough to compile to firmware or RTL is a program, and programs in
  design source break the charter's local verifiability. Deeper
  content enters exactly the way everything foreign enters: `by
  extern` images/RTL against a contract, with evidence (`by test`
  traces, WCET models). The HLS temptation is answered by the same
  rationale as the host-language ban -- one decision, two doors it
  closes.
- **EOPEN-8 closed (D71)**: operating modes ARE config variables --
  exposed by connections, blocks, or the system (regolith `04` sec.
  5), quantified by `forall`/`during`, with mode-entry events
  (`mode.enter(sleep)`) and sequencing masks covering the temporal
  side. Two examples that should have broken it (motor drive's system
  modes; Kestrel's `op` domain with per-mode power) did not. A
  statechart adds transition-graph semantics nobody has needed;
  reopen criterion in sec. 1a.
- **EOPEN-9 closed (D72)**: protocol conformance is structural in v1
  (roles bound, timing demands met -- T1/T2 + L5 timing claims from
  the `protocol` pack's templates). Transaction-level conformance
  needs no new mechanism *either*: a protocol pack that ships a
  behavioral `spec:` makes transaction conformance an ordinary T3
  equivalence obligation with declared coverage (insufficient coverage
  = indeterminate, honestly). v1 packs simply do not ship those specs
  yet; `assume!` carries the gap visibly. Model availability, not
  language design.
- **EOPEN-10 closed (D73)**: HIL results are `by test(ref)` evidence,
  the same class as mech lab reports and first-article inspection.
  The co-verification "boundary" was never a boundary: an HIL run
  discharges exactly the obligations whose claims it observed, keyed
  by content address like all evidence. No new mechanism, now
  settled rather than leaning.
- **EOPEN-11 closed (D74)**: EMC/EMI claims are writable now
  (budgets, masks, boundary `emc:` class) and discharged in v1 by
  `assume!` or `by test(chamber_report)` only. This is the honest-
  deferral machinery doing precisely its job: the claim structure is
  real, the harness models are far-future registry content, and
  `--release` refuses an unacknowledged assumption. Posture settled;
  chamber-model packs can arrive any time without a spec change.
- **EOPEN-13 closed (D75)**: learned nogoods are per-run solver state
  in v1 (regolith `07` sec. 7 already says nogoods are never lockfile
  content). Cross-run reuse is sound iff the cache key includes every
  catalog record revision the nogood's blame set consumed -- the
  INV-1 discipline applied to search state. Stated once, here;
  implementing it is orchestrator work with no spec surface.
- **EOPEN-14 closed (D76)**: WCET model availability is registry
  content, never spec. The harness ships conservative bound models for
  the Cortex-M class (simple pipelines, documented flash wait-states);
  everywhere else the honest posture is `by test` traces feeding
  measured bounds with declared error models. A new architecture is a
  new model pack; `info.wcet` claims are architecture-agnostic by
  construction.

## 2a. Resolved in 0.9

- EOPEN-12 settled (cycle 7, D58) on three transcribed records
  (`examples/registry/`): stm32g0 (atomic functions -- flat pin table
  suffices), atsamd21 (F85: SERCOM pads force the `function_modes:`
  role->pad constraint tables, incl. joint-legality combos), rp2040
  (column-rule grid + the PIO wildcard as an ordinary any-pin domain;
  mandatory-companion `demands:`). Schema: limits + derating +
  resources + functions + function_modes + packages + straps +
  models. Values await datasheet-hash verification and are honestly
  `tier=community` -- the trust machinery carrying transcription risk.
- EOPEN-18 closed (cycle 7, D57): harvest boundaries = environmental
  resource as profile-structured boundary truth (`supply:` reserved
  for definite sources); `convert(<from> -> <to>)` endpoint schema;
  `store(q)` retains any quantity (registered overload: retention);
  accumulation claims take profile windows (regolith `02` sec. 5;
  elec `02`).
- Log-unit views close SOPEN-5 (cycle 7, D56): see section 3; the
  Kestrel link budget is now a real dB claim, not an assume!.

## 2b. Resolved in 0.8

- EOPEN-17 closed (cycle 6, D47): host binding = capability matching
  with per-bank IO records, `hosted_on` pin, planner cause. Settled by
  the second worked example (`examples/systems/cubesat/payload.cupr`: sub-LVDS
  and 3.3V SPI forced onto two different banks of one part).
- Intent partition pins spelled (D48): inline `hosted_on <part>` on
  intents (`02-intent-layer.md` sec. 5) -- the lock-family word
  generalized, not a new mechanism.
- Budget `kind=` is pack-provided (D49): std adds `mass` and `energy`
  kinds; members may span domains (regolith `04` sec. 5.4).
- Artifact-typed caller params (D54, then [LEANING]; **settled in
  0.10**, cycle 8, D62): `board ObcPcb<fw: image>:` -- see the
  regolith contract doc. The corpus already held the second organic
  use (`PayloadPcb<bits: image>`, F88).

## 2c. Resolved in 0.7

- EOPEN-4 retired (cycle 5, D46): parameterized `from_fn`/`from_table`
  masks cover every observed waveform-template case; a solved
  constraint system over segments has no failing example demanding it.
  Reopen only on one (`03-behavioral-layer.md` sec. 7).
- Claim-position two-sided comparator spelling settled (D42): infix
  `within [lo, hi]`, never `= within` (regolith `03`).

## 2d. Resolved in 0.6

- EOPEN-7 fully closed: the formal sketch (schedule-invariance of
  observable traces via the delta property of coupling elements) is
  written into `03-behavioral-layer.md` sec. 1a. Do not reopen without
  a failing example.
- Invariant-audit adjustments landing in elec (design log cycle 4):
  intent latency reconciles through flow-chain budgets (`05` sec. 1);
  host binding gains IO banking; hints defined as never load-bearing.

## 2e. Resolved in 0.5

- EOPEN-7 core -> event-bounded hybrid semantics: SR within a clock
  domain, DAE between instants, converter-port-only coupling,
  non-instantaneous converters (no cross-boundary algebraic loops by
  construction) (`03-behavioral-layer.md` sec. 1a; design log cycle 3,
  D32). Decided by `examples/tracks/cuprite/sampled_buck.cupr`.
- SOPEN-4 -> `policy:` blocks: `prefer` (soft), `forbid` (hard),
  global `minimize` objectives at policy altitude (regolith `12`
  sec. 4).
- Expert ladder + in-source `waive` + external linkage (`by extern`,
  supplied plans, prebuilt images) land regolith-wide (regolith
  `12`, regolith `08` sec. 4); elec surface: DRC/ERC waives, Verilog
  linkage, `locked: pinmux(...)`, `hosted_on`.
- Discrete-time loop claims sketched: `elec.phase_margin(loop(...))`,
  `elec.limit_cycle(loop(...))` (harness models future work).

## 2f. Resolved in 0.4

- EOPEN-15 (intent -> workload) -> `realizes` with an exactly-one-
  realization ledger, L2 demand implication, and derived workloads for
  unrealized intents (`05-computer-track.md` sec. 1; design log
  cycle 2, D25).
- EOPEN-16 (analog net discipline) -> v1: terminal ledger +
  `discard`ed terminals, reference reachability, at most one
  voltage-imposing terminal (`arbitrate ... parallel` to share),
  supply-short detection (`03-behavioral-layer.md` sec. 2; D26).
  KCL/DAE well-formedness rides with EOPEN-7.
- Panelization -> planner territory, plan = evidence; module-on-carrier
  is the `pieces:` binding (`04-structural-layer.md` sec. 2; D27).
- SOPEN-2 core -> settled via the two xdomain examples: import-based
  cross-language reference, declaring-system obligation ownership,
  boundary subsumption (regolith `10` sec. 3; D23/D24/D29).

## 2g. Resolved in 0.3

- Behavioral discrete construct renamed `on <event>:` (was
  `process on`; collided with the [S] manufacturing `process`).
- `impl by circuit` body shape: component classes + `nets:` joins
  (`03-behavioral-layer.md` sec. 2).
- Supply ports carry direction: `supply(in|out, ...)`.
- Bus bit ranges `[i .. j]` (half-open, semantic position) and `.bits`
  blessed; regolith `02` sec. 3.
- Claims over interior structure -> derived-structure handles through
  the intent namespace (`02-intent-layer.md` sec. 4a).
- Budget human-fixes -> `locked:` (the lock family; `pins:` was fatal
  vocabulary here and is retired regolith-wide).
- `demands:` confirmed as the elec spelling of the regolith demands
  block.

## 2h. Resolved in 0.2 (was open in 0.1)

- EOPEN-2 (verb set/extension) -> core verbs + package-defined verbs
  (`std.intents`, `std.debug`); regolith `11-packages-and-stdlib.md`.
- EOPEN-3 (allocation search) -> declared-partition-first over the
  regolith's conflict-driven greedy search with lazy verification and
  blame-set backjumping (regolith `07-claims-and-evidence.md` sec. 7).
- SOPEN-1 (time structure) -> events/windows/masks in the quantity core,
  shared with mech (regolith `02-quantity-core.md` sec. 5).
- Region ownership -> lifted into the regolith as first-class owned
  regions (regolith `05-ownership-and-queries.md`).
- `communicate` scope -> boundary-only; internal links are derived flow
  realizations (`02-intent-layer.md` sec. 1).
- Debug targets -> targets + reserves (regolith `04-contracts.md`
  sec. 6).
- Abstract vs concrete blocks -> `block`+`spec:` as functional contract;
  `impl ... by spec/composing/circuit/vendor` with equivalence
  obligations (`03-behavioral-layer.md`).

## 3. Regolith feedback (things elec design pressure-tests)

- [SOPEN-2] core settled in 0.4 (see regolith `10` sec. 3): two
  mechatronic examples worked end-to-end without schema changes.
  Remaining residue is toolchain, not schema: T2 conformance tooling
  for foreign-domain roles (running mech measurements inside an elec
  build and vice versa) -- post-Phase-C orchestrator work; the
  interface schema is closed.
- [SOPEN-3] fully resolved: the registry **hosting model** is designed
  in regolith `11` sec. 10 (cycle 8, D77 -- federated
  content-addressed sources, sparse index, signing carries trust
  tiers, yank-not-delete, vendoring); naming settled in cycle 9
  (D78/D80) and renamed in cycle 26 (D132): the package manager is
  **magnetite**; the registry carries no separate name.
- [SOPEN-4] resolved in 0.5: `policy:` global objectives (regolith
  `12` sec. 4).
- [SOPEN-5] resolved in 0.9 (cycle 7, D56): **logarithmic unit
  views** (regolith `02` sec. 5a) -- log units view linear
  quantities; referenced (dBm/dBW/dBuV) vs unreferenced (dB/dBi/dBc);
  sum legality = at-most-one-reference after cancellation (validated
  by grammar experiment: accepts every link-budget shape, rejects
  dBm+dBm at L1); corners commute through the monotone view, so
  margin math stays linear and untouched.
- [SOPEN-6] resolved in 0.9 (cycle 7, D55): **the geom role kit**
  (regolith `10` sec. 3a) -- seven domain-neutral role predicates,
  each a declared-measures + T2-measurement pair both realizers can
  evaluate; shared layout constructors; derived datums; versioned
  registry content under coherence. The Kestrel contract pack now
  conforms.

## 4. Sequencing

The elec track intentionally trails mech by one phase: mech Phase B (the
geometry-free linter) proves the regolith's static machinery; elec
Phase A (write 5-10 real designs in target syntax: this thermostat, a
buck converter, a motor controller, one FPGA+MCU board) starts then,
reusing the regolith implementation directly. The single highest-value
early artifact is the same as mech's: a `cuprite check` that catches
driver conflicts, domain-crossing violations, level mismatches, and
budget non-closure with zero layout and zero simulation.
