# 13 -- Verifying a supplied CAM plan (`std.cam`)

Status: DESIGNED/PARTIAL. The `std.cam` model pack itself is WORKING
(five models over two dialects, exercised directly against the
harness discharge path -- see `tests/harness/test_cam_models.py`).
The `plan: extern(<ref>, gcode_<dialect>)` LOWERING that would let a
`.hema` part spell a plan and have the compiler emit these
obligations automatically is NOT yet built (see "What is missing"
below) -- this guide teaches the pack's model contract so it is ready
to consume obligations once that lowering lands, and shows how to
exercise it directly today.

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

## What is missing (deliverable-1 finding)

The `plan: extern(<ref>, gcode_<dialect>)` SOURCE-LEVEL syntax has no
lowering today: nothing in `regolith-lower` (`crates/regolith-lower/
src/claims.rs`) emits `cam.*` obligations from it, and no `fmt.
gcode_fanuc`/`fmt.gcode_marlin` reader is registered anywhere (the
`formats` kind list in `docs/spec/regolith/11-packages-and-stdlib.md`
sec. names them as a FUTURE vocabulary entry, not a landed reader).
Building that lowering is Rust work in `regolith-lower`/
`regolith-syntax`, outside this WO's `Language: Python; Rust none`
header -- it is recorded as a follow-up in the WO-67 close-out
ledger rather than invented here.
