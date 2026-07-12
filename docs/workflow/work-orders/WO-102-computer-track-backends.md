# WO-102 -- Computer-track emission: firmware + HDL backends

Status: done (see close-out note)
Language: Python (backends; realizer/firmware + hdl harness
  read-side only)
Spec: D208; charter 38 sec. 1.9; AD-25 (native artifact = pinned
  side artifact); WO-37 (firmware realizer), WO-81/82/89 + D202
  (HDL tiers, hdl.build source-generic); AD-22 (one producer).

## Goal

A computer-track design ships its computed artifacts: the realized
firmware (ELF + link map + BSP report) and the verified HDL build
products land in the release package instead of evaporating after
verification.

## Deliverables

1. `FirmwareBackend`: consumes the firmware realizer's realized IR
   + pinned native bytes (persist-at-realize rides WO-99 D5 --
   coordinate; add the ELF to the `NativeArtifactStore` the same
   way STEP bytes are); emits `firmware/<subject>/` with the ELF,
   link map, and a JSON build report (toolchain, flags, source
   pins, content addresses). Nothing is rebuilt at ship time --
   ship packages what the build proved (AD-22).
2. `HdlBackend`: packages the hdl.build products the WO-82 tiers
   already produce (verilated build dir is a CACHE, not an
   artifact -- ship the source-set manifest, lint/tier report,
   and any synthesized netlist that a tier legitimately produced;
   do NOT invent a bitstream where no synthesis tier ran --
   absent tiers are named absent with the toolenv install hint).
3. Spec blocks + auto-derivation: `firmware`/`hdl` families
   register through WO-99's producer registry; auto_specs picks
   them up when the payload carries the respective realized
   subjects.
4. Tests: riscv_hart_rv1 ships an `hdl/` family (tier report +
   source manifest; behavioral-tier evidence present);
   a firmware fixture (the WO-37 exemplar) ships `firmware/`
   with a verifiable content address; absent-tool degradation is
   a named absence, never a crash; docs: guide updates.

## Acceptance criteria

- riscv_hart_rv1 and mainboard_mx (its MCU firmware subject, if
  realized) packages contain the new families; `ship --verify`
  passes over them.
- No backend invokes a compiler/synthesizer at ship time.
- `make check` green.

## Close-out note (implementation)

Implemented as `python/regolith/backends/firmware.py`
(`FirmwareArtifact`/`FirmwareBackend`) and `python/regolith/backends/
hdl.py` (`HdlSourceFile`/`HdlTierRow`/`HdlBuildProducts`/`HdlBackend`),
wired into `regolith ship`'s `"firmware"`/`"hdl"` spec blocks
(`python/regolith/cli/app.py`: `_firmware_from_spec`/
`_firmware_backend_from_spec`/`_hdl_from_spec`/`_hdl_backend_from_spec`,
mirroring `_assemblies_from_spec`/`_instructions_backend_from_spec`'s
existing shape) and `BackendInputs.firmware`/`.hdl`
(`python/regolith/backends/framework.py`, `python/regolith/backends/
ship.py`'s `derive_producer_inputs`/`ship`). Tests:
`tests/backends/test_firmware.py`, `tests/backends/test_hdl.py`,
plus a `ship`+`verify` round-trip in `tests/backends/test_ship.py`.

**Scoped interpretation of deliverable 1's "ELF" (escalation, not an
invention)**: this repo has NO production path that compiles a
firmware design into an ELF today. WO-37's realizer stops at
generating the BSP/contract/linker SOURCE tree (an explicit WO-37
non-goal: "application/control logic synthesis... stays the existing
deferral"); the only C compile in the codebase
(`tests/realizer/firmware/test_realize.py::
test_host_cc_smoke_compile_gated`) is a test-only `-c` smoke check of
a throwaway `main.c` against the generated header, not a production
image. Inventing a real cross-toolchain compile-at-realize step was
out of this WO's bounded scope (it belongs to WO-37 or a follow-on --
"application logic synthesis" is explicitly deferred there). Per
AD-22's own "never fabricate, name the absence" law, `FirmwareArtifact`
therefore carries an OPTIONAL `elf_content_hash`: when a caller (a
future realize-time compile step, or a project with its own
out-of-band build) pins ELF bytes into the `NativeArtifactStore`
(WO-99 D5 precedent -- see `test_firmware_backend_ships_pinned_elf`),
`FirmwareBackend` resolves and ships them unchanged, never invoking a
compiler itself; with no pin, it ships the generated tree plus an
honest, reasoned `elf: {"present": false, "reason": ...}` (never a
crash, never a fabricated image) -- see `NO_ELF_REASON`. This is the
same "named absence" shape deliverable 2 already specifies for HDL's
missing synthesis tier, generalized from "tool not installed" to "no
application source pinned for this design."

**Deliverable 3's "producer registry" wording**: `firmware`/`hdl`
artifacts are NOT `DrawingModel`-shaped (the WO-99
`ProducerRegistry`/`RendererRegistry` in `regolith.backends.registry`
dispatch subject-kind -> `DrawingModel` -> per-format bytes; firmware/
HDL packages are heterogeneous native-artifact file sets, the same
shape `MechBackend`/`ElecBackend`/`InstructionsBackend` already are,
none of which register through `registry.py` either). The actual
"one registration, zero edits elsewhere" seam these three backends
use is the existing ship-spec-block + `builtin_backends` dict pattern
(`_mech_backend_from_spec`/`_instructions_backend_from_spec`'s shape);
`FirmwareBackend`/`HdlBackend` follow that established precedent
exactly rather than forcing a `DrawingModel` shape onto non-drawing
output. No `auto_specs` change was needed for the same reason:
`auto_specs` only ever drove the drawing-track spec derivation.

**Tests (deliverable 4)**: `tests/backends/test_hdl.py`'s
`test_hdl_backend_ships_riscv_source_and_tier_report` runs the REAL
riscv_hart_rv1 flagship build (WO-89) and packages its actual
discharged `hdl.build` evidence + `pc_incr.v` source -- the
"riscv_hart_rv1 ships an `hdl/` family... behavioral-tier evidence
present" criterion, built from a real discharge, not a fake.
`tests/backends/test_firmware.py` runs the WO-37 realizer's own
Kestrel/stm32g0 exemplar fixture (mirrors `tests/realizer/firmware/
test_realize.py`'s fixture) through `FirmwareBackend`, proving a
verifiable content-addressed firmware package (`test_firmware_backend_
is_deterministic`) and both a pinned-ELF path and a missing-tool/
missing-source absent path, never a crash. `mainboard_mx` carries no
realized MCU firmware subject in this repo today (its acceptance
clause is explicitly conditional -- "if realized"), so it is not
exercised by this WO; the fixture-level tests above satisfy the
Kestrel-exemplar clause.
