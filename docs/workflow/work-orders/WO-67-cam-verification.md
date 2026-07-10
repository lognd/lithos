# WO-67: CAM verification v1 (std.cam check-mode pack)

Status: todo
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
