# 13 -- Verifying a supplied CAM plan (`std.cam`)

Status: WORKING end to end (WO-69, plan-linkage lowering). A
`plan: extern(<ref>, gcode_<dialect>)` field on a `.hema` part lowers
to the five `cam.*` obligations automatically, and `regolith build`
resolves the extern plan bytes plus the declared `machine=`/
`tooling=` records through the ordinary orchestrator staging path to
discharge them against the landed `std.cam` pack (five models over
two dialects -- see `tests/harness/test_cam_models.py` for the pack
itself, `tests/test_cli_build_plan_cam.py` for the source-level
proof through the real `regolith build --json` pipeline).

Source: `docs/spec/toolchain/33-cam-verification.md` (NORMATIVE
charter), `docs/spec/toolchain/00-architecture.md` AD-35,
`docs/spec/regolith/08-lowering-architecture.md` sec. 4 (L6: "the
planner runs in check mode"), `docs/spec/regolith/07-claims-and-
evidence.md` sec. 6 (planning as evidence).

## The idea

regolith never GENERATES a machining or print plan (that stays the
expensive-tier future). What it does today is CHECK one you already
wrote: a G-code file is hash-pinned as an `extern` artifact, and five
cheap, deterministic, conservative models discharge its claims the
same way any other obligation discharges -- cited, cached, and honest
about what it does not know.

## The five models

All five live in `regolith.harness.models.cam` and share ONE
`Model.discharge` path (`regolith.harness.model`), so a Valid result
always carries evidence citing the plan hash + every record it
consumed, and a second identical discharge is a cache hit (same
evidence hash).

1. **`cam.parse`** -- the dialect front-end. `gcode_fanuc` (3-axis
   mill class: G0/G1/G2/G3, tool changes, work offsets) and
   `gcode_marlin` (FDM: G0/G1 + `E` extrusion) share one typed
   toolpath IR (`regolith.harness.models.cam.ir.Toolpath`). A canned
   drilling/boring cycle (G81/G82/G73/...) is REJECTED with a named
   `canned_cycle_rejected` issue, never silently modeled. Any
   malformed or unrecognized line becomes an issue citing its line;
   the parser is total over arbitrary bytes (fuzzed in
   `tests/harness/test_cam_parse.py`) -- it never raises.
2. **`cam.envelope`** -- every commanded X/Y/Z stays within the
   machine record's travel, with the active tool's stickout
   subtracted from the Z floor (reach arithmetic). A violation names
   the worst line + axis + excess.
3. **`cam.collision_coarse`** -- a coarse AABB/voxel check that no
   rapid (G0) move passes through the uncut-stock envelope below its
   top face (the classic "rapid plunges into stock" bug).
4. **`cam.removal`** -- a conservative voxel-resolution stock-removal
   check against the target's finished envelope: undercut (material
   left) or overcut (part body gouged), both against a declared
   `resolution_mm` error term. **Conservative honesty**: when
   `resolution_mm` is not strictly finer than the target's declared
   `margin_mm`, the result stays INDETERMINATE rather than claiming a
   pass the resolution cannot support (see
   `test_removal_conservative_honesty_thin_margin_indeterminate`).
5. **`cam.coverage`** -- every FeatureProgram-declared machined
   feature is touched by some cutting move; a missing feature names
   itself in the evidence note.

## Records the pack consumes

Every model resolves its inputs through the ordinary D96 payload
channel (`DischargeRequest.payloads`, port name -> hash-pinned
`PayloadRef`) -- no side channels (AD-22):

- `plan` (kind `plan`): the raw G-code bytes.
- `cam_machine` / `cam_tooling` (kind `table`): serialized
  `MachineRecord`/`ToolRecord` (`regolith.harness.models.cam.records`)
  -- travel/kinematics/spindle-or-nozzle and tool diameter/flutes/
  stickout.
- `cam_target` (kind `table`): a serialized `StockTarget` -- the
  fixture stand-in for a resolved target geometry (stock envelope,
  finished envelope, declared margin, per-feature touch zones).

**WO-66 note**: `std.machines`/`std.tooling` (the real stdlib record
families these mirror) had not landed when this pack was built;
`tests/harness/test_cam_models.py` uses fixture records with the same
shape. Swapping to the real stdlib refs once WO-66 lands is a tracked
follow-up (see the WO-67 close-out ledger in
`docs/workflow/work-orders/WO-67-cam-verification.md`) -- it should
not require changing the model signatures, only which records the
orchestrator stages.

## Verifying a supplied plan at the source level (WO-69)

Spell the plan on the part it machines, naming the extern G-code ref,
its dialect, and the machine/tooling records to check against:

```hematite
part pillow_block:
    plan: extern("op10.nc", gcode_fanuc) machine=fixture_mill_3axis, \
          tooling=fixture_tool_1, resolution=0.05mm
```

This lowers (`crates/regolith-lower/src/claims.rs`, `push_plan_
obligations`) to exactly the five `cam.*` obligations, keyed
distinctly by claim name (`cam.parse`/`cam.envelope`/
`cam.collision_coarse`/`cam.removal`/`cam.coverage`); removing the
`plan:` field removes all five. `machine=`/`tooling=` mirror the
existing `process=<head>(args)` key=value spelling (`stage cut:
process=laser_cut(sheet=1.5mm)`'s convention) rather than a new
argument shape; `resolution=<qty>` is the declared voxel error term
`cam.removal` needs (charter D3 conservatism). A malformed clause
(missing ref, or a dialect outside `gcode_fanuc`/`gcode_marlin`) is
E0449, with no obligations emitted -- honest silence, never a guess.

The plan's TARGET is not a third declared reference: it is the
enclosing part's OWN realized geometry, resolved the same
structural way a fluid edge's `from=` ref is (matched by subject
name against whatever `RealizedInput`s this build was supplied,
D128) -- when one is present, its digest is threaded onto the
`cam_target` `StockTarget`'s `geometry_digest` field as the cited
"target RealizedGeometry digest" (deliverable 2); a build with no
realized geometry for the part still discharges against the
declared `[[stock_target]]` record's own fixture bounds.

At the orchestrator (`regolith.orchestrator.plan_staging`, mirroring
`costing.py`'s staged-doc precedent): `machine=`/`tooling=` resolve
against local `[[machine]]`/`[[tool]]`/`[[stock_target]]` records
(`records/*.toml` under the project root, `key = "..."` the SAME
dotted-ref text the `plan:` clause names -- WO-66's `std.machines`/
`std.tooling` stdlib loaders are a swap-in follow-up, same posture as
the WO-67 ledger's own note); the extern ref's bytes are read off
disk and staged into the build's payload store; every consumed
record lands in the lockfile as an INV-22 `pin` line, and the extern
ref itself pins under a `extern(<ref>)` cause key.

## Trying it directly today

```python
from regolith.harness.models.cam.ir import Dialect
from regolith.harness.models.cam.models import CamEnvelopeModel
from regolith.harness.model import DischargeRequest
from regolith.orchestrator.payload_store import PayloadStore

store = PayloadStore(".regolith-demo")
plan_ref = ...  # PayloadRef(kind="plan", digest=store.put(open("op10.nc","rb").read()))
machine_ref = ...  # PayloadRef(kind="table", digest=store.put(MachineRecord(...).model_dump_json().encode()))

model = CamEnvelopeModel(Dialect.fanuc)
request = DischargeRequest(
    claim_kind=model.signature.claim_kind, limit=0.0, inputs={},
    payloads={"plan": plan_ref, "cam_machine": machine_ref},
    regimes=(Dialect.fanuc.value,),
)
result = model.discharge(request, registry_version="test", resolver=store.resolve)
```

See `tests/harness/test_cam_models.py` for the full corpus: a good
`pillow_block` plan discharging all five models Valid, and one broken
variant per failure class (`out_of_travel.nc`, `rapid_through_stock
.nc`, `undercut.nc`/`overcut.nc`, `missing_feature.nc`) each yielding
the named violated/indeterminate result with a line citation.

## Declared exclusions (v1, charter sec. 3)

Surface finish, chatter, thermal effects, tool wear, and five-axis
kinematics are OUT of scope -- `by test` territory until a calibrated
model with citations exists. `cam.removal`'s v1 arithmetic is a
bounding-envelope approximation (deepest cutting Z vs. the target
floor), not a full voxel raster; a full raster is future depth. A G-
code EMITTER (plan generation) is explicitly not built.

## Known gap: `cam.removal`'s margin arithmetic (cross-note, not fixed here)

`cam.removal` reports its declared `resolution_mm` as the model's
worst-case `eps` at an EXACT-ZERO `limit` (`DischargeRequest(limit=
0.0, ...)`, the shape every `cam.*` model uses). `Model.discharge`'s
one shared margin rule charges `eps` against that zero limit
(`margin = limit - (value + eps)`), so a perfectly good removal
(`value` == excess == 0.0) with ANY nonzero declared resolution
reports **violated**, not the intended conservative Valid/
indeterminate split -- reproducible directly against WO-67's own
`tests/harness/test_cam_models.py` request shape, independent of the
WO-69 linkage this guide documents (see
`tests/test_cli_build_plan_cam.py`'s
`test_a_good_plan_discharges_all_five_cam_models_valid`, which proves
the other four models discharge Valid and documents this one). Fixing
the arithmetic (likely: `cam.removal` needs its own margin
convention, or the checked excess needs to already fold `eps` in
before comparison) is `std.cam` pack work (WO-67's own follow-up
territory), out of WO-69's Rust-lowering/Python-staging scope --
recorded here as the cross-note rather than patched around.
