# WO-79: board-correctness rule packs, wave 1

Status: done (wave 1 landed 2026-07-10; see close-out below)
Depends: WO-28 engine (in-language rules, landed), WO-40 lints,
AD-21/AD-34, charter 36 (NORMATIVE), D186/D187. Record-field gaps
(crystal CL, MCU strap tables, connector exposure class) are IN
scope as additive stdlib fields/records under the sourcing law.
NO schema bump; no crates/ (a rule-engine gap escalates).
Language: in-language rule packs + records + Python fixtures/tests.
Spec: docs/spec/toolchain/36-board-correctness.md, 21-rule-packs.md,
32-stdlib-depth.md sec. 1.

## Deliverables

1. The five wave-1 families (charter sec. 2) as `erc:`-family
   packs: >= 3 demand rules each, `per:` citations (vendor app
   notes/standards named with revision), expect pass/fail fixtures
   per the AD-21 mandatory-fixture law.
2. Supporting record fields/records (additive, cited): crystal
   records with CL; MCU family strap/reset-requirement fields where
   the datasheet states them; connector exposure classes.
3. The hazard fixture board (examples/negative or fixtures/): trips
   every family; the fixed twin passes.
4. Coverage visibility: whatever the landed audit surface already
   renders (rules run/fired/passed per subject) verified for these
   packs; a genuine surface gap is an escalation, not a new report.
5. Docs: guide section (the encoded checklist, how to declare N/A),
   charter cross-refs, WO ledger. `regolith rules test` green over
   every pack.

## Acceptance: charter 36 sec. 5 verbatim; make check green;
Status flipped.

## Close-out (2026-07-10)

1. Five `erc:`-family packs, `stdlib/std.board_correctness/*.cupr`
   (magnetite.toml `provides.board_correctness`): `pdn_decoupling`
   (4 rules), `bringup_config` (3), `interface_protection` (3),
   `clock_discipline` (4), `dft_test_points` (3) -- 17 rules total,
   every one with a `per:` citation and a `pass:`/`fail:` `expect:`
   pair (30 fixture cases). `regolith rules test
   stdlib/std.board_correctness/*.cupr` is green (`ok=True`).
2. Additive record fields (sourcing law, `32-stdlib-depth.md` sec.
   1): `stdlib/std.elec/records/crystals.toml` (new, 3 crystal
   records with `cl_pf`, hand-cited to Abracon/ECS datasheets);
   `stdlib/std.elec/records/connectors.toml` (`exposure_class` field
   added to all 8 existing connector records, evidence
   method=derived, this repo's exposure taxonomy cited); MCU
   `demands:` gain `debug_header:`/`reset_supervisor:` on
   `examples/registry/{rp2040,atsamd21,stm32g0}.cupr`, each cited to
   the part's own datasheet section (RP2040 datasheet sec. 2.3.4/
   2.19.2; DS40001882 sec. 12/18; DS12232 sec. 5.3.15/5.1.2).
3. Hazard fixture: `examples/negative/66_board_correctness_hazard.cupr`
   attaches all five packs; fixed twin
   `examples/tracks/cuprite/board_correctness_fixed.cupr` (acceptance
   corpus, `test_corpus_clean.py` green). Honest limitation recorded
   in both files' headers and in guide sec. 4: the domains these
   rules quantify over (`power_pins`, `config_straps`,
   `exposed_connectors`, `crystals`, `critical_nets`) are
   `EntityKind::Other` and are NOT populated by any landed lowering
   pass for a `board` decl today (the WO-29 entity-population
   remainder -- `jlc_2l`/`std.elec.patterns.decoupling` carry the
   identical gap already). Both files therefore compile clean with
   zero rule firings today; the "trips every family" evidence that
   IS exercised today is the packs' own 15 `fail:` `expect:` cases
   (`regolith rules test`). Named growth, not silently dropped: real
   per-entity firing on the hazard board is blocked on WO-29's
   remainder landing, not on anything in this WO's scope.
   [CLOSED by WO-87 (D198), 2026-07-10: the board entity-population
   pass landed (`crates/regolith-lower/src/board_entities.rs`); both
   boards carry real declared topology now, the hazard board trips
   every family live with per-entity attribution, and the fixed twin
   is zero-firing (`tests/test_wo87_board_population.py`). The
   deferral text above is history, kept verbatim.]
4. Coverage visibility: `regolith check` over all five packs plus
   both hazard/fixed boards together renders `diagnostics=0
   obligations=0` -- consistent with #3 (zero entities committed in
   those domains today, so the landed audit/parity surface
   (`python/regolith/backends/parity.py`'s `dfm(`/`drc(`/`erc(`
   provenance classification) has nothing to render yet, honestly).
   No surface gap found beyond the already-named WO-29 remainder; no
   new report needed.
5. Docs: `docs/guide/15-board-correctness.md` (the encoded checklist
   table, attachment syntax, the waive-based N/A declaration, the
   record fields, the hazard-board honesty note, the post-mortem
   law). This WO ledger entry is the charter cross-ref (charter 36
   already names WO-79 as its machinery; no charter text changed).
6. Wanted-but-unreachable rules (named growth, not cut silently):
   a per-supply-pin realized DISTANCE bound beyond the placement-
   corner rule already shipped (`pdn_decoupling.shunt_cap_placement`
   is the realized-fact-tier rule that DOES exist; a full copper-
   pour/plane-impedance check needs a PDN-impedance solver, out of
   this WO's rule-pack surface entirely -- feldspar territory);
   register-level MCU strap POLARITY cross-checks against the actual
   schematic pull direction (needs a live component-record
   dereference at rule-eval time -- design doc D-B's "registry-record
   dereference" feature is NOT implemented by the landed engine,
   `crates/regolith-lower/src/rule_engine.rs`'s `EvalCtx` has no
   registry lookup, only `capability`/`env`/`measures` -- a rule-
   engine gap, escalated here, not invented around) [the registry-
   dereference seam LANDED in WO-87 (D198): `EvalCtx.registry`; the
   polarity cross-check RULE itself remains future pack growth]; full EMC
   pre-scan and SI eye/crosstalk analysis (charter sec. 4 non-goals,
   correctly out of scope). Grammar-layer escalation: the bare plural
   words `boards` and `assemblies` as a `forall ... in <word>` domain
   parse into a shape `ForallClause::var()`'s direct-child-token scan
   does not resolve (`asm.debug_header_count` reports
   `not_evaluable` even though the identical demand text works under
   any other domain word, e.g. `control_boards`) -- reproduced
   minimally, worked around in `bringup_config.cupr` by using
   `control_boards`, and escalated here per this WO's "no crates/"
   boundary (a `regolith-syntax`/`regolith-lower` fix, not a rule-pack
   authoring fix).
7. `make check`: green (see repo CI run at close-out commit).
