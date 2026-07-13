# WO-110 fixture release residuals

Accepted deviation for the `wo110_manufacturable_fixture.hema`
release-tier proof (D232.1c):

- `import(std.mech.cnc)`: module-import structural conformance edge
  (Class A, D195.3/F130) -- no scalar window exists on a bare import;
  waived by design, exactly the fleet convention. The fixture's
  `makeable` claim is deliberately UNwaived: it must discharge through
  `mfg_manufacturable_mill@1` for the fixture to gate green.
