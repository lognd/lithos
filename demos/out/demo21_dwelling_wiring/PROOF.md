# PROOF: dwelling/house-wiring program: branch circuits -> panel siting (cuprite-calcite tandem) -> cable + panel schedule artifacts (WO-167)

- pipeline path: real cuprite/calcite source (`examples/flagships/dwelling_r1/circuits.cupr` + `panel.cupr` + `dwelling.calx`) checked clean via `regolith check` (slice a) -> `DwellingCircuitPlan` (slice b, the SAME declared circuit data as the source) -> `regolith.realizer.elec.dwelling_wiring.realize_dwelling_circuit_plan` discharging every branch circuit's ampacity/voltage-drop claim through the real WO-135 `AmpacityModel`/`VoltageDropModel` and gating with the real WO-170 `check_ampacity_containment`/`check_voltage_drop_limit`/`check_working_clearance` predicates -> `cable_schedule`/`panel_schedule` artifacts (slice c) via the existing `Table`/`DrawingModel` schedule machinery (`regolith.backends.cost_schedule`).
- feature proven: a 200A/240V single-phase residential service with four author-declared branch circuits (kitchen small-appliance 20A/12AWG, bedroom lighting 15A/14AWG, bathroom 20A/12AWG, dryer 30A/10AWG) all pass their declared derated-ampacity and 3%-voltage-drop budgets; the panel's 0.75m declared working clearance (`UtilityCloset.depth - panel.footprint_depth - 0.75m` in `panel.cupr`, this design's own read of NEC Table 110.26(A)(1) Condition 1) meets its own declared minimum exactly.
- capability registration: `dwelling_wiring` domain registered via `regolith.backends.capabilities.register_capability` (all seven `RealizerCapability` fields populated: `program_kind`=`DwellingCircuitPlan`, `realized_kind`='dwelling_wiring.realized', `artifact_families`=('cable_schedule', 'panel_schedule'), one `deterministic` tool-adapter tier -- no external tool is invoked -- `process_records` referencing the three EXISTING WO-170 `std.process` elec-install records only, three real `dfm_checks`, and three EXISTING `elec.power.*` claim kinds, no new claim vocabulary).
- honesty labels: panel bus-ampacity/breaker-lugs rating/branch-slot-count is a NAMED REFUSAL (D250 sec. 3, see `dwelling/checks_report.json`'s `panel_catalog_content` entry) -- no breaker/panel manufacturer catalog record exists in `std.power` beyond WO-134/134B's landed transformer catalogue, and none is fabricated here.
- SCOPE NOTE (see this script's module docstring): the schedule artifacts are driven from an in-memory `DwellingCircuitPlan` mirroring the `.cupr` source's own declared data, rather than through a schedule-emitting `regolith build`/`ship` stage -- no such stage exists yet for the `power`/panel net kind (the same F-WO137-1 drawings-producer gap `power.cupr`'s ship spec already names); the cuprite/calcite source itself, the realizer, the DFM checks, and the capability registration are the REAL WO-167 code path, driven end to end above.

## Re-run

```
uv run python -m demos.demo21_dwelling_wiring
```

## Artifacts

| artifact | bytes | sha256 |
|----------|-------|--------|
| `cable_schedule/cable_schedule.pdf` | 5416 | `sha256:60c748dcf6300f02fe797b09dfa3df86242d636114d8ea24c70446bfb0982295` |
| `cable_schedule/cable_schedule.svg` | 8401 | `sha256:f44cd02258aabaebba7b5ede5fa95e3740c0b9e5bd2ef416a96ce3c6fcd964e2` |
| `dwelling/checks_report.json` | 1294 | `sha256:6964db2e2f1cc01b1c13283f2d5400ec234cc5038b23b0ff91c57e7cd4a3991d` |
| `panel_schedule/panel_schedule.pdf` | 4721 | `sha256:a9fe42166e2a7466bd91416f30c80e9f8bf612df78f6568b87d859fca38677af` |
| `panel_schedule/panel_schedule.svg` | 7139 | `sha256:132e15a26eeab61322a51a01b40d695c06aa96cecd312261590433288aba31c9` |
| `source_check/check_output.txt` | 1044 | `sha256:d16564dc4582103a3d47fd93e1f445c10caf06b55b9a492f87ed70baed37555f` |
