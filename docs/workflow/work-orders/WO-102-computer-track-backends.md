# WO-102 -- Computer-track emission: firmware + HDL backends

Status: open
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
