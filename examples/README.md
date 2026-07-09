# examples/ -- the spec pressure corpus

Every file here is a pressure test of the language specs and (where
the toolchain can compile it) a golden-corpus input. Conventions:
comments cite the spec section a construct exercises; engineering
numbers are realistic; `.hema`/`.cupr` files are parse-clean
(INV-20: a poisoned subject is corpus rot unless deliberately
negative); claim forms the harness cannot yet lower are EXPECTED and
captured by the deferral golden (`tests/golden/`). Never hand-edit a
golden -- regenerate per the driver docstrings and diff-review.

```
examples/
  tracks/       single-file (or paired) per-track pressure tests
    hematite/   mech: pillow_block, sheet_bracket, weldment_frame,
                molded_clip, torch_igniter (flagship), gear_reducer
    cuprite/    elec + computer: thermostat, mux6to64,
                buck_converter, motor_drive, fpga_mcu_board,
                sampled_buck, flight_controller
    xdomain/    cross-track pairs: sensor_pod, imu_board,
                servo_drive + servo_module
    fluorite/   (cycle 23 / D122) five simple fluid circuits --
                spec pressure tests until WO-31, then the WO-31
                golden corpus
  systems/      multi-file, multi-track projects (the stress corpus,
                design-log cycle 23 / D119)
    cubesat/    Kestrel: the ten-file flagship + magnetite.toml
    (cnc_router, espresso_machine, sdr_transceiver land here as the
     cycle-23 authoring integrates)
  hdl/          (incoming, D120) foreign-HDL fixture pairs proving
                the cuprite/09 coverage matrix: legal .v/.sv/.vhd
                sources + native cuprite equivalents + equivalence
                obligations
  registry/     component-record fixtures (stm32g0, atsamd21,
                rp2040, i2c_protocol) -- the datasheet-transcription
                format, EOPEN-12/D58
  negative/     (cycle 23 / D123) the rule-breaking corpus: each
                file breaks EXACTLY ONE rule, graded obvious ->
                hidden; `# BREAKS:`/`# EXPECT:` headers drive
                tests/golden/test_negative_corpus.py; known-uncaught
                breaks are `# EXPECT-TODO:` xfails = demand signal
```

`.fluo` files are spec pressure tests until WO-31 registers the
extension -- `regolith check` does not see them; each containing
project's README says so. Per-project READMEs carry a file map
(file | subsystem | pressure applied) and a "Candidate findings"
ledger that the coordinating design cycle promotes into
`docs/workflow/design-log/` (project authors never edit the design log).
