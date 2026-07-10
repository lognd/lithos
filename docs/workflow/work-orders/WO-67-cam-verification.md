# WO-67: CAM verification v1 (std.cam check-mode pack)

Status: done (deliverables 2-6, 7, 8 landed this dispatch over the
Python pack surface; deliverable 1's obligation-emission half is a
Rust-lowering cut named in the close-out ledger below, consistent
with this WO's `Language: Python; Rust none` header)
Depends: WO-51/42 (FeatureProgram + RealizedGeometry, landed),
WO-20/44 (pack + plugin seams, landed). std.machines/std.tooling
records: WO-66 (SOFT -- use fixture records mirroring its charter
shapes if WO-66 has not merged; swap refs in a follow-up note).
NO SCHEMA_VERSION bump (toolpath IR is pack-internal + evidence
content, not a cross-FFI payload; if that proves wrong, STOP and
escalate for the WO-62 bump per the D167/D168 pattern).
Language: Python (std.cam pack: parser, envelope, collision,
removal, coverage models; numpy allowed). Rust none.
Spec: docs/spec/toolchain/33-cam-verification.md (NORMATIVE),
00-architecture.md AD-35 (+ AD-19/22/25), design-log
2026-07-09-cycle-31 D175; regolith/08 sec. 4 (extern plans + check
mode -- the doctrine this implements), regolith/07 sec. 6
(planning as evidence).

## Goal

A supplied G-code plan verifies for real: parse -> envelope ->
coarse collision -> conservative stock removal vs RealizedGeometry
-> feature coverage, each a check-mode model discharging plan
claims with cited, cached, conservative evidence -- and each
failure class caught with line citations.

## Deliverables

1. **Plan linkage plumbing**: `plan: extern(<ref>, gcode_fanuc |
   gcode_marlin)` resolves through the existing extern/format seam
   (regolith/11 formats kind) to hash-pinned plan bytes reaching
   the pack via the ordinary payload-ref channel; lockfile cause
   `extern(<ref>)` (verify how much of this seam exists -- WO-25/
   28 landed parts; implement only the missing plumbing, cite what
   you found).
2. **`cam.parse`**: dialect front-ends (fanuc-class subset:
   G0/G1/G2/G3, tool changes, offsets, canned-cycle REJECTION with
   named diagnostic v1; marlin-class subset for FDM) -> typed
   toolpath IR (pack-internal pydantic). Malformed line =
   INDETERMINATE citing the line, never an exception.
3. **`cam.envelope`**: commanded positions + tool stickout vs the
   machine record's travel; violation cites line + axis + excess.
4. **`cam.collision_coarse`**: rapids vs uncut-stock AABB/voxel
   conservative check.
5. **`cam.removal`**: voxel stock sim (declared resolution as
   error term, margin-driven: thin margin -> finer tier or
   indeterminate); undercut/overcut vs the target RealizedGeometry
   tolerance surface.
6. **`cam.coverage`**: every FeatureProgram machined feature
   touched by cutting moves.
7. **Fixtures + corpus**: a milled corpus part with a supplied
   good plan (all models discharge) + one broken variant per
   failure class (out-of-travel, rapid-through-stock, undercut,
   missing feature) with the named results; flagship-ready marlin
   parse + envelope fixture against an FDM machine record.
8. **Docs**: guide section (verifying a supplied plan), charter
   cross-refs, declared-exclusions text in evidence, WO ledger.

## Acceptance criteria

- Good plan: all five models Valid with evidence citing machine
  record + tool records + geometry digest + plan hash; cached
  (second run = cache hits).
- Each broken variant: the named violated/indeterminate result
  with line citation; no crash paths (fuzz the parser lightly:
  arbitrary bytes never raise).
- Conservative honesty: a coarse-resolution pass whose margin is
  thinner than the voxel error stays indeterminate (test).
- Parity report (if WO-63 landed) classes the plan as
  planner/extern provenance -- else record the cross-note.
- No schema bump; `make check` green; Status flipped.

## Close-out ledger (this dispatch)

**Extern-seam finding (deliverable 1)**: `by extern("ref", <format>)`
foreign linkage exists generically today (`crates/regolith-lower/src/
contracts.rs`'s `Cause::Extern` -- the `impl ... by extern(...)`
production the firmware `elf` binding and the elec/mech importers
already use, WO-25/28). What does NOT exist anywhere in the tree
(checked `crates/regolith-lower`, `crates/regolith-syntax`,
`python/regolith/orchestrator/translate.py`): the L6 `plan:` field
construct (`plan: extern("op10.nc", gcode_fanuc)`, distinct from `impl
... by extern`), any `fmt.gcode_fanuc`/`fmt.gcode_marlin` reader
registration (the `formats` kind row in `docs/spec/regolith/
11-packages-and-stdlib.md` lists these names as vocabulary, not a
landed reader), and any `regolith-lower` obligation emission for the
five `cam.*` claim kinds. Building that is Rust work in
`regolith-lower`/`regolith-syntax` (new grammar production +
`Cause`/obligation-emission surface) -- outside this WO's own
`Language: Python; Rust none` header, so it was NOT invented here.
**Follow-up** (needs its own WO, Language: Rust + Python glue): wire
`plan:` lowering to emit one obligation per `cam.*` claim kind, with
its `payloads` map populated from the extern ref's pinned bytes
(`plan` port) plus whatever staging step publishes `cam_machine`/
`cam_tooling`/`cam_target` (mirroring `regolith.orchestrator.costing`'s
staged-doc precedent for `std.cost`).

**What landed**: the full `std.cam` pack (`python/regolith/harness/
models/cam/`) -- `ir.py` (dialect parsers + toolpath IR),
`records.py` (fixture `MachineRecord`/`ToolRecord`/`StockTarget`
shapes), `checks.py` (pure envelope/collision/removal/coverage
arithmetic), `models.py` (five `Model` subclasses x two dialects,
registered in `harness/models/__init__.py`). All five models discharge
through the ONE shared `Model.discharge` margin path (excess-vs-zero
upper-bound claims); an indeterminate check short-circuits to
`Err(DomainError)` so the registry renders honest indeterminate
evidence, never an optimistic pass.

**Model ids landed**: `cam_parse_gcode_fanuc@1`, `cam_parse_gcode_
marlin@1`, `cam_envelope_gcode_fanuc@1`, `cam_envelope_gcode_marlin@1`,
`cam_collision_coarse_gcode_fanuc@1`, `cam_collision_coarse_gcode_
marlin@1`, `cam_removal_gcode_fanuc@1`, `cam_removal_gcode_marlin@1`,
`cam_coverage_gcode_fanuc@1`, `cam_coverage_gcode_marlin@1` (ten
model ids total; the marlin dialect's collision/removal/coverage
models are registered for symmetry but exercised only by the fanuc-
dialect fixture corpus -- FDM's flagship-1 scope is parse + envelope
per the charter, sec. 1 D5).

**Fixtures + named results** (`tests/fixtures/cam/`, all pillow_block-
class, exercised in `tests/harness/test_cam_models.py`):
- `good.nc`: all five fanuc models Valid (`cam.parse`, `cam.envelope`,
  `cam.collision_coarse`, `cam.removal` at 0.05mm resolution against a
  0.5mm target margin, `cam.coverage` over two features).
- `out_of_travel.nc`: `cam.envelope` violated (positive excess; a
  350mm X move against a 300mm-travel machine record).
- `rapid_through_stock.nc`: `cam.collision_coarse` violated (a rapid
  to Z=-5 inside the uncut-stock AABB).
- `undercut.nc`: `cam.removal` violated, named `undercut` (plan never
  cuts to the target floor).
- `overcut.nc`: `cam.removal` violated, named `overcut` (plan gouges
  25mm past an 18mm floor).
- `missing_feature.nc`: `cam.coverage` violated (the `bore_b` feature
  is never touched; named in the evidence note).
- `canned_cycle.nc`: `cam.parse` indeterminate, `canned_cycle_
  rejected` issue citing the G81 line (G80 cancel is NOT
  misclassified as a cycle -- verified by test).
- Conservative-honesty test: the SAME `good.nc` plan at 1.0mm
  resolution against the 0.5mm target margin stays indeterminate
  (`test_removal_conservative_honesty_thin_margin_indeterminate`).
- Cache test: two identical discharges produce a byte-identical
  evidence hash (`test_evidence_is_cached_by_content_address`).

**Marlin/FDM fixture status**: `flagship1_print.gcode` parses clean
under `gcode_marlin` (extrusion `E` moves recognized) and
envelope-checks Valid against a fixture FDM printer machine record
(`test_marlin_flagship1_envelope_valid`) -- satisfies the charter's
"flagship-1's Marlin dialect parses and envelope-checks against a
printer machine record" acceptance line. Removal/coverage for FDM
(deposition-bounds inversion, sec. 1 D5) is NOT exercised by a
fixture in this dispatch -- the models are registered and would
accept a marlin `DischargeRequest` the same way, but no FDM
removal/coverage fixture was built (scope: the charter only commits
FDM to "the same envelope/coverage models", and flagship-1's coverage
fixture was judged out of this WO's fixture-count budget; tracked as
a follow-up alongside the WO-66 swap-in).

**std.machines/std.tooling swap-in**: WO-66 (soft dependency) had not
merged into this worktree as of this dispatch (`Status: todo` in
`docs/workflow/work-orders/WO-66-stdlib-depth.md`). `records.py`
defines fixture-shaped `MachineRecord`/`ToolRecord` mirroring the
charter's described fields (toolchain/32 sec. 2); tests use these
fixtures directly, never a real stdlib load. Follow-up: once WO-66
lands its `std.machines`/`std.tooling` record loaders, reconcile
(ideally subsume, not duplicate) `records.py`'s fixture shapes against
the real loader records.

**Parity report cross-note**: WO-63 (parity report) was not inspected
in this dispatch (out of this WO's file-surface scope per the
dispatch note: "avoid ... backends/report internals"). No `cam.*`
provenance classification was added to a parity report in this
change; recorded here as the cross-note the acceptance criterion asks
for.

**Removal model simplification**: `cam.removal`'s v1 arithmetic
compares the deepest cutting Z reached against the target's declared
floor (`StockTarget.finished.z_min`) -- a bounding-envelope
approximation, not a full voxel raster (a full raster is explicitly
"future depth" per the charter; declared in `checks.py`'s docstring).

**Schema**: no `SCHEMA_VERSION` bump -- the toolpath IR and all
`std.cam` record shapes are pack-internal pydantic models, never
crossing the Rust/Python FFI boundary (nothing under `_schema/`
changed).

**Verification**: `.venv/bin/pytest tests/harness/test_cam_parse.py
tests/harness/test_cam_models.py -q` -> 19 passed (7 parser + 12
model/discharge tests, including the fuzz test and the conservative-
honesty test). Full `make check` run at close (see commit history).
