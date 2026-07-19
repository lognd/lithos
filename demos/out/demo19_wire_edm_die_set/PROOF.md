# PROOF: wire-EDM die-set production program: material state -> profile cut -> bolted die-set assembly (WO-166)

- pipeline path: `HeatTreatStep` (slice a) -> `regolith.harness.models.material_state.check_heat_treat_transition` -> `WireEdmProfile` (slice b) -> `regolith.realizer.mech.wire_edm.realize_wire_edm_profile` -> `regolith.backends.edm.WireEdmBackend.produce` (DXF via the existing `DrawingModel`/`render_dxf` path + setup sheet) -> `DieSetAssembly` (slice c) -> shut-height/alignment/press-tonnage/punch-die-clearance checks -- see the SCOPE NOTE below for why this demo drives that path directly rather than through `regolith build`/`ship`.
- feature proven: two hardened tool-steel plates (D2 punch, A2 die) each state-transitioned as_rolled -> quenched_and_tempered (`std.process/quench_temper`, gated by the real `check_process_sequencing` + `check_quench_section_uniformity` pair, WO-169 wave 1) and each wire-EDM profiled (kerf 0.25mm, spark gap 0.02mm) with every declared corner radius passing `check_wire_edm_corner_radius` and the closed-profile start-hole gate passing `check_wire_edm_start_hole`; the three-plate bolted stack (shut height 57.0mm) passes its declared press-daylight window; the two-guide-pin alignment stack (0.020mm worst-case) passes its declared budget; the required press tonnage (4.181 tons, from the standard blanking-force formula perimeter x thickness x shear strength) passes against the declared 15.0-ton press.
- capability registration: `wire_edm` domain registered via `regolith.backends.capabilities.register_capability` (all seven `RealizerCapability` fields populated: `program_kind`=`WireEdmProfile`, `realized_kind`=`edm_profile.realized`, `artifact_families`=(`edm_profile`, `die_set`), one `deterministic` tool-adapter tier -- no real EDM-machine toolpath post-processor is claimed -- `process_records` citing `std.process/wire_edm`/`quench_temper`/`stamping_blanking`, six real `dfm_checks`, and the `mfg.die_set_producible` claim kind).
- honesty labels: `tier=deterministic` on every emitted file (no real EDM-machine tool adapter claimed, WO-160/AD-45); punch-die clearance is an explicit NAMED REFUSAL (no cited public-domain clearance-percent-by-material bound exists in this repo -- see `die_set/checks_report.json`'s own `punch_die_clearance` entry); the shot-peen recast-layer remediation step is named OPTIONAL and NOT invoked in this demo (no compressive-layer-depth claim is made).
- SCOPE NOTE (see this script's module docstring): this demo drives the realizer + backend chain directly from in-memory IR values rather than through `regolith build`/`ship` against a `.cupr`/`.hema` source -- a hematite grammar addition for a parameterized material-state variant, or a new wire-EDM program verb in `regolith-syntax`/`regolith-lower`, is outside this dispatch's schema-frozen posture (D272 spent; realized kinds stay plain-pydantic, promotable later per the T-0043 posture) -- named here as a follow-up, never silently invented.

## Re-run

```
uv run python -m demos.demo19_wire_edm_die_set
```

## Artifacts

| artifact | bytes | sha256 |
|----------|-------|--------|
| `die_set/checks_report.json` | 1690 | `sha256:4b9f7a2bae715d20eb8014cc44a9f55fe56aec4c8c8a8bf6625ef88b64c5807b` |
| `edm_profile/die_profile.dxf` | 2676 | `sha256:a79a25883d32ceeb73f7bf1e49ed8034a37ebeb894effa31fc843e72d4b2cf48` |
| `edm_profile/die_setup_sheet.json` | 1612 | `sha256:44e86fda9194e230a7993ef1e3fbe442d9cb64f71433eb5dfeb889d81e2f9e5b` |
| `edm_profile/punch_profile.dxf` | 2676 | `sha256:e437771dec8cb1f1fbf36bd6ed9959f1ad0e9f468f9eb7c941267fb99a677846` |
| `edm_profile/punch_setup_sheet.json` | 1617 | `sha256:ff4f2bc1db73d2ac195b92c16f08041811b1b1b3b693d67d2dd58136e85cd916` |
