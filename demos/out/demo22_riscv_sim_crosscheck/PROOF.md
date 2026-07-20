# PROOF: riscv_hart_rv1 sim demo: expected_signals-vs-sim cross-check (WO-158)

- pipeline path: `regolith build --release` + `regolith ship` (release and `--emit-profile debug`) on `riscv_hart_rv1` through the real CLI, plus a direct `HdlSimAssertGenericModel` discharge (the same discharging model class the pipeline's own `hdl.sim_assert` obligation uses) fed through the real, unmodified `SimBackend` -- see the named-gap section below for why the direct call is needed today.

## Census delta (WO-157's own discharge, cited not repeated)

- BEFORE (recon's own pre-WO-157 baseline citation): 79 obligations, 4 discharged, 75 accepted deviations.
- AFTER (read live from `tests/golden/data/fleet_census.json['riscv_hart_rv1']`, never hand-typed): 81 obligations, 5 discharged, 76 accepted deviations.
- the delta is RECLASSIFICATION, never invented obligations: 2 obligation(s) were newly formed by the stimulus requirement itself (the `require: stimulus: sim(...)` clause), and 1 discharge(s) moved from accepted-deviation to real, model-backed DISCHARGED (F152 bar).

## The E1105 cross-check (WO-158 deliverable 4)

Real, reproducible run: `--emit-profile debug` ships the flagship's own `harness/expected_signals.json`; the `hdl.sim_assert` model (`HdlSimAssertGenericModel`) is run directly over `pc_incr.v` + `pc_incr_directed_vectors` (the same source+stimulus the pipeline's own obligation discharges); `cross_check_expected_vs_sim` classifies every shipped window against the simulated design's port set.

Fleet result today: HartPackage.clk_in=no_overlap

This is an HONEST NO_OVERLAP finding, not a fabricated agreement (D250.3): the flagship's one allocated debug channel (`HartPackage.clk_in`) is an SI impedance claim (`clk_z0.lo`), not a net `pc_incr`'s own port list (['branch_target', 'pc_in', 'pc_next', 'sel_branch']) carries -- there is currently no digital tap whose target net names a `pc_incr` port, so there is nothing for THIS demo's cross-check to agree or disagree about on the real shipped artifact. Named, not silently dropped.

## Fixture cross-checks (mechanism proof, NEVER shipped fleet artifacts)

To prove the cross-check itself actually distinguishes agreement from disagreement (not just report the one no-overlap case the real fleet data happens to produce today), two clearly-labeled fixtures run the SAME real verilator discharge over WO-155's own `mux2`/`mux2_broken` non-fixture example designs:

- correct mux2: `agreement` -- simulated trace's 'y' port matched every directed vector's expectation
- broken-priority mux2 mutant: `disagreement` -- simulated trace recorded a mismatch on 'y'

## Timing closure (WO-156, honest partial)

WO-156 landed `TimingBudgetModel`/`elec.timing_budget` generally (T-0027's follow-up), but `riscv_hart_rv1`'s own corpus declares no `budget: ...: kind=timing` clause -- there is no timing-closure table for THIS flagship to ship. This demo ships the sim-only half as an honest partial (WO-158's own allowance for exactly this case); no fabricated timing row.

## Named gap: ship-time sim/ wiring

`regolith ship` (release or debug profile) does not yet thread a `sim=` `SimProducts` map into `BackendInputs` the way `hdl=`/`firmware=` already are (`backends/ship.py::ship`, `cli/app.py` have no `sim=`/`"sim"` spec-block channel) -- so a real `regolith ship` run today never emits `sim/uarch/{trace.vcd,sim_report.json}` even though `SimBackend` (WO-155 deliverable 7) is fully implemented and tested. This demo obtains the real family by calling the discharging model directly (see the module docstring) and ships it through the same unmodified `SimBackend`. Filed forward as a new ticket (see the T-0028 progress note) -- out of this demo's own scope to wire.

## Re-run

```
uv run python -m demos.demo22_riscv_sim_crosscheck
```

## Artifacts

| artifact | bytes | sha256 |
|----------|-------|--------|
| `crosscheck.json` | 716 | `sha256:a40e44216fd2cd418fe9ee9ff56b5495f01890362b7014499023aff985a19de9` |
| `debug/acceptance_ledger.json` | 44462 | `sha256:60e07f2b8833787c91ceae451bc888b26ab2886521909f0afb5d157bbf0ca157` |
| `debug/artifact_index.json` | 9531 | `sha256:237bb10d88c37770b7295edb4afb0d1a2d03f08c20e941c44fff44a194d22282` |
| `debug/calc/audit_index.json` | 29361 | `sha256:67e395f391fa70856c4e20def128d459f690e8ee6d1e9ad720134726a34dd0c6` |
| `debug/calc/calc_book.json` | 37402 | `sha256:bcd016febe03ffae488d570c1d1e1d176ae4f47be91b30742f3f61c24be4d363` |
| `debug/calc/clk_rs__632e8824a899.pdf` | 6156 | `sha256:9bc046314f61e3d01d49ffea90956282332084aa16b8758e1868b1d670e2602d` |
| `debug/calc/clk_z0.hi__632e8824a899.pdf` | 5984 | `sha256:fd22e2659052e04f24c9669d6949d5357118d26f68b70965185d3c4903797f1d` |
| `debug/calc/clk_z0.lo__632e8824a899.pdf` | 5984 | `sha256:bac07fb677afa48cdbe7d4cf2f20f17564d9d6fe5eae80593352830b60a1b793` |
| `debug/calc/hdl.build__c5c1cf91fe37.pdf` | 6121 | `sha256:58aa9d96f753d7c52ab38a843cbe1c5c997996b283eb3cd8ec98fa60645789a1` |
| `debug/calc/hdl.sim_assert__c5c1cf91fe37.pdf` | 6403 | `sha256:5e6bad126539e3629ebb5be79363ab354fd2a9b50824a4157ca87f3b9c744a30` |
| `debug/drawings/drawings/contract_graph.drawing.json` | 1827 | `sha256:64e8059c9ff5981c8114d69002bb37206e0a132a198a69d6fee646bb0491bc7e` |
| `debug/drawings/drawings/contract_graph.dxf` | 2610 | `sha256:5685f690a7122b3f61db2031e70fe812ac3a077e1adb3212e9b779a3151fffe4` |
| `debug/drawings/drawings/contract_graph.explain.txt` | 2001 | `sha256:dbee7dfcecce281cbc1158893c4387e0e99d814d099cd249d3881fc96c73a279` |
| `debug/drawings/drawings/contract_graph.pdf` | 3500 | `sha256:9cf6e5291537b72038e39a739d7a33c36f96d05fd5ac9c65b010393f31c791c2` |
| `debug/drawings/drawings/contract_graph.svg` | 4361 | `sha256:1a7ef513e0422ee383cae36027948ddaeac97274dcb7ff3bc6b9e7edc8b80859` |
| `debug/gate_summary.json` | 207 | `sha256:70b6fd55574675636ae6c388cb334f9a7ab3da6b627204e603af56b882cfde0d` |
| `debug/harness/bringup.md` | 988 | `sha256:9e05d46f2afe5943af36631495636a36e3fee8fd769cc8b55894d1c1bdae9c98` |
| `debug/harness/capture_clocks.sigrok-cli` | 257 | `sha256:6d7a781595f63c76a42f9ee95e3d7d59bd32680b68e0bcb153837d205a597b2e` |
| `debug/harness/expected_signals.json` | 447 | `sha256:d63ee70156ead76f5557d057efdfe2a17945048e033bf57b81669bc9ff4376e5` |
| `debug/harness/tap_map.json` | 1526 | `sha256:72df4ef66b2024d2fa11a6765e3a0bf783d380f2b0e3e7be08e259bfd243b11b` |
| `debug/hdl/hdl/pc_incr_rtl/source_manifest.json` | 127 | `sha256:5d319c5b87a8945fe979d812b4e962d1c936767fb1dfeb9586337e9a8d84113e` |
| `debug/hdl/hdl/pc_incr_rtl/src/debug_taps.v` | 382 | `sha256:c9f73693ee9bba64865e160c93066e881367c8c2c8ad19d76b45e284cadf0963` |
| `debug/hdl/hdl/pc_incr_rtl/src/pc_incr.v` | 1046 | `sha256:d7baf63a2cb16d15a8bf0b1d936aadc5460428238ac57ea9c5e79755aa99220b` |
| `debug/hdl/hdl/pc_incr_rtl/tier_report.json` | 683 | `sha256:83a883832d675d6eea63a0df935efadd46f865da2a6a540e8a6e4829e3737f64` |
| `debug/index.md` | 3358 | `sha256:c616f9615e4f01d688506b09a6d8c14d88780c7cc5d02533317a288e50b2c699` |
| `debug/manifest.json` | 12686 | `sha256:0e345a1fe3ae2804ec9b94f6accef23b8ba0af1b61981df0bfea4ba02e71a274` |
| `debug/parity_ledger.json` | 99430 | `sha256:8dfce201876727cb71fcc6bbcc1ef65a5bf3e38c92545d2c37fe5b4a1335405c` |
| `release/acceptance_ledger.json` | 44462 | `sha256:60e07f2b8833787c91ceae451bc888b26ab2886521909f0afb5d157bbf0ca157` |
| `release/artifact_index.json` | 7559 | `sha256:86a834630ed61f90d1ff2eee1030bd3c1cb9fb7aeb68d7013d879f429c6f2289` |
| `release/calc/audit_index.json` | 29361 | `sha256:67e395f391fa70856c4e20def128d459f690e8ee6d1e9ad720134726a34dd0c6` |
| `release/calc/calc_book.json` | 37402 | `sha256:bcd016febe03ffae488d570c1d1e1d176ae4f47be91b30742f3f61c24be4d363` |
| `release/calc/clk_rs__632e8824a899.pdf` | 6156 | `sha256:9bc046314f61e3d01d49ffea90956282332084aa16b8758e1868b1d670e2602d` |
| `release/calc/clk_z0.hi__632e8824a899.pdf` | 5984 | `sha256:fd22e2659052e04f24c9669d6949d5357118d26f68b70965185d3c4903797f1d` |
| `release/calc/clk_z0.lo__632e8824a899.pdf` | 5984 | `sha256:bac07fb677afa48cdbe7d4cf2f20f17564d9d6fe5eae80593352830b60a1b793` |
| `release/calc/hdl.build__c5c1cf91fe37.pdf` | 6121 | `sha256:58aa9d96f753d7c52ab38a843cbe1c5c997996b283eb3cd8ec98fa60645789a1` |
| `release/calc/hdl.sim_assert__c5c1cf91fe37.pdf` | 6403 | `sha256:5e6bad126539e3629ebb5be79363ab354fd2a9b50824a4157ca87f3b9c744a30` |
| `release/drawings/drawings/contract_graph.drawing.json` | 1827 | `sha256:64e8059c9ff5981c8114d69002bb37206e0a132a198a69d6fee646bb0491bc7e` |
| `release/drawings/drawings/contract_graph.dxf` | 2610 | `sha256:5685f690a7122b3f61db2031e70fe812ac3a077e1adb3212e9b779a3151fffe4` |
| `release/drawings/drawings/contract_graph.explain.txt` | 2001 | `sha256:dbee7dfcecce281cbc1158893c4387e0e99d814d099cd249d3881fc96c73a279` |
| `release/drawings/drawings/contract_graph.pdf` | 3500 | `sha256:9cf6e5291537b72038e39a739d7a33c36f96d05fd5ac9c65b010393f31c791c2` |
| `release/drawings/drawings/contract_graph.svg` | 4361 | `sha256:1a7ef513e0422ee383cae36027948ddaeac97274dcb7ff3bc6b9e7edc8b80859` |
| `release/gate_summary.json` | 207 | `sha256:70b6fd55574675636ae6c388cb334f9a7ab3da6b627204e603af56b882cfde0d` |
| `release/hdl/hdl/pc_incr_rtl/source_manifest.json` | 127 | `sha256:5d319c5b87a8945fe979d812b4e962d1c936767fb1dfeb9586337e9a8d84113e` |
| `release/hdl/hdl/pc_incr_rtl/src/pc_incr.v` | 1046 | `sha256:d7baf63a2cb16d15a8bf0b1d936aadc5460428238ac57ea9c5e79755aa99220b` |
| `release/hdl/hdl/pc_incr_rtl/tier_report.json` | 683 | `sha256:83a883832d675d6eea63a0df935efadd46f865da2a6a540e8a6e4829e3737f64` |
| `release/index.md` | 2851 | `sha256:7d39df5ba3f6a372fd698f3ef32dd71f2337843769a399457dd5c41919a3543a` |
| `release/manifest.json` | 11977 | `sha256:97e254e3c15babc341696d5f4ab43713e74aeaa41767dfe13bfff04715114b65` |
| `release/parity_ledger.json` | 99430 | `sha256:8dfce201876727cb71fcc6bbcc1ef65a5bf3e38c92545d2c37fe5b4a1335405c` |
| `sim/fixture_mux2_broken/sim_report.json` | 528 | `sha256:c2bf286ed04f3e78160022ab2638e1b6fa4d06c77578a35356e3212d19c9b476` |
| `sim/fixture_mux2_broken/trace.vcd` | 688 | `sha256:a59875aae435300820815fac218e57820fa0dca524f05a1a4420413769987d20` |
| `sim/fixture_mux2_ok/sim_report.json` | 461 | `sha256:502d6b85fc4fd4d00eab4084e805d2f52f0f8acc37dc0e3f3585c8abf2fbb9a0` |
| `sim/fixture_mux2_ok/trace.vcd` | 676 | `sha256:4755348b913a3d60495ece5a6294a9eafdcbab4f5afa93b83eb8ee5283a191fe` |
| `sim/uarch/sim_report.json` | 467 | `sha256:6eec92417366f08ef8734d7c50199321d8fb8284dfc656e59926af30c96c8127` |
| `sim/uarch/trace.vcd` | 1596 | `sha256:a97fc529f02a776e5f9f36ced0d615237805cbfdd2255c4892d53d618132ccdb` |
