# WO-77 -- Declared material-removal vocabulary (charter 34 phase 1)

Status: done (cycle 33, 2026-07-10 -- see the close-out ledger at
  the end of this file; file authored 2026-07-10 after the first
  dispatch's correct escalation -- the queue had carried this WO as
  "file exists" in error; D200 records the vocabulary rulings the
  charter delegated to this WO's spec cycle)
Language: Rust (regolith-syntax claim-scope verbs, regolith-ir/
  -lower projection) + Python (realizer projections, DFM rows,
  coverage ledger) + corpus
Spec: toolchain/34-topology.md sec. 2 (the charter, NORMATIVE for
  intent); D200 (design-log 2026-07-10-cycle-33 -- the concrete
  vocabulary this WO implements); AD-17 (one claim-scope feature
  traversal); WO-51 (FeatureProgram producer), WO-22 (realizer +
  E0443 omission posture), WO-67 (coverage/named-skip posture);
  hematite/07 (feature-op grammar home).

## Goal

The honest erosion, phase 1: an author DECLARES a removal family
over a target region; the optimizer explores its parameters with
machinery that already exists; the feature chain realizes it; DFM
gates every candidate. No density fields, no synthesis -- pattern
vocabulary only.

## The vocabulary (D200 -- implement, escalate only on contradiction)

Four constructor VERBS in the existing `then:`-scope feature-call
form (the Bore/CBore/Pierce/Bend idiom -- NO new statement form;
parameters use the existing literal / `in [lo, hi]` / `in {a, b}`
slot forms the optimizer already consumes):

1. `Ribs(count, pitch, thickness, height?)` -- count int, pitch/
   thickness/height lengths; height optional (defaults to the
   target region's depth).
2. `PocketGrid(nx, ny, wall, floor, depth?)` -- nx/ny ints, wall/
   floor lengths, depth optional (defaults to through-depth minus
   floor).
3. `Shell(t)` -- wall thickness.
4. `Lattice(cell, density)` -- cell in a DISCRETE set (v1 set:
   `{gyroid, honeycomb, cubic}`), density a fraction in [0, 1].

Target region: exactly the existing claim-scope subject mechanism
every current feature verb uses -- no new targeting grammar.

## Deliverables

1. Grammar/claim-scope: the four verbs recognized by the ONE
   feature-call traversal (AD-17); malformed family params (wrong
   arity, wrong dimension, density outside [0,1], unknown cell
   name) = NEW constructive E-code (next free; E0450 is taken)
   naming the family's signature.
2. Lowering: each verb materializes an ordinary `FeatureOp` (the
   EXISTING IR shape -- kind/constructor/params; NO new IR fields,
   NO SCHEMA_VERSION bump; if the existing shape genuinely cannot
   carry a family, STOP and escalate rather than bump).
3. Realizer projections (Python interpreter): Ribs, Shell, and
   PocketGrid project into v1 geometry where build123d supports
   them; Lattice is an HONEST named omission (the E0443/W-warning
   posture + a coverage-ledger named skip: "lattice: no v1
   projection"). Coverage ledger rows for all four.
4. DFM tier rows (the manufacturability law, charter sec. 2): a
   rule-pack batch (the WO-28/std packs idiom) with per-family
   predicates -- min rib thickness vs process, pocket wall vs
   tool access, shell min t, lattice cell x process feasibility
   (subtractive processes cannot make an internal gyroid:
   INFEASIBLE, named). Fixture cases both ways per family.
5. Corpus: a fixture part (or a cnc_router_r1 part if one fits
   naturally) declaring `Ribs` with a bounded `count`/`thickness`
   and a mass-minimize objective -- the optimizer pins a winner
   through EXISTING machinery (`cause: optimize(...)`); a negative
   fixture for the new E-code (numbering checked against master at
   the end).
6. Docs: hematite/07's feature-op section gains the four verbs
   (track-header version bump); guide mention beside the existing
   feature-op examples; charter 34 sec. 2 gets a "landed" cross-
   reference (no rewriting of its text).

## Acceptance criteria

- The Ribs fixture builds: FeatureProgram carries the op, the
  optimizer pins count/thickness with a trace, DFM rows fire on
  an infeasible twin.
- Lattice declares, lowers, and skips HONESTLY (named skip in the
  coverage ledger; no fabricated geometry).
- No SCHEMA_VERSION bump; no corpus regression (zero
  lowered->deferred transitions); goldens regenerated via make
  targets.
- `make check` green.

## Dependencies

WO-51/22/67 (landed), WO-85/90 (landed -- the current parse base).
Phase 2 (density fields) stays gated on this WO + WO-76 + an owner
compute-budget check-in (charter sec. 3) -- NOT this dispatch.

## Close-out ledger (cycle 33)

1. **Deliverable 1 DONE.** The four verbs ride the existing AD-17
   claim-scope traversal untouched (a `FeatureCall` was already the
   right shape); the NEW single home is
   `crates/regolith-lower/src/removal.rs`: family signatures, the
   three slot forms (`k=v` / `k in [lo, hi]` / `k in {a, b}`, plus
   the corpus's `k = in [..]` constraint style), and constructive
   validation. Malformed params (arity, unknown/duplicate slot,
   wrong dimension via `regolith-qty` length-dimension checks,
   density outside [0, 1], unknown cell name, inverted bounds) are
   **E0451** naming the full family signature; the op is omitted.
   `grammar.ebnf` needed NO production change: family arguments ride
   `ctor-stmt`'s existing value surface (verified by parsing the
   spellings through the live front end before any code was written).
2. **Deliverable 2 DONE, bump-free.** Each verb materializes an
   ordinary `FeatureOp` (kinds `ribs`/`pocket_grid`/`shell`/
   `lattice`; bounded/discrete slots carry cause `planner`, the
   existing regolith/03 class). `make schema` produces an EMPTY diff
   -- SCHEMA_VERSION stays 27. `regolith-sem::EntityKind` gained
   Rib/PocketGrid/Shell/Lattice variants (+ kind words + measure
   vocabularies) so rule packs quantify over the families;
   `EntityKind` is not a schemars type, so this is also bump-free.
3. **Deliverable 3 DONE.** `RibsOp`/`PocketGridOp`/`ShellOp` in the
   realizer schema + build123d interpreter arms (slab-minus-ribs,
   bordered pocket grid, subtract-the-deflated-interior shell), each
   with hand-computed-volume tests and Err-valued misuse paths
   (`tests/realizer/mech/test_removal_ops.py`). The promotion seam
   (`regolith.orchestrator.programs`) converts literal family ops;
   an unpinned planner slot or a `lattice` op keeps the WHOLE
   program pending with the reason NAMED. Coverage ledger: three
   `realizes` rows + a THIRD category for Lattice --
   `lowers(skips: no v1 projection)` (never an E0443; the singular
   legacy `Rib` ctor stays an honest E0443 skip). Ledger drift
   tests updated (`tests/realizer/mech/test_coverage.py`).
4. **Deliverable 4 DONE.** `examples/tracks/hematite/std_removal.hema`:
   `std.removal` (subtractive floors: min_rib_thickness,
   rib_slot_tool_access, pocket_grid_wall/floor, shell_min_wall, and
   the lattice INFEASIBILITY row spelled as `lattice_density_min:
   1.0` -- solid or nothing) + `std.removal_am` (printable-density
   floor). Every rule has pass+fail expect fixtures, green through
   the real `rules test` facade (`tests/golden/test_rules_cli.py`).
   RECORDED RESIDUAL: per-CELL feasibility (e.g. an additive pack
   that prints gyroid but not cubic) needs a string-comparison rule
   form the evaluator's numeric subset deliberately excludes
   (INV-17 bans `==`); the density floor captures the subtractive
   case exactly. Reopen on a real additive pack that must
   distinguish cells.
5. **Deliverable 5 DONE.** `examples/tracks/hematite/ribbed_panel.hema`
   (four parts, one per family; golden + deferral corpus groups
   `ribbed_panel`, regenerated with ZERO churn on existing entries);
   negative fixture `examples/negative/70_removal_family_malformed
   .hema` (E0451; numbering checked against master, which ends at
   69). `tests/orchestrator/test_wo77_removal.py` pins count AND
   thickness through EXISTING drivers only (discrete over the
   integer bounds composed with golden-section over the interval;
   every candidate realized through the real OCCT interpreter) and
   asserts the `cause: optimize(mass, trace=<digest>)` lock rows,
   the E0601 infeasible twin, and promotion honesty.
6. **Deliverable 6 DONE.** hematite/07 sec. 2a entry (header 0.13 ->
   0.14), guide sec. 3a (`docs/guide/01-hematite-guide.md`), charter
   34 sec. 2 landed cross-reference (text unchanged), this ledger.

cnc_router_r1 release-build census: byte-identical report before/
after (184 results / 176 unresolved / release_ok=false / E0443 x35 /
L0803 x1) -- the flagship spells none of the new vocabulary, and no
existing obligation moved. Zero lowered->deferred transitions
anywhere in the regenerated corpora.
