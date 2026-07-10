# WO-93 -- Flagship wave 2: cubesat promotion

Status: partial (dispatch 2026-07-10; see Dispatch note below)
Language: corpus authoring + Python (gap-driven)
Spec: D196.1 (the promotion ruling); toolchain/31-flagships.md
  (the flagship bar + parity posture); WO-70..75 close-outs (the
  fleet pattern: phases, honest walls, optimizer pins); F115
  addendum census (cubesat 91 obligations / 7 discharged -- the
  strongest system).

## Goal

examples/systems/cubesat graduates to examples/flagships/cubesat
at the flagship bar: every honest gap either closed or ledgered as
a named wall, at least one optimizer pin proven from the compiled
design, its feldspar-reachable claims discharging, and the D196.2
artifact bar met (`preview` produces its sheet/graph set stamped;
`ship` refuses only on the honestly-unresolved remainder).

## Deliverables

1. The move (directory + goldens/deferral dicts + path references
   -- grep for BOTH string-joined and Path-joined spellings; the
   small_office graduation missed two Path-joined test refs).
2. Deferral-census-driven gap pass: classify all ~84 unresolved
   obligations by reason; close what landed machinery already
   supports (record refs, load paths, conformance impl bounds --
   D195's teaching deferrals name exactly what each impl owes);
   ledger the rest as named walls in the WO file, fleet-style.
3. At least one `by select`/dimension optimizer pin from the
   compiled design (`cause: optimize(...)` in the lockfile), the
   WO-70..75 posture.
4. Artifact set: `preview --out` sheets + contract graph committed
   as CI-checked expectations (the test asserts artifact
   presence + stamp, not pixel equality); `regolith test` corpus
   net extended (a .test.<ext> scenario per track the design
   spans).
5. Docs: flagship README updated to the fleet table shape.

## Acceptance criteria

- Release build discharge count strictly above the census baseline
  (7), with every remaining deferral carrying a specific reason.
- One real optimizer pin with trace. Artifact bar met via preview.
- No spec/grammar changes in this WO (escalate instead).
- `make check` green.

## Dependencies

WO-85/92 + preview landed (all merged). Serializes with WO-87 at
integration if its board entities change cubesat's elec counts
(re-census after merging, do not fight it).

## Dispatch note (2026-07-10) -- what landed, what didn't

Delivered: the move (both string- and Path-joined spellings across
Rust and Python, goldens regenerated via make targets/cargo insta,
never hand-edited); one real continuous optimizer pin with trace
(`PanelOutline.a`, `tests/orchestrator/test_wo93_cubesat_optimize.py`,
`cause: optimize(...)`); the D196.2 artifact bar
(`tests/test_cli_preview_cubesat.py`,
`tests/test_flagship_cubesat_contract_graph.py`); the `regolith
test` net (`structure.test.hema` + `kestrel.test.cupr`, one verdict
per spanned track); the flagship README in fleet-table shape
(`examples/flagships/cubesat/README.md`, full gap-pass ledger
W1-W5); `make check` green.

NOT delivered, honestly: the "discharge count strictly above 7"
acceptance line. The gap pass found exactly two obligations where
an entity-derived bound could be replaced by a literal cited from
design data (rail_stress, appA.size -- both now closed as literals
in the README's ledger), but BOTH land on claim kinds
(`mech.stress.von_mises`, firmware `fit`/size) with no registered
harness model, so they reclassify `unresolved_limit` /
`temporal_reduction_unresolved_limit` -> `no_model` rather than
discharging. Checked every one of the 38 registered model claim
kinds (`uv run python -c "... default_registry().model_ids()"`)
against cubesat's 91 obligations by hand: `link_budget_margin_db@1`
is a near-miss (built explicitly for this file's `Link.margin`
claim per its own docstring) but the corpus's own comment records
its `antenna.gain` term as a DELIBERATE author choice ("rf chain
models are future work ... honestly indeterminate until flatsat
range test evidence") -- confirmed the identical shape recurs
verbatim in `examples/systems/sdr_transceiver/sdr.cupr`, so
"wire it up" would mean inventing an RF gain value the corpus
author explicitly declined to assert, not closing an honest gap.
`thermo_lumped_steady@1` (claim kind `thermo.junction_temperature`)
is the other near-miss for `fpga_ceiling`/`batt_window`, but those
claims translate-lower under the claim's own label name rather than
a `thermo.junction_temperature`-shaped form, so wiring it needs a
translate-side change (out of this WO's authoring-only scope; the
`unsupported_op`/`conformance_windows_unresolved` walls W1/W3 are
the same class of translate-level gap). Escalating rather than
inventing: recommend a follow-up WO scoped to either (a) the
translate-side claim-form recognition for
`thermo.temperature(...)`-shaped claims, or (b) a corpus-authored
`by select` choice point (cubesat currently has none; every
existing candidate claim is either a continuous optimize dim
already spent on `PanelOutline.a`, or requires a new interface this
WO should not invent). `Status: partial` reflects this -- the WO
should NOT be flipped to `done` until either the acceptance line is
relaxed by the owner (the walls above are genuinely outside this
WO's authoring-only scope) or a follow-up dispatch lands one of the
two translate-side fixes above.
