# cubesat -- Kestrel, 1U Earth-observation CubeSat (WO-93, flagship wave 2)

D196.1's flagship wave 2 promotion (design-log 2026-07-10-cycle-33):
the strongest `systems/` corpus member (F115's census: 91
obligations, 7 discharged going in) graduates to the flagship bar --
mech (machined rail frame + laser-cut side panels + a deployable
antenna mechanism), elec (five boards: EPS/OBC/ADCS/comms/payload),
firmware (the Kestrel flight-core partition/schedule surface), a
cross-track dB link budget, and mass/energy/pointing-error budgets
spanning every part, in one integration file (`kestrel.cupr`).

## File map

| file | track | contract |
|---|---|---|
| `structure.hema` | hematite | four-rail machined frame + laser-cut side panels; the DFM waiver (qual-proven relief wall) and the `PanelOutline.a` continuous optimizer pin |
| `antenna.hema` | hematite | deployable tape-spring monopole: a hold-down mechanism with modal (stowed/deployed) claims and an event-coupled release |
| `contracts.cupr` | cuprite | shared interfaces (CardBay, CardMount, StackMate, AntennaMate, Umbilical) every board/structure file implements |
| `eps.cupr` | cuprite | electrical power system board |
| `obc.cupr` | cuprite | on-board computer board (hosts the flight-core `cpu0`) |
| `adcs.cupr` | cuprite | attitude determination and control board |
| `comms.cupr` | cuprite | UHF comms board (the `AntennaPort` far end, PA/burn channel) |
| `payload.cupr` | cuprite | imaging payload board (hosts the `TileCompressor` FPGA workload) |
| `kestrel.cupr` | cuprite (top) | mission intents, the flight-core computer + firmware image, mass/energy/pointing budgets, the dB link budget, the flatsat ground-support overlay |
| `structure.test.hema` / `kestrel.test.cupr` | design tests | one verdict scenario per spanned track (charter toolchain/37), the `regolith test` corpus net extension |
| `magnetite.toml` | -- | the project manifest: dependency set + evidence-document hashes |

## WO-93 gap-pass ledger

Fresh baseline (`regolith build --release`, post WO-87/90/92 merge):
**91 obligations, 7 discharged, 84 unresolved** -- unchanged in
count from F115's own census (structurally safe edits below reclassify
several reasons but do not themselves discharge; the wall analysis
records exactly why).

Closed this dispatch (literal bounds cited from design data, in
place of entity-derived refs the reduction path can't yet resolve --
D195's "declare an honest impl-body bound" path):

- `structure.hema` `Rail.Structural.rail_stress`: `material.sigma_y /
  1.6` -> `314.375MPa` (AL7075_T6 `yield_MPa=503` /
  `stdlib/std.materials/records/aluminum.toml` / 1.6 safety factor).
- `kestrel.cupr` `flight_fw.Resources.fit`: `partitions.appA.size` ->
  `480kB` (the declared `appA: flash[32kB .. 512kB]` partition
  range).

Both reclassify from an unresolved-bound reason to `no_model`
(no `mech.stress.von_mises` / firmware-size harness model registers
yet) -- a real, separately-named wall, not a discharge; recorded
below rather than claimed as closed.

Named walls (ledgered, not attempted -- toolchain/spec gaps outside
this WO's scope, matching AD-22's stop-and-record discipline):

- **42 `conformance_windows_unresolved`**: confirmed, obligation by
  obligation, to be the D195 "nothing scalar to compare" bucket
  (module imports, geometric/role promises) on every one of
  cubesat's `conforms` obligations -- not the "impl owes a bound"
  bucket WO-92 split out. No impl-body literal closes these; they
  need the realized-fact channel (WO-22/24-family growth) or a new
  scalar promise vocabulary word. **W1**.
- **~26 `no_model`**: no harness model registers for `dipole`,
  `mag_floor`, `wcet`, `stack`, `fit`, `torque`, `settle`,
  `first_mode`, `frame_total`, `rail_stress`, and a dozen more claim
  kinds (thermal/link/firmware/mechanism domains) -- genuine solver
  depth, the D173 feldspar-or-a-new-model precedent, out of this
  WO's authoring-only scope. **W2**.
- **9 `unsupported_op`**: `comparator 'require' defers` -- the
  `_split_comparator` translate-level gap WO-48's close-out named,
  unresolved for a `require` clause shape cubesat exercises; a
  language gap routing to a design-log entry + WO, not a corpus fix.
  **W3**.
- **`antenna.gain`** (`kestrel.cupr` `Link.margin`, `given_unresolved`):
  deliberately left unmodeled by the ORIGINAL author (the source's
  own comment: "rf chain models are future work ... honestly
  indeterminate until flatsat range test evidence") -- an
  intentional epistemic-honesty deferral, not a gap to close.
  Confirmed the same shape recurs in `examples/systems/
  sdr_transceiver/sdr.cupr`'s own `antenna.gain` reference: a
  cross-domain RF-gain-on-a-mech-assembly vocabulary word genuinely
  does not exist yet. **W4**.
- **`trust: >= certified`** (`structure.hema`, `unresolved_limit`):
  an enum/trust-tier comparator, not a scalar quantity -- outside
  the literal-bound-citation path entirely. **W5**.

## Optimizer pin

`structure.hema`'s `PanelOutline.a = in [94mm, 96mm] minimize` (the
90mm `CardBay` bolt patterns need >= 94mm of panel width for edge
margin; the CubeSat Design Specification's panel-width tolerance
allows shrinking the fixed 96mm envelope down to that floor).
Proven via the landed continuous golden-section evaluator over the
realized `FeatureProgram`
(`tests/orchestrator/test_wo93_cubesat_optimize.py`, the WO-64
pattern -- `regolith check`'s v1 sketch-promotion surface does not
yet thread `in [lo, hi] minimize` through the walk promoter, W2's
same class of gap, so every flagship in the fleet proves its
continuous pins this way): the search converges near the 94mm lower
bound and produces a `cause: optimize(...)` lock row.

## Artifact bar (D197/D196.2)

`regolith preview examples/flagships/cubesat --out DIR` writes the
contract-graph sheet (24 nodes, 12 edges) stamped `PREVIEW -- NOT
RELEASED: 84 unresolved`, plus `gate_summary.json`
(`tests/test_cli_preview_cubesat.py`, `tests/
test_flagship_cubesat_contract_graph.py`). `regolith ship` correctly
refuses (INV-24; the gate is not clean) -- no manifest/BOM ever
written by `preview`.

## `regolith test` corpus net

`structure.test.hema` (hematite) and `kestrel.test.cupr` (cuprite),
one verdict scenario per spanned track, both green:

```
test examples/flagships/cubesat/kestrel.test.cupr::kestrel_link_verdict ... ok
test examples/flagships/cubesat/structure.test.hema::rail_structural_verdict ... ok
```
