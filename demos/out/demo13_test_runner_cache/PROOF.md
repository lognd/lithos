# PROOF: regolith test over a corpus net with cache-proven replay

- feature proven: `regolith test` discovers and runs every `test <name>:` declaration under a multi-root corpus net (cuprite + hematite + fluorite + calcite declarations), with content-addressed incremental caching.
- pipeline path: the real `regolith test` CLI, each scenario through the ordinary build door (AD-22) -- no private pipeline, no fake runner.
- corpus net: 5 scenario(s) across 4 root(s): `examples/flagships/printer_k1`, `examples/flagships/cubesat`, `examples/tracks/fluorite/aquarium_loop.test.fluo`, `examples/tracks/calcite/bus_shelter.test.calx`.
- cache proof: run 1 (cold, cache files cleared) reports `from_cache: false` for EVERY scenario; run 2 (unchanged) reports `from_cache: true` for EVERY scenario -- asserted programmatically above, tabulated in `cache_proof.md`.

## Scenarios

| scenario | cold from_cache | warm from_cache |
|---|---|---|
| aquarium_loop_pin_case | False | True |
| build_sanity | False | True |
| bus_shelter_pin_case | False | True |
| kestrel_link_verdict | False | True |
| rail_structural_verdict | False | True |

## Re-run

```
uv run python -m demos.demo13_test_runner_cache
```

## Artifacts

| artifact | bytes | sha256 |
|----------|-------|--------|
| `cache_proof.md` | 260 | `sha256:fcb8c0be8e7e6afc1f3c5d76c57f716f6cbdb7ae13615de2eec78eac342ea9c1` |
| `run1_cold.json` | 1661 | `sha256:dcadea8f469d5861072f3af9ef12fa7e4b9cfe9c7f34055526a744fb5f3c5b09` |
| `run2_warm.json` | 1656 | `sha256:9c55fe58e1edf6b04aebf7f2520cec83dd3377be5f2175fe9081c6e3fb664793` |
