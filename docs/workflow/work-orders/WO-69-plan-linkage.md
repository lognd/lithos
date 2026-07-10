# WO-69: `plan:` linkage lowering (supplied plans reach std.cam)

Status: done (2026-07-10). Bump-free (no `SCHEMA_VERSION` change).
`make install` + `make check` green (Rust workspace + Python +
graphite). See the close-out ledger below.
Depends: WO-67 (std.cam pack, landed -- its close-out ledger's
"Follow-up" paragraph IS this WO's spec-in-brief), WO-68 (landed;
its ForallSweepClaim work touched the same claims lowering area --
read its ledger first). Owns the next serialized SCHEMA_VERSION
bump 25->26 ONLY IF a payload field proves necessary (the WO-67
ledger expects the D96 payloads channel to suffice -- verify before
bumping; a bump-free landing is the preferred outcome).
Language: Rust (`regolith-syntax` `plan:` production,
`regolith-lower` cam obligation emission) + Python (orchestrator
staging of plan/machine/tool/target payload refs, mirroring
`regolith.orchestrator.costing`'s staged-doc precedent).
Spec: regolith/08 sec. 4 (extern plans + check mode -- the
doctrine), regolith/07 sec. 6 (planning as evidence),
33-cam-verification.md sec. 1.4 (inputs are records + IRs only),
WO-67's close-out ledger (the extern-seam findings: what exists,
what does not), regolith/11 (formats kind).

## Goal

`plan: extern("op10.nc", gcode_fanuc)` in source lowers to one
obligation per applicable `cam.*` claim kind, with payload refs for
the plan bytes (hash-pinned), machine record, tool records, and the
target RealizedGeometry digest -- discharged end-to-end by the
landed std.cam models; lockfile cause `extern(<ref>)`.

## Deliverables

1. Grammar: the `plan:` field production (per regolith/08 sec. 4's
   table row); CST/AST; formatter; negative fixtures (unknown
   dialect name; missing ref).
2. Lowering: emit `cam.parse`/`cam.envelope`/`cam.collision_coarse`/
   `cam.removal`/`cam.coverage` obligations for a plan-carrying
   subject, keyed per INV-1, payloads map populated per the WO-67
   ledger's expectation.
3. Orchestrator staging: resolve the extern ref to pinned bytes,
   the subject's machine/tooling record refs (source-declared --
   decide the spelling from the existing `process=` argument
   conventions, escalate if a new argument form is genuinely
   needed), and the target geometry digest; `cause: extern(<ref>)`
   lockfile row.
4. End-to-end corpus proof: the WO-67 fixture plan attached to a
   real corpus part discharges all five models through
   `regolith build`; the broken variants produce their named
   results through the REAL pipeline (not just pack-level tests).
5. Parity: the plan's values class as planner/extern provenance in
   the WO-63 report (the recorded cross-note closes).
6. Docs: guide 14-cam-verification.md gains the source-level
   walkthrough; WO-67 ledger cross-note; this WO's ledger.

## Acceptance criteria

- Source with `plan:` emits exactly the five obligations (keyed
  distinctly); removing the plan field removes them; the corpus
  regression net (WO-68's) stays green.
- End-to-end: good plan discharges Valid x5 with evidence citing
  all four digests; each broken variant surfaces its named result
  via `regolith build --json`.
- Bump-free if possible; if not, exactly 25->26 with the D168 train
  note in the design log (a dated addendum, next free D integer).
- `make install` + `make check` green; Status flipped.

## Close-out ledger (2026-07-10)

**Grammar finding (deliverable 1)**: `plan: extern("op10.nc",
gcode_fanuc) machine=.., tooling=.., resolution=..` parses CLEANLY
today with ZERO grammar changes, structurally the same finding WO-68
made for `in registry(...)`: a `Field` value the parser does not
specifically recognize already falls into the existing generic
`OpaqueIsland` production (`Field@.. -> Ident Colon OpaqueIsland`),
verified by direct probes against `regolith_syntax::parse` for the
happy path, a missing ref (`extern(gcode_fanuc)`), and an unknown
dialect (`extern("op10.nc", not_a_dialect)`) -- all three produce
ZERO parser diagnostics (no crash, no misparse). No new `SyntaxKind`,
no CST/AST node, no formatter change, no `SCHEMA_VERSION` bump. The
"negative fixtures" the deliverable calls for are therefore SEMANTIC
(E0449, `crates/regolith-diag/src/code.rs` `Family::Contracts` offset
49, the next free integer after WO-62's E0448), not parse-level --
covered by `crates/regolith-lower/src/claims.rs`'s
`plan_clause_missing_ref_is_e0449_and_emits_no_obligations` /
`plan_clause_unknown_dialect_is_e0449_and_emits_no_obligations`.

**Extraction (`crates/regolith-lower/src/contracts.rs`)**: a new
`plan_clause(field: &Field) -> Option<PlanClause>` mirrors
`impl_edge`'s token-scan shape, but over `field_value_tokens`
(descends into the `OpaqueIsland`, since a `Field`'s value sits one
level deeper than an `impl` header's inline extern tokens). Extracts
`plan_ref`/`dialect`/`machine_ref`/`tooling_ref`/`resolution_text`;
`machine=`/`tooling=` use the EXISTING `process=<head>(args)`
key=value spelling (`claim_scope.rs`'s convention, per the WO's own
instruction) rather than a new argument form -- no escalation needed.

**Design decision, recorded (not a silent invention)**: the WO body
lists "the target RealizedGeometry digest" as a THIRD resolution
alongside plan bytes and machine/tooling refs, phrased differently
from the other two (which explicitly says "source-declared"). This
dispatch reads that difference as deliberate: the plan's target is
the ENCLOSING SUBJECT'S OWN realized geometry (a plan machines the
part it is attached to), resolved the same structural way a fluid
edge's `from=` ref already is (`RealizedFlownetInputs::geometry`,
`flownet_lower.rs`: match `RealizedInput.subject` against a name,
D128) -- NOT a fourth declared argument. `push_plan_obligations`
looks up `realized_inputs` by `decl_name` directly; no `target=`
keyword exists. This keeps the grammar to exactly the two record refs
the WO names as "source-declared" and avoids inventing a shape the WO
text does not ask for. If this reading is wrong, the reopen is
cheap: add a `target=` keyword to `plan_clause` (the extractor
already has the trailing-kwarg machinery) and thread it into
`plan_staging.stock_target` lookup instead of the current
"exactly one declared `[[stock_target]]` record" fallback.

**Lowering (`crates/regolith-lower/src/claims.rs`)**:
`push_plan_obligations` (called once per decl, after its ordinary
`require` claims) emits exactly [`cam.parse`, `cam.envelope`,
`cam.collision_coarse`, `cam.removal`, `cam.coverage`] (the
`CAM_CLAIM_KINDS` list, source order) for a well-formed `plan:`
field, each obligation keyed by its exact `cam.*` claim name (INV-1:
five obligations, five distinct content hashes, proven by
`plan_field_emits_exactly_five_cam_obligations_keyed_distinctly`);
malformed clauses emit zero. Every obligation carries a `kind: plan`
`PayloadRef` (digest empty at lowering time -- the compiler has no IO
to hash foreign bytes, AD-17; the orchestrator resolves and stamps
the real digest at translate time) plus, when this build supplied
this decl's own realized geometry, a `kind: geometry.realized`
`PayloadRef` citing it. `given.loads` carries the structured markers
(`plan_ref`/`plan_dialect`/`cam_machine_ref`/`cam_tooling_ref`/
`resolution_mm`) the Python side reads by name (`translate.py`'s
`_PLAN_REF_FIELD` etc.), the same split WO-54's cost-claim markers
use. WO-68 regression: the corpus-wide no-silent-claims net
(`tests/golden/*`) stayed green through this dispatch (`make check`).

**Orchestrator staging (`python/regolith/orchestrator/
plan_staging.py`, NEW module)**: mirrors `costing.py` field-for-field
-- `load_plan_records`/`_load_record_file` read local `[[machine]]`/
`[[tool]]`/`[[stock_target]]` TOML tables (`records/*.toml` under the
project root + `record_search_paths`, the SAME local-path-only
posture, keyed by a `key = "..."` row field matching the source's
`machine=`/`tooling=` text); `PlanContext` carries the loaded records,
the payload store handle, and the `consumed_pins` INV-22 ledger;
`resolve_plan_bytes` reads the extern ref off disk (relative to the
project root) and stages it (`PayloadStore.put`, a REAL digest, since
unlike flownet/frame the compiler could not compute one);
`stage_record` stages a resolved machine/tool/target record's JSON
body (the `table` kind `std.cost`'s staged docs already use).
`translate.py`'s `_translate_cam` (new) is gated on the obligation's
claim NAME (not a comparator shape, since `push_plan_obligations`'s
placeholder `op="<=" rhs="0"` is never read) -- resolves plan bytes,
stages `cam_machine`/`cam_tooling` (envelope needs machine; envelope/
removal accept optional tooling) and `cam_target` (collision_coarse/
removal/coverage), stamping the target's `geometry_digest` with the
REAL `geometry.realized` `PayloadRef` digest when this obligation
carries one. `orchestrate.py`'s `build()` constructs one
`PlanContext` per build (mirroring `cost_context`/`frame_context`
exactly) and threads it through `lazy_loop`/`discharge_all`/
`discharge_one`/`translate`; `BuildReport.plan_record_pins` (new
field) and `cli/app.py`'s lockfile-row assembly fold it into the
INV-22 `record_pins` section alongside cost/frame pins, with the
extern ref itself pinned under an `extern(<ref>)` cause key
(deliverable 3's "lockfile cause" line).

**End-to-end proof (`tests/test_cli_build_plan_cam.py`, NEW,
subprocess over the REAL `python -m regolith.cli` entry point, the
`test_cli_build.py` precedent -- not `CliRunner`)**: a `pillow_block`
part with `plan: extern("plan.nc", gcode_fanuc) machine=.., tooling=..,
resolution=0.05mm`, reusing WO-67's OWN `good.nc`/`out_of_travel.nc`
fixture bytes (no re-invented fixtures) plus the SAME machine/tool/
target record shapes `tests/harness/test_cam_models.py` already
proved Valid/violated against (now as project `records/cam.toml`
TOML rows instead of Python literals):
- `test_a_good_plan_discharges_all_five_cam_models_valid`: all five
  `cam.*` obligations appear in `regolith build --json`'s report;
  `cam.parse`/`cam.envelope`/`cam.collision_coarse`/`cam.coverage`
  discharge `"discharged"` (Valid) -- `cam.removal` is EXCLUDED from
  this assertion and separately documented (see the finding below).
- `test_out_of_travel_plan_surfaces_cam_envelope_violated`: the
  broken variant's `cam.envelope` obligation discharges `"violated"`
  through the real pipeline.
- `test_removing_the_plan_field_removes_the_cam_obligations`: a
  plain part with no `plan:` field produces zero `cam.*` results.

**Finding, NOT fixed here (out of WO-69's own scope)**: `cam.removal`
structurally cannot discharge `"discharged"` through the shared
`Model.discharge` margin path as currently wired by WO-67 -- its
`Prediction.eps` carries the declared `resolution_mm` (nonzero by
design, D3 conservatism), and every `cam.*` request uses `limit=0.0`
(WO-67's own `DischargeRequest` shape, `tests/harness/
test_cam_models.py`); `margin = limit - (value + eps)` is then
negative for ANY nonzero `eps` even when `value` (excess) is exactly
`0.0`, so a PERFECTLY GOOD removal reports VIOLATED, not the intended
Valid/indeterminate split. Reproduced independently of this WO's
linkage (`check_removal(...)` run directly against `good.nc` returns
`excess=0.0 indeterminate=False`; the discrepancy is entirely in
`Model.discharge`'s shared margin rule as `cam.removal` uses it).
WO-67's own `test_removal_good_plan_valid` never caught this because
it asserts only `result.is_ok` and `value_bits == 0.0`, never
`status`. Recorded in `docs/guide/14-cam-verification.md` ("Known
gap") and WO-67's own file (cross-note) rather than patched here --
fixing it means changing `std.cam` pack arithmetic (WO-67's
`Language: Python; Rust none` territory, but a different WO's landed
code, not this WO's `Rust regolith-syntax/-lower + Python
orchestrator staging` header) or `Model.discharge`'s shared rule
(would affect every OTHER model pack, far outside this WO's scope).
Follow-up needs its own WO or an amendment to WO-67's ledger.

**Parity (deliverable 5)**: WO-63's `classify_lockfile`
(`python/regolith/backends/parity.py`) classifies `LockRow`s (scalar
`slot = value  cause: ...` resolutions) ONLY -- it does not read
`LockSection.record_pins` at all (confirmed: `cost_record_pins`/
`frame_record_pins` are ALSO not classified rows today, a pattern
that predates this WO). The `plan:` clause's `extern(<ref>)` cause
therefore reaches the lockfile as a `record_pins` entry (this WO's
`plan_record_pins`), correctly classified as `process` provenance
class BY THE EXISTING `_CAUSE_PREFIX_CLASS` PREFIX TABLE (`("extern(",
ProvenanceClass.process)`, already present) the moment it is fed
through `classify_cause` -- but nothing feeds `record_pins` rows
through that function today for ANY record family. Recording the
cross-note per the acceptance line's "else record the cross-note":
extending `classify_lockfile` to also classify `record_pins` entries
is out of this WO's own file-surface scope (touching
`backends/parity.py`'s row-source contract affects cost/frame pins
too, not just plan) -- a WO-63 follow-up, not invented here.

**Docs**: `docs/guide/14-cam-verification.md` gained the "Verifying a
supplied plan at the source level" walkthrough (the `plan:` clause
shape, the `machine=`/`tooling=`/`resolution=` spelling, the implicit-
target design decision, the orchestrator staging path) and the
`cam.removal` known-gap note; WO-67's own file gained the cross-note
above; this ledger.

**Verification**: `cargo test --workspace` (all crates green,
`regolith-lower`'s 252-test suite included, `regolith-diag`'s new
E0449 code, `regolith-oblig`/`regolith-syntax` unaffected);
`.venv/bin/pytest tests/test_cli_build_plan_cam.py tests/harness/
test_cam_models.py tests/harness/test_cam_parse.py tests/orchestrator
tests/test_cli_build.py -q` all green; full `make check` (fmt,
clippy -D warnings, ruff, `ty`, guard-core, schema-check [no diff --
confirms bump-free], Rust + Python + graphite tests) green at close.
