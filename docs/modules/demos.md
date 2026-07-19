# demos/ -- WO-108 physical proof-pack demo scripts

Each `demos/demoN_*.py` script drives the REAL regolith pipeline (no
mocks) over a real `.hema`/`.cupr`/`.fluo`/`.calx` corpus fixture and
records every physical artifact it emits into a per-demo output tree
(`demos/out/<demo>/`): a gitignored artifact bytes directory, a
committed `manifest.json` content-hash ledger, and a committed
`PROOF.md` human-readable proof. `make demos` runs the live set;
`make demos-strict` fails on any not-live demo.

Every demo script follows the SAME shape (module-level path/config
constants naming its fixture and output slot, then a `main()` entry
point that drives the pipeline and writes the proof pack), so they
share one contract anchor below rather than one each.

<a id="demo-proof-pack-shape"></a>
## The proof-pack demo shape (every `demoN_*.py`)

Module-level constants name the demo's fixture source path(s) and
`demos/out/<name>` slot; `main(argv)` drives the real pipeline end to
end and calls into `demos.harness.DemoWriter` to emit
`manifest.json`/`PROOF.md`. Exit code is nonzero iff the demo's pipeline
step failed or (under `--strict`) the surface it demos is not yet live.
Proof-pack correctness (determinism, hash-matches-content, PROOF.md
mentions every manifest row) is verified by `tests/test_wo108_demos.py`
and the `tools/health` `demos` leg, not per-demo unit tests -- a demo
script IS an integration test of the real pipeline by construction.

Per-demo focus (each demo names the surface it proves):

* `demo1_select_ebi_decode.py` -- discrete `select` (WO-56).
* `demo2_continuous_printer.py` -- continuous staged evaluator (WO-57/64).
* `demo3_removal_ribbed_panel.py` -- removal-vocabulary pins (WO-77).
* `demo4_section_search.py` -- civil section search (WO-65).
* `demo5_bounded_slot.py` -- bounded sketch-segment slot margin search.
* `demo6_fleet_showcase.py` -- a full `regolith ship` package.
* `demo7_drawings_multiview.py` -- real HLR multi-view drawing sheets.
* `demo8_bom_cost_schedule.py` -- BOM v2 + cost + member schedule.
* `demo9_assembly_instructions.py` -- mate-ordered assembly steps.
* `demo10_three_d_glb_viewer.py` -- deterministic GLB + offline viewer.
* `demo11_board_gerbers.py` -- real KiCad gerber set from a BoardOutline.
* `demo12_firmware_hdl.py` -- firmware tree + HDL evidence.
* `demo13_test_runner_cache.py` -- `regolith test` cache-proven replay.
* `demo14_preview_parity.py` -- `regolith preview` vs `ship` byte-parity.
* `demo15_calc_audit.py` -- the calc book + audit trail (D221).
* `demo16_doctor_config.py` -- doctor/config/toolenv environment surface.
* `demo17_physical_bringup_pack.py` -- physical bring-up pack (WO-127 D4).

<a id="harness"></a>
## demos/harness.py -- shared proof-pack machinery

Shared machinery every demo script drives: `DemoWriter` composes the
manifest + PROOF.md for a demo's output tree; `ArtifactRow`/`Manifest`
are the committed content-hash ledger's shape; `sha256_hex` is the ONE
digest function every row/proof cites; `gap_proof` records an HONEST
not-yet-live surface instead of faking a pass.

### `DEMOS_ROOT` / `OUT_ROOT` / `REPO_ROOT` / `MANIFEST_NAME` / `PROOF_NAME`
The fixed paths and filenames every demo's output tree uses -- one
home so no demo hardcodes its own layout.

### `sha256_hex`
The content hash every manifest row and PROOF.md cites (sha256 --
the same digest family `dist/index.md` uses repo-wide).

### `ArtifactRow`
One committed artifact's manifest row shape (path, hash, size).

### `Manifest`
The whole per-demo `manifest.json` shape: every `ArtifactRow` plus
the demo's liveness verdict.

### `DemoWriter`
Composes a demo's `manifest.json` + `PROOF.md` from the artifacts it
recorded during a run; the ONE place every demo script writes its
proof pack through.

### `artifact_table`
Renders a `PROOF.md` artifact table from a tuple of `ArtifactRow`s --
one rendering home so every demo's table has the same shape.

### `gap_proof`
Records an HONEST not-yet-live surface (a demo whose backing pipeline
step is not yet merged) as a structured gap rather than a faked pass;
`make demos-strict` turns any live `gap_proof` into a nonzero exit.

<a id="run-all"></a>
## demos/run_all.py -- the demo runner

### `DEMOS`
The registry of every demo module in run order (the WO-108 live set);
the ONE list `make demos`/`make demos-strict` and the `tools.health`
`demos` leg all iterate.

### `main`
Runs every demo in `DEMOS`, aggregates pass/fail/not-live, and returns
the composed exit code (`--strict` promotes not-live to failing).
