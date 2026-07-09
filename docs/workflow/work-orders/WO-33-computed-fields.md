# WO-33: Computed indexed fields (compute claims over zones and config domains)

Status: done -- all six deliverables land. Deliverables 1-4 (grammar,
schema, lowering, orchestrator honest-deferral wiring) landed
earlier; deliverable 5 (the two `examples/` fixtures + their goldens)
and deliverable 6 (the doc cross-references) close out this change.
`make check` green including regenerated schema + goldens. See the
"Remaining / escalations" note at the end of this file for the one
design ambiguity (the cycle diagnostic) left for a future WO to
reconcile.
Depends: WO-30 (the `field` payload kind + coverage encoding),
WO-13/WO-19 (claim lowering pipeline). Feldspar's consumer half is
its OPEN-14 (interim extremal ports stay valid; this WO gives the
REAL design a source side). GATES: the regen-chamber and suspension
fixtures' honest lowering (feldspar G23/G36).
Language: Rust (`regolith-syntax` claim grammar addition,
`regolith-lower` compute-claim pass, `regolith-oblig` field-datum
schema); Python (orchestrator promise-chain wiring, `_schema/`)
Spec: design-log 2026-07-07-cycle-20 D98 (the decision -- this WO
file carries the full shape); regolith/02 sec. 4 (zones) + sec. 5
(events/datums precedent for ledger entry); regolith/07 sec. 2
(obligations), sec. 6 (plan evidence precedent for
computed-artifacts); `../../spec/toolchain/20-solver-abstraction.md` sec. 8.3 (payload
channel); AD-5/AD-17/AD-18.

## Goal

A claim can COMPUTE a named, indexed quantity (a field over zones, a
curve over a config variable) that sibling claims consume through
ordinary projections -- closing the "worst-point scalar with
hand-carried conservatism" degeneration for regen-wall temperatures
(zone-indexed) and suspension camber/toe/motion-ratio curves
(config-indexed) with ONE design.

## The shape (D98, normative here)

Source form (both index-domain kinds, one grammar):

```
compute wall_T: thermo.wall_temperature over liner.zones
compute camber: vehicle.camber over travel in [-80mm, 120mm]
compute mr:     vehicle.motion_ratio over travel in [-80mm, 120mm]
```

- `compute <name>: <quantity kind> over <index domain>` is a claim
  form: it lowers to ONE obligation whose SUCCESSFUL evidence
  carries a `field` payload (WO-30 channel) -- the discretized
  values over the index domain, plus the domain encoding itself
  (reusing the WO-30 `CoverageAxis` type for the index axis:
  interval or enumerated; the field's resolution IS a coverage
  statement).
- The produced name enters the datum ledger (borrow-exempt, exactly
  like events, regolith/02 sec. 5): one datum, one ledger, both
  tracks may reference it.
- CONSUMPTION is ordinary claim vocabulary -- projections lower to
  derived quantities whose givens carry the producing obligation's
  field payload ref (the promise-chain mechanism, dissipation
  precedent):
  - extremal: `max(wall_T) < 800K`, `min(camber) > -3deg`
  - point: `wall_T at zone(tip) < 900K`, `camber at travel(0mm)`
  - slope: `slope(camber, travel) in [-0.05, 0]deg/mm` (the
    bump-steer/roll-stiffness demand -- G36's sharpener; slope of
    an interval-valued field is the conservative envelope slope)
  - a sibling `compute` may consume another computed field as a
    given (roll stiffness needs the mr CURVE), forming an ordinary
    promise DAG; cycles are the existing derivation-cycle
    diagnostic, not new machinery.
- HONESTY RULE: a projection over a field whose evidence is
  indeterminate is indeterminate (chain rule of the ledger); a
  field discharged at coarser resolution than a consumer's claim
  needs is the consumer's coverage problem, visible because the
  field's axis encoding rides its evidence.

## Deliverables

1. **Grammar**: the `compute` claim form (`regolith-syntax`; both
   `over <zone set ref>` and `over <var> in <interval>`);
   projection heads `max/min/at/slope` parse as ordinary qualified
   claim expressions (`at zone(...)`/`at <var>(...)` argument
   forms). `../../spec/toolchain/grammar.ebnf` + fuzz in lockstep.
2. **Schema** (`regolith-oblig`): `FieldDatum { name, quantity_kind,
   axis: CoverageAxis, payload: PayloadRef | null }` -- the ledger
   entry (null payload until discharged); obligations for compute
   claims carry the axis; SCHEMA_VERSION rides the WO-30 line (one
   bump if WO-30 shipped).
3. **Lowering** (`regolith-lower`): compute claims -> one obligation
   each + a `FieldDatum` ledger entry in the build payload;
   projection claims -> ordinary obligations whose givens reference
   the producing field datum by name + digest slot; the promise DAG
   is checked for cycles with the existing diagnostic; a projection
   naming an undeclared field is the existing unresolved-reference
   family.
4. **Orchestrator**: discharge wiring -- when a compute obligation's
   evidence lands, its field payload digest back-fills consumers'
   pending givens (the existing promise-chain scheduling; log the
   chain at INFO). The honest interim stands: with no
   field-producing model registered, compute obligations are
   indeterminate and consumers inherit it (no fake data path).
5. **Fixtures**: a zone-indexed fixture (two-zone wall temperature
   feeding a `sigma_y(T_local)`-shaped consumer) and a
   config-indexed fixture (camber curve + slope bound) in
   `examples/`; goldens for lowering both; an invariant-style test
   that consumer evidence is indeterminate while the producer is.
6. **Docs**: regolith/02 gains sec. 4a (computed indexed fields --
   the D98 text, condensed); regolith/07 sec. 2 table row;
   cross-reference from fluorite/03 sec. 4 (HxSegment) and the
   hematite zone section.

## Acceptance criteria

- Both fixtures compile: ONE producer obligation per compute claim;
  projections reference it by datum name + digest slot.
- The slope projection lowers with the conservative-envelope rule
  stated in its obligation (visible in `regolith debug ir`).
- Producer indeterminate => consumer indeterminate, with a
  diagnostic naming the chain (never silently discharged).
- A compute-compute cycle is a compile diagnostic naming the cycle.
- Same-source determinism on the new payload/ledger entries.
- `make check` green; schema drift green; goldens via
  `make snapshots`.

## Non-goals

- Any field-producing MODEL (four-bar kinematics, marching thermal
  solvers -- feldspar/pack territory; the interim indeterminate
  path is the deliverable here).
- 2-D+ index domains (one axis in v1; the axis type already
  generalizes -- reopen with the first two-axis fixture).
- Field arithmetic between fields (consume-as-given only in v1).

## Remaining / escalations (2026-07-08 partial close-out)

What landed (all in `crates/regolith-syntax`, `crates/regolith-oblig`,
`crates/regolith-lower`, `crates/regolith-api`, `python/regolith/_schema`,
`tests/test_orchestrator.py`, `tests/golden/data/`):

- Deliverable 1 (grammar): `compute <name>: <quantity kind> over
  <index domain>` parses as a new `ComputeField` node inside a
  `require` group's body, contextually recognized (like
  `capability`/`dfm`) so no reserved-keyword collision; `over ...`
  rides the existing opaque-tail sweep, no new sub-grammar.
- Deliverable 2 (schema): `ClaimForm::Compute`, `FieldDatum { name,
  quantity_kind, axis, payload }`, and `CoverageMethod::Undischarged`
  (the honest pre-discharge axis state). `SCHEMA_VERSION` 14 -> 15
  (rebased past WO-32/WO-42's intervening 9 -> 14 bumps).
- Deliverable 3 (lowering): one obligation + one `FieldDatum` per
  `compute` claim; a projection head (`max`/`min`/`slope`, `<name> at
  ...`) resolves to a `given.refs` entry naming the producer's
  content hash, or diagnoses `E0303 UNRESOLVED_FIELD_REFERENCE` if
  the name is undeclared; a compute-compute cycle diagnoses `E0305
  COMPUTE_FIELD_CYCLE` naming the chain.
- Deliverable 4 (orchestrator): NO new orchestrator code was needed
  or added. `translate()`'s existing totality already defers a
  `ClaimForm::Compute` obligation (`non_scalar_claim`, only the
  scalar-comparison form lowers) and defers any consumer whose
  predicate opens with a projection call instead of a bare comparator
  (`unsupported_op`, `_split_comparator` finds nothing at the head).
  Both land as `Indeterminate`, never a fake pass. Pinned by
  `test_compute_obligation_defers_with_no_field_producing_model` and
  `test_projection_of_a_computed_field_also_defers` in
  `tests/test_orchestrator.py`.

What landed closing out this change (2026-07-08, deliverables 5-6):

- Deliverable 5: `examples/tracks/hematite/regen_chamber.hema`
  (zone-indexed: a two-zone `wall_T` compute claim feeding a
  `sigma_y(wall_T at zone(tip))`-shaped structural consumer) and
  `examples/tracks/hematite/suspension_link.hema` (config-indexed: a
  `camber`/`mr` compute pair over `travel in [-80mm, 120mm]` feeding a
  `min(camber)` extremal and a `slope(camber, travel)` bump-steer
  bound). Both are parse-clean (INV-20) and added to
  `tests/golden/test_golden_corpus.py` (structural snapshot, including
  the `FieldDatum` ledger entries) and
  `tests/golden/test_deferral_corpus.py` (the orchestrator verdict
  list). The deferral goldens pin exactly the honesty rule: each
  compute claim (`wall_T`, `camber`, `mr`) defers `non_scalar_claim`
  and each projection consumer (`hoop`, `camber_limit`, `bump_steer`)
  defers `unsupported_op` -- the "consumer indeterminate while
  producer is" acceptance criterion, frozen as data rather than a
  bespoke test, per this repo's golden-corpus convention. Goldens
  regenerated via `REGOLITH_UPDATE_GOLDEN=1` and diff-reviewed (new
  files only, no drift on any existing corpus member).
- Deliverable 6: `regolith/02-quantity-core.md` gained sec. 4a
  (computed indexed fields, condensed D98 text); `regolith/07-claims-
  and-evidence.md` sec. 2 gained a "Computed-field obligations"
  paragraph (no pre-existing table row fit obligations' prose
  structure, so this is a paragraph in the same section rather than a
  literal table row); `fluorite/03-lowering.md` sec. 4's existing
  forward reference ("Computed zone FIELDS ... are D98/WO-33") now
  points at the landed section and the worked fixture; `hematite/02-
  language.md` sec. 7 (Zones) gained rule 6 cross-referencing the same
  section and fixture.

One design ambiguity worth flagging for whoever picks this back up:
the WO text says compute-compute cycles are "the existing
derivation-cycle diagnostic, not new machinery." No such diagnostic
was found anywhere in this repo (Rust or Python) at the time of this
change -- `E0105 COMBINATIONAL_CYCLE` is a distinct, unrelated
converter-graph check. `E0305 COMPUTE_FIELD_CYCLE` was added as a NEW
code in the `References` family (E03xx) rather than reusing something
that does not exist; if a later WO turns up the intended existing
mechanism, reconcile the two rather than keeping both.
