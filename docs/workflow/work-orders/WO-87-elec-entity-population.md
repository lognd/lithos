# WO-87 -- Elec entity-population pass + rule-eval registry dereference

Status: todo
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
