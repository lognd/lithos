# PROOF: perf-board jumper/wire assignment -> wiring map + cut list (WO-165)

- pipeline path: an in-memory `PerfboardNetlist` -> `regolith.realizer.elec.perfboard.realize_perfboard` (assign jumpers, run the duplicate-hole DFM check, package as `RealizedBoardAssignment`) -> `regolith.backends.perfboard.PerfboardBackend.produce` (project the wiring map through the `DrawingModel` -> svg renderer, write the cut-list CSV/JSON) -- see the SCOPE NOTE below for why this demo drives that path directly rather than through `regolith build`/`ship`.
- feature proven: the perf-board program end to end -- a fixed 8x12-hole (0.1in/2.54mm pitch) substrate (`PerfboardSubstrate`), a Manhattan point-to-point jumper assignment over 4 nets (`regolith.realizer.elec.perfboard.assign_jumpers`), packaged as a `RealizedBoardAssignment` (`board_assignment.realized`, WO-163's seam), then the `wiring_map`/`cutlist` artifact families (WO-165 deliverable 4), both stamped `tier=deterministic` (no external tool -- the assignment algorithm is entirely in-process, AD-45).
- capability registration: `perfboard` domain registered via `regolith.backends.capabilities.register_capability` (all seven `RealizerCapability` fields populated, including the real `check_no_shared_holes` DFM check -- WO-164's refusal rule).
- 5 wire segment(s) assigned across 4 net(s); every declared net covered exactly once (asserted above).
- honesty labels: no autorouting/obstacle-avoidance solve is claimed (straight point-to-point per net, the WO's own v1 scope); no copper/etching path is claimed (`substrate_kind` = "perfboard", no `.kicad_pcb`).
- SCOPE NOTE (see this script's module docstring): this demo drives the realizer + backend directly from an in-memory netlist rather than through `regolith build`/`ship` against a `.cupr` source -- a real `.cupr` `substrate: perfboard` grammar variant or a staged-build integration point is outside this dispatch's declared surface (cuprite grammar is the power track's surface; `regolith.compiler`/`orchestrate.py` staged-build wiring is beyond the 'subject-selector only' orchestrator scope this dispatch was given) and is named here as a follow-up, per the WO's own escalation option, never silently invented.

## Re-run

```
uv run python -m demos.demo18_perfboard_wiring
```

## Artifacts

| artifact | bytes | sha256 |
|----------|-------|--------|
| `cutlist/board_dimensions.json` | 474 | `sha256:fd8c76be465999ededc49caba579b556c3353e7df88d05cf5015b23c1a0c808f` |
| `cutlist/cutlist.csv` | 201 | `sha256:7f32c5d251a4eb5fc067831ea76eaaf7b2c443fc73775dec45b394f9229ead99` |
| `wiring_map/wiring_map.json` | 4288 | `sha256:e311d18eeb163f377beefa25044d38886eb766c33e5425004dff52ac3e381f0c` |
| `wiring_map/wiring_map.svg` | 4557 | `sha256:faea5a6f4364f0cceb4488abf675c4ed01d19d92bed35a822f2270374c70b377` |
