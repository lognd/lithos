# WO-87 -- Elec entity-population pass + rule-eval registry dereference

Status: done (2026-07-10; escalated as F117, ratified as D198, then
  executed same day -- see "Close-out" below)
Language: Rust (regolith-lower/-sem) + Python (only if the rule
  surface needs plumbing)
Spec: WO-79 close-out item 3 (the named gap, verbatim); WO-29
  (lowering output surface -- this is its recorded elec remainder);
  cuprite/08 (board decls); toolchain/21-rule-packs.md (rule engine,
  quantified domains); design-log 2026-07-10-cycle-32 F112;
  design-log 2026-07-10-cycle-33 opener.

## Goal

The five std.board_correctness packs (WO-79) quantify over
`power_pins` / `config_straps` / `exposed_connectors` / `crystals` /
`critical_nets` -- all `EntityKind::Other`, populated by NO landed
lowering pass for a `board` decl. Both hazard and fixed corpus
boards therefore compile with zero rule firings; the packs' only
live evidence is their own fixture `expect:` cases. Land the
entity-population pass so the rules fire on REAL boards:
`examples/negative/66_board_correctness_hazard.cupr` must trip
every family; `examples/tracks/cuprite/board_correctness_fixed.cupr`
must stay clean. (`jlc_2l` / `std.elec.patterns.decoupling` carry
the identical gap -- the same pass un-blocks them; verify, do not
special-case.)

Second deliverable (F112's paired ask): rule-eval registry
dereference -- a rule expression that names a registry record field
(the packs' `per:` citations pattern) resolves through the loaded
records instead of failing/deferring; scope exactly to what the
five packs' rules need, no speculative generality.

## Deliverables

1. A lowering pass (regolith-lower, wired per the pass-driver
   serialization rule -- check nothing else in flight edits the
   driver) that populates the five domains from a `board` decl's
   real structure: power pins from supply-net membership, config
   straps from strap/boot-pin bindings, exposed connectors from
   connector instances with `exposure_class`, crystals from crystal
   instances, critical nets from the packs' declared criteria.
   Entity kinds: promote from `EntityKind::Other` only as far as
   the entity DB's existing kind vocabulary allows WITHOUT a schema
   bump; if a new kind is unavoidable, STOP and escalate (WO-85
   owns this cycle's bump; a second bump serializes behind it,
   D168).
2. Rule-eval registry dereference for record-field access in rule
   predicates (the engine's existing resolves:/INV-21 cause
   discipline; one dereference seam, no second record loader).
3. Tests: per-domain population unit tests (Rust, beside the pass);
   the hazard board trips >= 1 rule in EVERY family and the fixed
   twin stays zero-firing (pytest over the real pipeline); rules
   test fixtures stay green; goldens regenerated not hand-edited.
4. Docs: guide 15-board-correctness.md loses its honesty caveat
   (the "zero entities committed" note) in the same change; WO-79
   ledger cross-updated; WO-29 remainder marked closed in its file.

## Acceptance criteria

- `regolith check` over the five packs + hazard board renders the
  per-entity firings (diagnostics > 0, correctly attributed);
  fixed twin renders zero.
- mainboard_mx release build: board-correctness obligations move
  from never-formed to formed-and-evaluated (record before/after).
- No SCHEMA_VERSION bump in this WO.
- `make check` green.

## Dependencies

WO-79 (landed, defines the packs), WO-28 engine (landed). Pass
driver: serializes with WO-85 IF both edit regolith-lower's driver
-- coordinate at integration (WO-85 is in flight; this WO's pass
insertion point must rebase over whatever WO-85 lands there).

## Escalation (2026-07-10, design-log cycle-33 F117)

First-dispatch execution found this WO blocked on three facts the
body does not resolve; per README dispatch-protocol step 5
(architecture ambiguity -> escalate, never invent), no code was
landed. Summary (full analysis + recommended architecture in the
design log):

1. No elec structural entity layer exists. `regolith-lower` commits
   no `EntityKind::Net`/`Instance`/`Port` for a `board`/`system`
   decl today; deliverable-1's sources presuppose a net/instance/
   port extraction that is WO-24/WO-35 realizer-grade and unbuilt.
2. The "un-block jlc_2l / std.elec.patterns.decoupling, no special-
   casing" criterion forces populating real `EntityKind::Net`
   entities (decoupling quantifies `forall n in nets`, deferred
   because `Net::known_measure_keys()` is `None`). A board-domain
   `Other(...)` constructor shortcut fires the five board packs but
   leaves decoupling/jlc_2l deferred -- failing this criterion.
3. Deliverable 2's rule-eval registry dereference needs registry
   records inside the Rust rule engine (`EvalCtx` has no registry
   handle). Records load ONLY in Python's magnetite `RecordStore`;
   the sole channel into `regolith-lower` is `RealizedInputs`.
   Feeding records there is an architecture decision (channel +
   payload shape) the WO does not make. Deliverable 1's crystal/
   connector/strap classification needs the same records.

Also unscoped: the corpus hazard/fixed boards are empty attachment
shells, so deliverable 3 requires authoring real divergent board
structure into both files.

Recommended redispatch (design-log F117): records-into-Rust via the
existing WO-42 realized-input channel (`kind: "registry.records"`),
a board-population pass extracting Net/Instance/Port + derived
domains, `known_measure_keys()` grown for the board vocabulary, an
`EvalCtx` registry handle for the dereference, and authored corpus
structure. No new EntityKind, no SCHEMA_VERSION bump. Owner
ratification needed on the records-payload channel shape and on
whether the net/instance/port extraction is in scope here vs
deferred to WO-24/WO-35 -- no reopen without it.

## Close-out (2026-07-10, executed under D198's rulings)

1. The pass: `crates/regolith-lower/src/board_entities.rs`, run
   inside `lower.entities` (`entities.rs`, right after the `then:`
   feature materialization -- the WO-85-current driver threads the
   registry payload from `lib.rs` into `build_entities_with_registry`
   and `run_checks_with_registry`). Declared topology only (D198):
   `then:` `vendor(<key>)` instances, `nets:` block entries AND
   `connect:` mating lines, `straps:` bindings; derived domains per
   the module doc (power_pins from the record's `power_pin_names` x
   net membership; capacitor tiers load/bypass/bulk from
   `capacitance_pf`; crystals' `c_load_calculated` as the two load
   caps' series value; exposed connectors/nets via `exposure_class` +
   tvs counts; critical nets = rails + strap-bound nets; per-net
   `undecoupled_power_pin_count` for the decoupling sweep).
   `supervised_rails`/`clock_nets` are vocabulary-only (no honest
   declared-tier source; empty = vacuous, never fabricated).
2. Records channel (D198 ruling 1): Python
   `regolith/magnetite/records_payload.py` serializes every
   `[[component]]` row under the resolved record roots (the ONE
   loader home); `crates/regolith-lower/src/registry.rs`
   deserializes; `kind: "registry.records"` spelled in exactly those
   two places and pinned by `tests/test_wo87_board_population.py`.
   Attached automatically by `orchestrate.build()` (from the D192
   record roots) and the CLI `check` verb
   (`resolve_records_roots_for_paths`: nearest manifest, then the
   dev stdlib walk).
3. Rule-eval registry dereference: `EvalCtx.registry` -- a bound
   entity's missing measure resolves through its `record` measure
   into the loaded record (`x.cl` -> `cl_pf` -> `18pF`, the
   unit-suffix convention), plus the absolute
   `registry.<key>.<field>` path; scoped to exactly that (no
   speculative chains). No registry handle = the term defers as
   before.
4. Engine semantics shift (the jlc_2l/decoupling un-block):
   `EntityKind::Net` + the eleven board-domain `Other(<word>)`s
   gained `known_measure_keys` vocabulary (ONE home,
   `regolith-sem/src/entity.rs`), so those domains EVALUATE instead
   of deferring: populated entities check per-entity, an empty
   domain is a genuine vacuous pass (the "part with no holes" law).
   Consequence regenerated into the goldens: espresso's
   `erc(jlc_2l.fanout_drive)` unpopulated-domain deferral became a
   declared-tier vacuous pass (ControlPcb declares no nets; the
   realized netlist tier, WO-24/35, re-forms aggregate checks).
   Attachment fix ridden along: multi-line `process=<pack>(...)`
   argument lists (the board_correctness corpus spelling) now
   resolve -- the parser sweeps continuation lines into opaque
   islands the candidate scan now reads.
5. Corpus: the hazard/fixed twins carry real divergent topology; the
   hazard board fires >= 1 rule in EVERY family with per-entity
   attribution (15 E0601s), the fixed twin renders zero diagnostics
   with exactly three honest realized-tier deferral obligations
   (shunt_cap_placement, vbus_inrush's `.where` filter,
   test_point_probe_clearance). mainboard_mx's carrier board
   attaches the five packs over its declared bring-up hardware:
   release-build obligations moved 31 (0 board-correctness,
   never-formed) -> 33 (2 formed-and-evaluated deferrals, zero
   violations) under `regolith build --release
   examples/flagships/mainboard_mx stdlib/std.board_correctness`.
   New stdlib records (sourcing law): capacitors.toml, mcus.toml
   (rp2040 `power_pin_names`), protection.toml (PESD5V0S1BA),
   dft.toml (probe pad, SWD header). The negative-corpus harness
   gained the `# WITH:` directive (extra session roots + records)
   so the hazard `EXPECT: E0601` contract is enforced.
6. Tests: Rust per-domain population units beside the pass
   (8 in `board_entities.rs`), registry/deref/attachment units in
   `rule_engine.rs`/`registry.rs`/`rules.rs`;
   `tests/test_wo87_board_population.py` (per-family firing, fixed
   twin, decoupling un-block both ways, mainboard, kind-string pin,
   no-records honesty). `regolith rules test` stays green over all
   five packs. Goldens/deferral corpora regenerated via
   `REGOLITH_UPDATE_GOLDEN=1`, never hand-edited.
7. Residuals (named, not dropped): pack SOURCES enter a session by
   explicit root or local copy (the espresso jlc_2l precedent) --
   auto-joining `[depends]` rule-pack sources to the parse session
   is a separate design question, not taken here; the strap POLARITY
   cross-check rule WO-79 item 6 wanted is now WRITABLE (the deref
   seam exists) but stays future pack growth; `Port` entities are
   committed only as net-member spellings (no port-level rule quantifies
   yet -- add when one does).
