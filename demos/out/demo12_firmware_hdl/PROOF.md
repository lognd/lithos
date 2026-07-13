# PROOF: shipped firmware tree + HDL tier evidence (computer track)

## HDL (riscv_hart_rv1)

- `build --release` discharges the flagship's `hdl.build` obligation through the std.hdl verilator pack over its own `pc_incr.v`; the shipped tier row: model `hdl_build@1+verilator5.047`, tool verilator 5.047, status DISCHARGED.
- named absences, shipped verbatim in `tier_report.json`: no sim_assert/equiv_directed evidence on this subject, and netlist absent because no synthesis-to-netlist model exists in std.hdl (WO-82/D202) -- the named-absence surface, never a fabricated netlist.

## Firmware (espresso_machine BrewCtl / stm32g071cb)

- pipeline path: the stm32g0 registry record's own pin table -> `assign_pinmux` (WO-35 deterministic solver) for the uart2 debug pair -> `FirmwareDesign` -> `realize_firmware` (WO-37 codegen) -> `regolith ship --spec` with the `"firmware"` block (WO-102 channel).
- pinmux assignments (each lockfile-caused):

```
u_mcu.uart2.tx -> pa2 (planner(pinmux uart2.tx))
u_mcu.uart2.rx -> pa3 (planner(pinmux uart2.rx))
```

- the shipped `build_report.json` names the honest ELF absence (no toolchain invocation pinned an image) -- the generated contract header, family-pack BSP, linker script and build fragment ship; a binary never does unless a real toolchain produced one.
- no invented clocks/events: the design declares none in `on`-block/clock form, so those ledgers are empty.
- WO115-F2 (named gap): no lowering pass derives `FirmwareDesign` from `computer`/`bind` declarations (the WO-37 input is caller-supplied by design, v1), and the cubesat OBC's stm32l496 family has no registered family pack (only the stm32g0 reference pack) -- fleet firmware ships only through this caller channel today.

## Re-run

```
uv run python -m demos.demo12_firmware_hdl
```

## Artifacts

| artifact | bytes | sha256 |
|----------|-------|--------|
| `espresso/firmware/firmware/brewctl/build_report.json` | 535 | `sha256:865893e98ec27ddc891a5b0998b5bd7e2c014c1199664c3dbff78f968eafaddf` |
| `espresso/firmware/firmware/brewctl/generated/Makefile.fragment` | 304 | `sha256:0ddf13f657da6bba8563244257200b26ef1d7e580114f129fc6b647b526d8c20` |
| `espresso/firmware/firmware/brewctl/generated/brewctl.ld` | 138 | `sha256:981e0d9a9173b6417252918023926874e3fe78463f1974fbe317cda73856e701` |
| `espresso/firmware/firmware/brewctl/generated/brewctl_bsp.c` | 754 | `sha256:b07b7555aa2033e4059248ba88e6dc62e9d4fef8e7cfe64934592726fc62e003` |
| `espresso/firmware/firmware/brewctl/generated/brewctl_contract.h` | 722 | `sha256:f486ef544e7593412ae8cc5f46d57f37900778bb98037a8c4b7c9f1b082f3552` |
| `espresso/firmware/firmware/brewctl/generated/brewctl_isr.c` | 177 | `sha256:7ac6dc82fbd00dff0be752d7301370e6c97d39c8e40bbc7e9edf0ff2ac39aa88` |
| `riscv/hdl/hdl/pc_incr_rtl/source_manifest.json` | 127 | `sha256:5d319c5b87a8945fe979d812b4e962d1c936767fb1dfeb9586337e9a8d84113e` |
| `riscv/hdl/hdl/pc_incr_rtl/src/pc_incr.v` | 1046 | `sha256:d7baf63a2cb16d15a8bf0b1d936aadc5460428238ac57ea9c5e79755aa99220b` |
| `riscv/hdl/hdl/pc_incr_rtl/tier_report.json` | 644 | `sha256:b6c4fd516bd33b211ef7a9776d7a3a3009dc5221e59a82d59a510e6341e9c35d` |
| `ship.spec.demo12.json` | 4588 | `sha256:c623980ea25f6005b2acdd51c86e8c9560d122a0287f9f7782db32f61dc55288` |
