# Declarative Engineering Languages -- Documentation

Three declarative, goal-oriented design languages built on one shared
regolith:

- **hematite** -- mechanical design (parts, processes, assemblies).
- **cuprite** -- electrical and computer design (circuits, boards,
  logic, processors).
- **fluorite** -- fluid circuits (feed systems, coolant loops,
  hydraulics, pneumatics; ratified cycle 20, D93).

Named (D78, renamed cycle 10; fluorite cycle 20): one geology theme --
**hematite** is iron ore (steel, structure -> mechanical); **cuprite**
is copper ore (wire, current -> electrical); **fluorite** is the
mineral named for flowing (flux -> fluids); the **quarry** (package
tool) extracts them, and the **lodestone** registry indexes them, all
worked by **regolith** (the shared toolchain). The whole project --
the languages, toolchain, and registry together -- is umbrella-branded
**lithos**.

All of them invert the traditional workflow:

```
Traditional:  Implementation -> (manual analysis) -> "does it work?"
Here:         Claims + Contracts -> (solvers, provers) -> Implementation + Evidence
```

The designer declares what the artifact must do, how it will be made, and
what it promises to other artifacts. The system derives the implementation,
allocates the numbers nobody wants to pick by hand, and attaches evidence to
every physical claim. Text is the single source of truth: diffable,
reviewable, and statically checkable without rendering or simulating
anything -- which makes design generation (human or LLM) a locally
verifiable problem.

The languages are deliberately "different vocabularies over the same
machinery": the type system, the contract model, the ownership discipline,
the claim/obligation/evidence pipeline, the lowering architecture, and the
build system are all defined once, in the regolith, and bound per domain.
Learning one language should mean already knowing 80% of the other.

## Reading order

1. `regolith/` -- the abstract backing layer. Read this first; every
   language track is an instantiation of it.
2. `hematite/` -- the mechanical language (hematite). The mature track: unified
   spec 0.13, consolidating drafts 0.1-0.12.
3. `cuprite/` -- the electrical and computer language (cuprite). Design-phase
   sketch, structured to mirror the mechanical track.
4. `fluorite/` -- the fluid-circuit language (fluorite). Ratified v1
   (cycle 20); the youngest track, born from solver-side demand.

## Directory map

```
docs/
  regolith/    the shared abstract layer (domain-neutral)
    01-principles.md              mantras, defaults test, four-component architecture
    02-quantity-core.md           quantities, units, intervals, zones, registries
    03-value-sources.md           the five-source grammar for every number
    04-contracts.md               interfaces, connections, conformance, vendors
    05-ownership-and-queries.md   entity DB, queries, borrows, datums, symmetry
    06-execution-model.md         stages, scopes, snapshot/commit semantics
    07-claims-and-evidence.md     obligations, signatures, margin-driven discharge
    08-lowering-architecture.md   the generic L0-L6 stack
    09-build-and-lockfile.md      build tiers, lockfile, diagnostics, deferral
    10-domain-binding.md          the regolith-concept x domain binding table
    11-packages-and-stdlib.md     package manager (quarry), registries, trust,
                                  stdlib; projects, files, and team workflow
    12-overrides-and-hints.md     the expert ladder: pins, hints, policy,
                                  override-by-evidence, waive; audit surface
    13-invariants.md              the invariant ledger (INV-1..27): every
                                  guarantee with mechanism + proof argument

  hematite/    hematite -- mechanical track (spec 0.13, unified)
    01-overview.md                vision and architecture
    02-language.md                parts, stages, scopes, features, profiles, queries
    03-contracts-and-assemblies.md  interfaces, matings, assemblies, tolerances, fits
    04-vocabulary.md              every keyword: position, meaning, lowering
    05-lowering.md                mech L0-L6 and the construct x level matrix
    06-roadmap.md                 implementation phases
    07-open-questions.md          OPEN / SEAM / watchlist, consolidated

  cuprite/    cuprite -- electrical + computer track (design sketch)
    01-overview.md                vision; circuit and computer sub-tracks
    02-intent-layer.md            named intents, flows, boundary -- no chips, no pins
    03-behavioral-layer.md        the HDL superset with continuous quantities
    04-structural-layer.md        component binding, pins, layout, DRC/ERC
    05-computer-track.md          workloads -> architecture -> RTL or vendor silicon
    06-lowering.md                elec L0-L6 and checks per level
    07-vocabulary-sketch.md       draft keyword tables, mapped to the regolith
    08-open-questions.md          EOPEN list

  fluorite/   fluorite -- fluid-circuit track, `.fluo` (RATIFIED v1,
              cycle 20 D93; drafted as calcite/.calc, now dead
              names; closes 20-solver-abstraction sec. 7 item 6)
    01-overview.md                scope, personas, seams, non-goals
    02-language.md                media, FluidPort, components,
                                  flownets, states, claims
    03-lowering.md                flownet payload, obligation shapes,
                                  cross-track couplings
    04-open-questions.md          FOPEN ledger (deferrals with
                                  reopen criteria)

  design-log/   dated findings + decisions ledgers, one per design cycle

  implementation/  agent-executable work orders (WO-nn) for building
                   the toolchain; conventions + dependency graph in its
                   README

../examples/    source files in target syntax (spec pressure tests)
  mech/pillow_block.hem          profile, stages/setups, patterns, zones,
                                  role binding, CAM claims, retro-contract
                                  on import, one assembly
  mech/sheet_bracket.hem         sheet metal, `free`+DFM, profile holes/
                                  regions, interface-envelope loads
  mech/weldment_frame.hem        multi-piece parts (`pieces:`), joining
                                  stage `align:`, post-weld machining
  mech/molded_clip.hem           variants, molding DFM, `within [lo,hi]`,
                                  fatigue claims
  mech/torch_igniter.hem         end-to-end flagship: lathe+mill pipeline,
                                  zones, mechanism claims, budget, todo!/
                                  assume!, trust floors
  mech/gear_reducer.hem          mesh_alignment budget in anger; ladder
                                  rungs 2/3/4/5/7; supplied G-code plan
  elec/thermostat.cupr            boundary intents, derived buses, targets,
                                  budgets, derived-structure handles
  elec/mux6to64.cupr              abstract block vs concrete impls,
                                  equivalence obligations, orbit wiring
  elec/buck_converter.cupr        continuous spec, `impl by circuit`,
                                  masks, params vs generics
  elec/motor_drive.cupr           system modes, arbitrate, error budget,
                                  intent->workload `realizes`
  elec/fpga_mcu_board.cupr        CDC, bidir arbitrate, buy+build bind,
                                  two images, EOPEN-7 observations
  elec/sampled_buck.cupr          the EOPEN-7 decider: continuous plant +
                                  sampled loop, converter ports, loop claims
  computer/flight_controller.cupr workloads, architecture, bind, firmware
                                  image claims (fit/stack/WCET/boot)
  xdomain/imu_board.cupr          SOPEN-2 pressure test #1: mixed-domain
  xdomain/sensor_pod.hem         interface, thermal handoff via effects:
  xdomain/servo_drive.cupr        SOPEN-2 pressure test #2: cross-language
  xdomain/servo_module.hem       import, boundary subsumption, mixed-
                                  domain vendor record, cross-track matings
  registry/stm32g0.cupr           EOPEN-12 record #1: atomic functions,
                                  flat pin table
  registry/atsamd21.cupr          EOPEN-12 record #2: SERCOM pads ->
                                  function_modes constraint tables (F85)
  registry/rp2040.cupr            EOPEN-12 record #3: column rules +
                                  PIO wildcard + mandatory companions
  registry/i2c_protocol.cupr      protocol pack shape
  cubesat/                        Kestrel: the LARGE multi-file stress
                                  project (cycle 6) -- 1U cubesat;
                                  quarry.toml manifest, shared contract
                                  pack, 4 boards + structure + antenna
                                  + top system; D47-D54 deciders, F74-
                                  F83 findings; EOPEN-17 settled here
```

## Status legend

Used throughout:

- **[SETTLED]** -- decided; changing it is a spec revision.
- **[LEANING: x]** -- default direction chosen, revisit allowed cheaply.
- **[OPEN-n] / [EOPEN-n] / [SOPEN-n]** -- needs a decision (mech / elec /
  regolith numbering).
- **[SEAM-n]** -- designed on both sides, the joint itself unspecified.

## Cross-domain future

A mechatronic system is one `system` with parts from both domains: a board
is simultaneously an electrical artifact and a mechanical one (mounting
holes, connector positions, dissipation as a thermal boundary on the
enclosure). The regolith's contract model is what makes this tractable --
an interface may carry roles and promises from more than one domain's
quantity namespaces. Deliberately out of scope until both tracks stand on
their own; see `regolith/10-domain-binding.md`.

## Conventions

- All documentation and source examples are ASCII-only. The languages
  themselves define ASCII canonical operator spellings (`&`, `dia`, `+-`,
  `deg`, `mu_`); formatters may render unicode, files never store it.
- Mechanical spec versions: 0.1 -> 0.2 -> 0.3 (archive) -> ... -> 0.12
  -> **0.13 (this tree)**. Electrical: 0.1 -> ... -> 0.9 -> **0.10
  (this tree)**.

## Revision log

**mech 0.13 / elec 0.10 / regolith additions** (this revision; full
ledger in `design-log/2026-07-03-cycle-8.md` -- the final pass: the
technical open queue is now EMPTY):

- **Every remaining technical OPEN/EOPEN closed** on existing
  machinery -- the meta-finding (F90) is that none needed a new
  mechanism. Mech: OPEN-2 (allocation policies are pack-provided
  budget math, D63), OPEN-3 (v2 kinematics is model packs over
  existing hooks; syntax provably sufficient, D64), OPEN-5 (constraint
  vocabulary = closed SolveSpace-equivalent set, D65), OPEN-6
  (re-import = re-pin + re-resolve + T2 re-run; the diff is a report,
  not a mechanism, D66), OPEN-8 (surface state joins the contact-
  record coherence key, D67), OPEN-11 (`refining` legality
  per-(op, geometry-class) in process modules, D68). Elec: EOPEN-5
  (pre-layout lazy loop, D69), EOPEN-6 (no workload sublanguage --
  a consequence of the host-language ban D60; D70), EOPEN-8 (modes
  are config variables, D71), EOPEN-9 (structural conformance;
  transaction depth is pack `spec:` content, D72), EOPEN-10 (HIL =
  `by test`, D73), EOPEN-11 (EMC posture = honest deferral, D74),
  EOPEN-13 (nogoods per-run; cross-run soundness condition stated,
  D75), EOPEN-14 (WCET models are registry content, D76). All
  deferrals carry explicit reopen criteria in the track
  open-questions docs.
- **Registry hosting model** (regolith `11` sec. 10; the technical
  half of SOPEN-3, D77): sparse append-only index + content-addressed
  archives; sources declared in the manifest; mirrors trivially safe
  (INV-22 corollary: hosting affects availability, never meaning);
  signing carries trust tiers, hosting does not; yank hides, never
  deletes; `quarry vendor` for offline; server-side computed-semver
  enforcement on publish.
- **D54 settled (D62)**: artifact-typed caller params, on D54's own
  criterion -- the corpus already held the second organic use
  (`PayloadPcb<bits: image>` beside `ObcPcb<fw: image>`, F88).
  Discipline recorded: injection, not templating (whole-artifact
  reference, permanent borrow, consume-never-modify).
- Stale-marker sweep: the `[ELEC-TBD]` profile row in the domain
  binding table (last stale marker in the tree, F89) now states the
  settled elec binding (parameterized waveform/mask templates, D46).
- Track READMEs' status lines updated to match reality (elec core is
  settled-by-example, not "[LEANING] at best"); the only open decision
  anywhere is naming (OPEN-10 / EOPEN-1 / tool+registry names), the
  owner's, due at Phase B start; candidate families in the cycle-8
  log sec. C.

**mech 0.12 / elec 0.9 / regolith additions** (previous revision; full
ledger in `design-log/2026-07-03-cycle-7.md` -- closing the
judgment-heavy queue before agent dispatch):

- **Logarithmic unit views** (regolith `02` sec. 5a; closes SOPEN-5,
  D56): log units view linear quantities; referenced vs unreferenced;
  sum legality = at-most-one-reference (validated by grammar
  experiment -- `dBm + dBm` dies at L1); corners commute through the
  monotone view. The Kestrel link budget is now a real dB claim.
- **The geom role kit** (regolith `10` sec. 3a; closes SOPEN-6,
  D55): seven domain-neutral geometric role predicates, each a
  declared-measures + T2-measurement pair both realizers evaluate;
  shared layouts; derived datums; versioned under coherence.
- **Energy-harvest vocabulary** (elec `02`; closes EOPEN-18, D57):
  `supply:` = definite sources only; environmental resources as
  profile-structured boundary truth; `convert(<from> -> <to>)`;
  `store(q)` retains any quantity (registered overload); profile
  windows on accumulation claims (regolith `02` sec. 5).
- **EOPEN-12 settled** (D58) on three transcribed MCU records: the
  SAMD21's SERCOM pads forced the `function_modes:` role->pad
  constraint tables (F85); the RP2040 adds column rules + the PIO
  wildcard; records honestly `tier=community` pending datasheet-hash
  verification.
- Claim subject `all` canonicalized, `all_parts` retired (D59);
  OPEN-7 settled for v1 (no host language in design source, D60);
  OPEN-12 closed (per-stage plans, D61); INV-17 extended with the
  log-view reference check.

**mech 0.11 / elec 0.8 / regolith additions** (previous revision; full
ledger in `design-log/2026-07-03-cycle-6.md` -- the LARGE-project
stress test):

- **Kestrel** (`examples/cubesat/`): a 1U cubesat as a ten-file
  project -- the first real exercise of projects/files/teams
  (regolith `11` sec. 9) and the corpus's integration flagship.
- Settled by the example: EOPEN-17 closed (D47, second FPGA example
  with a genuine two-bank IO conflict); intent partition pins spelled
  `hosted_on` inline (D48); budget `kind=` pack-provided, std gains
  `mass`/`energy`, members may span domains (D49); relative path
  imports resolve against the importing file (D51); orbit connections
  (`pairwise ... by <Mating>`) lifted to regolith vocabulary (D53);
  composite artifacts may impl interfaces across their parts (F82);
  config-domain references resolve per enclosing context like
  `boundary.` (F75); artifact-typed caller params [LEANING, D54] for
  image injection.
- Newly opened by the example: EOPEN-18 (energy-harvest boundary +
  ops-profile energy claims), SOPEN-5 (logarithmic quantities -- link
  budgets), SOPEN-6 (quantity-core geometric role vocabulary for
  cross-domain contracts).

**mech 0.10 / elec 0.7 / regolith additions** (previous revision; full
ledger in `design-log/2026-07-03-cycle-5.md` -- the fresh-eyes cycle):

- **Projects, files, and teams** (regolith `11` sec. 9): a project is
  manifest + source tree + one lockfile; files are containers, not
  scopes (new INV-27, file-layout invariance); named vs bare import
  forms defined (bare = registry contributions only; path imports must
  name); acyclic import graph; contract-first decomposition, shared
  evidence caches, and merge-by-rebuild stated as the team workflow.
- Claim-position two-sided comparator settled by grammar experiment
  (D42): infix `within [lo, hi]`, never `= within` (regolith `03`;
  two examples fixed).
- Artifact-position imports defined: `parts: x: import(path) [sealed]`
  is a one-stage part whose stage is named `src` (regolith `06`,
  mech `02` -- the form the examples already used).
- Image `partitions:` use the zones `remainder` rule; open-ended
  `[a ..]` ranges retired (D44).
- EOPEN-4 retired (D46): parameterized `from_fn`/`from_table` masks
  cover every observed case; no solved waveform-constraint system.
- Stale-marker sweep: OPEN-13/EOPEN-7/EOPEN-16 references cleaned from
  examples and vocabulary; mech `02` lead example fixed against its
  own path rule; mech `03` assembly example fixed to bind impls (not
  raw features), use `zones(...)`, and carry a coherent budget;
  missing `supply(in|out)` direction and `use by_spec` drift fixed;
  gear-reducer elisions completed so the corpus is self-contained.
- INV-15 enumeration gains the sketch DOF ledger; regolith `09` cause
  list aligned with INV-21.

**mech 0.9 / elec 0.6 / regolith additions** (previous revision; full
ledger in `design-log/2026-07-03-cycle-4.md`):

- **The invariant ledger** (new `regolith/13-invariants.md`,
  normative): all twenty-six load-bearing guarantees stated with
  mechanism, proof argument, and test family (WO-17 makes them
  executable); per-model obligations (corner maps, declared model
  shape) honestly flagged as the weakest links.
- Holes found by the audit, fixed: `@hint` droppability defined
  (hints never load-bearing; entity-DB symmetry reclassified as
  checked *facts*); orbit extension requires givens invariant under
  the orbit group (the asymmetric-load hole in verify-one); "base
  evidence remains valid under targets" corrected to the
  reserved-regions realization rule + content addressing (the
  parasitics hole); waivers cannot absorb resolution duties, get
  lockfile-recorded match sets with loud growth, face trust floors,
  and may `expires:`; reproducibility restated as
  decisions-and-identities with declared model determinism;
  intent->workload latency reconciles through the flow-chain budget
  (transport was ignored); semver comparison scoped to literal slots.
- Architecture re-audit of D1-D37 against the mantras: all affirmed;
  five adjusted as above (design log cycle 4, section B).
- EOPEN-7 fully closed (formal sketch in elec `03` sec. 1a);
  EOPEN-17 hardened with IO banking; waiver expiry decided (D40).
- Construct x level matrices updated for pieces/variant/waive/policy/
  extern (mech `05`, elec `06`); `--release` semantics restated
  (INV-24).

**mech 0.8 / elec 0.5 / regolith additions** (previous revision; full
ledger in `design-log/2026-07-03-cycle-3.md`):

- **The expert ladder** (new `regolith/12-overrides-and-hints.md`):
  one doctrine for every human redirect -- assert, pin, hint,
  override-by-evidence, force-model, assume, waive -- with the safety
  property that nothing can convert `violated` into `discharged`, and
  a four-trail audit surface (source, lockfile, ledger, release
  gates). New in-source scoped `waive` (evidence upgrades it to a
  release-permitted deviation); CLI `--waive` demoted to
  exploration-only.
- `policy:` blocks -- `prefer` (soft, search-ordering), `forbid`
  (hard, domain cut), global `minimize` objectives -- resolving
  SOPEN-4.
- **Manual lowering + external linkage** (regolith `08` sec. 4):
  `by extern(ref, format)` as the fifth impl strategy; level-by-level
  entry table (Verilog/DXF at L3, imports + opaque IP/prebuilt ELF at
  L4, supplied evidence at L5, supplied plans checked -- not
  regenerated -- at L6); the no-dead-uppers rule; `formats` package
  kind.
- EOPEN-7 settled in shape: event-bounded hybrid semantics (SR within
  a domain, DAE between instants, converter-port-only coupling,
  non-instantaneous converters), decided by
  `examples/elec/sampled_buck.cupr`; formal write-up is the residue.
- OPEN-1 closed (variants ride swept obligations + symmetry);
  OPEN-13 closed (`std.mech.weld` models + weld DFM rules);
  EOPEN-17 shape (host binding as capability matching, `hosted_on`).
- `locked: pinmux(...)` -- the one place a package pin may appear in
  design source.
- New examples: sampled buck (EOPEN-7 decider), gear reducer
  (mesh_alignment budget in anger + four ladder rungs + a supplied
  G-code plan); mux gains a `by extern` Verilog impl; sheet bracket
  gains an evidence-less waive (release-gated).

**mech 0.7 / elec 0.4 / regolith additions** (previous revision; full
ledger in `design-log/2026-07-03-cycle-2.md`):

- SOPEN-2 core settled after a second mechatronic example
  (`examples/xdomain/servo_*`): cross-language reference is the
  ordinary `import` (extension-dispatched); joint obligations belong
  to the declaring system; **boundary subsumption** (enclosing context
  must be contained in each import's declared boundary) added to the
  contract model (regolith `04` sec. 5.6, `10` sec. 3). Residue is
  T2 tooling, not schema.
- EOPEN-15 resolved: `realizes` with an exactly-one-realization
  ledger, L2 demand implication, derived workloads for unrealized
  compute intents (elec `05`).
- EOPEN-16 resolved (v1): analog net discipline -- terminal ledger +
  `discard`ed terminals, reference reachability, one voltage-imposer
  (`arbitrate parallel` to share), supply-short check (elec `03`).
- Panelization settled as planner territory (plan = evidence); the
  multi-piece `pieces:` row binds in elec to module-on-carrier
  (regolith `07`/`10`, elec `04`).
- OPEN-13 first half settled: weld feature taxonomy, `weld` joint
  entities with measures, distortion as position scatter (mech `02`
  sec. 7a); harness models remain open.
- F35: ad-hoc `@ <value>` claim point-conditions retired -- corner
  discipline owns worst-case evaluation.
- New EOPEN-17 (host binding for synthesized blocks, `hosted_on`
  pin); EOPEN-7 constraints recorded from the frame-grabber example
  (synchronous-reactive core leaning), still open pending a
  continuous-discrete feedback example.
- New examples: torch igniter end-to-end (mech flagship), FPGA+MCU
  frame grabber, servo drive + servo module (xdomain #2); sensor pod
  updated off the retired `artifact()` placeholder.

**mech 0.6 / elec 0.3 / regolith additions** (previous revision; full
findings ledger in `design-log/2026-07-03-cycle-1.md`):

- Vocabulary made collision-free: behavioral `process on` ->
  `on <event>:`; budget `pins:` -> `locked:` (lock family, was pin
  family); `dof: free=` -> `kept=`; block-impl naming via `as`;
  cross-track homonym policy (mech `04` sec. 1).
- Spellings defined: two-sided comparator literal `within [lo, hi]`;
  closed intervals `[a, b]` vs half-open ranges `[i .. j]`; bus
  slicing + `.bits` blessed as semantic addressing; count constructor
  `n x thing`; `import` documented.
- Parameter rule: `<...>` caller-chosen vs `params:` impl-chosen;
  inline promise refinement on impls (regolith `04`).
- Mech: multi-piece parts (`pieces:` + joining stages, weldments);
  `variant` axes (OPEN-1 shape); fatigue claim spellings (OPEN-4
  done); profile export anchoring; standalone-part loads via
  interface envelopes; TorchIgniter/Compression doc examples repaired.
- Elec: derived-structure handles (`report.supply`) for claims over
  interior structure; `impl by circuit` bodies (component classes +
  `nets:`, EOPEN-16); directional supply ports; config-variable
  exposers generalized (EOPEN-8); intent->workload `realizes`
  (EOPEN-15); EOPEN-12 record schema sketched in `examples/registry/`.
- SOPEN-2 pressure-tested end-to-end (`examples/xdomain/`): binding
  and thermal handoff work on existing machinery; the cross-language
  reference form and joint-obligation ownership remain open.
- New examples: sheet bracket, weldment frame, molded clip, buck
  converter, motor drive, sensor pod (x2), registry records (x2);
  all four originals repaired against the fixes above.
- Implementation work orders for agent execution: `implementation/`.

**mech 0.5 / elec 0.2 / regolith additions** (previous revision):

- Package manager + library-data standard: `regolith/11` (quarry;
  immutable revisioned records, computed semver, trust tiers, stdlib).
- Time/frequency-domain claims for both tracks: events, windows, masks,
  `peak/settles/overshoot/rms/stays_within` (regolith `02`, `07`);
  resolves mech OPEN-9 and old SOPEN-1.
- CAM as obligation -- planning-as-evidence: manufacturability/cost/time
  claims discharged by planner models; backends serialize plan evidence
  (regolith `07`, mech `02`/`05`).
- All four mech SEAMs redesigned into settled rules: stage-exit role
  binding + `refining` ops (SEAM-1), whole-orbit pattern binding
  (SEAM-2), swept obligations (SEAM-3), `zones over` blocks (SEAM-4).
- Elec intent layer rebuilt on boundary-vs-interior: `communicate` is
  boundary-only; internal buses/pins are derived flow realizations
  (the IMU/TWI rule); intent verbs are package-defined.
- Targets + reserves (debug LEDs, test points) as additive overlays that
  cannot invalidate base verification (regolith `04`).
- Abstract vs concrete blocks: `block`+`spec:` as functional contract,
  `impl by spec/composing/circuit/vendor`, equivalence obligations
  (regolith `04`, elec `03`).
- Conflict-driven allocation search: greedy descent, cheap-model
  screens, lazy verification, blame-set backjumping, learned nogoods
  (regolith `07`).
- Hardware-bug ledger (elec `03`) and eager return-path/noise screens +
  PDN budgets (elec `04`).
- Computer track deepened: peripheral demand vectors, `bind` blocks,
  firmware `image` with partitions and fit/stack/WCET/boot claims
  (elec `05`).
- Region ownership lifted into the regolith (`05`).
- Example-driven fixes from `examples/`: bare statements imply their own
  scope; orbit connection forms (`pairwise`, `flatten`, broadcast);
  `bind`/`partitions:`; `forall` confirmed as the only quantifier
  spelling; impl-naming rule for assemblies.
